"""
Lo que hace que las cuentas cierren: la planilla del IESS, las
retenciones al SRI, los décimos acumulados, las horas extra con recargo,
los anticipos que se descuentan solos y los candados para no tocar lo que
ya se pagó o se descontó.
"""

from datetime import date

from django.utils import timezone

from apps.finanzas import calculos
from apps.finanzas.models import ConfiguracionFinanzas, Egreso, PerfilLaboral, RolPagos, categoria
from apps.finanzas.tests_finanzas import Base, D


class ConEmpleada(Base):
    def setUp(self):
        super().setUp()
        self.perfil = PerfilLaboral.objects.create(
            tenant=self.tenant, usuario=self.recepcion, modalidad="dependencia", sueldo=D("482"),
            fecha_ingreso=date(2024, 1, 2), fondos_reserva_mensual=False)

    def generar(self, mes="2026-09"):
        return self.client.post("/api/v1/finanzas/roles/generar/", {"mes": mes}, format="json")


class HorasExtraTests(ConEmpleada):
    def test_horas_suplementarias_y_extraordinarias_sobre_el_valor_hora(self):
        self.perfil.sueldo = D("480")
        self.perfil.save()
        r = calculos.rol(self.tenant, self.recepcion, self.mes,
                         horas_suplementarias=D("10"), horas_extraordinarias=D("4"))
        ingresos = {i["concepto"]: i["valor"] for i in r["ingresos"]}
        # Valor hora 480/240 = 2,00: 10 h × 2 × 1,5 = 30 y 4 h × 2 × 2 = 16.
        self.assertEqual(ingresos["Horas suplementarias (10 h al 50 %)"], "30.00")
        self.assertEqual(ingresos["Horas extraordinarias (4 h al 100 %)"], "16.00")
        self.assertEqual(r["iess"]["aporte_personal"], "49.71")           # 9,45 % de 526
        self.assertEqual(r["neto"], "476.29")

    def test_el_recargo_se_ajusta(self):
        config = ConfiguracionFinanzas.de(self.tenant)
        config.recargo_suplementarias = D("60")
        config.save()
        self.perfil.sueldo = D("480")
        self.perfil.save()
        r = calculos.rol(self.tenant, self.recepcion, self.mes, horas_suplementarias=D("10"))
        self.assertIn({"concepto": "Horas suplementarias (10 h al 60 %)", "valor": "32.00"}, r["ingresos"])

    def test_mas_de_30_dias_o_demasiadas_horas_no(self):
        for extra in ({"dias_trabajados": "31"}, {"horas_suplementarias": "250"}):
            r = self.client.post("/api/v1/finanzas/roles/", {"empleado": str(self.recepcion.id),
                                                             "mes": "2026-09", **extra}, format="json")
            self.assertEqual(r.status_code, 400)


class AnticiposTests(ConEmpleada):
    def anticipo(self, monto="50", dia=date(2026, 9, 15)):
        return self.client.post("/api/v1/finanzas/egresos/", {
            "fecha": dia.isoformat(), "categoria": str(categoria(self.tenant, "sueldos").id),
            "concepto": "Anticipo de sueldo", "monto": monto, "profesional": str(self.recepcion.id),
            "descontar_al_profesional": True}, format="json")

    def test_el_anticipo_apuntado_se_descuenta_solo_y_al_pagar_se_recalcula(self):
        self.generar()
        rol = RolPagos.objects.get(empleado=self.recepcion)
        self.assertEqual(rol.neto, D("436.45"))
        # Se apunta después de generar el borrador: al pagar ya cuenta.
        self.assertEqual(self.anticipo().status_code, 201)
        self.client.post(f"/api/v1/finanzas/roles/{rol.id}/pagar/", {}, format="json")
        rol.refresh_from_db()
        self.assertEqual(rol.neto, D("386.45"))
        self.assertIn({"concepto": "Anticipos entregados en el mes", "valor": "50.00"}, rol.calculo["descuentos"])
        self.assertTrue(Egreso.objects.filter(origen="rol", monto=D("386.45")).exists())

    def test_con_el_rol_ya_pagado_no_se_apunta_ni_se_toca(self):
        r = self.anticipo()
        self.generar()
        rol = RolPagos.objects.get(empleado=self.recepcion)
        self.client.post(f"/api/v1/finanzas/roles/{rol.id}/pagar/", {}, format="json")
        segundo = self.anticipo("20")
        self.assertEqual(segundo.status_code, 400)
        self.assertIn("ya está pagado", str(segundo.data))
        self.assertEqual(self.client.post(f"/api/v1/finanzas/egresos/{r.data['id']}/anular/",
                                          {"motivo": "error"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(f"/api/v1/finanzas/egresos/{r.data['id']}/", {"monto": "10"},
                                           format="json").status_code, 400)
        # El del mes siguiente sí.
        self.assertEqual(self.anticipo("20", date(2026, 10, 3)).status_code, 201)


class IessTests(ConEmpleada):
    def test_planilla_del_mes_pagarla_y_anular_el_pago(self):
        self.generar()
        iess = calculos.obligaciones(self.tenant, self.mes)[0]
        # 45,55 personal + 58,56 patronal (12,15 %) + 40,15 fondos (8,33 %).
        self.assertEqual((iess["tipo"], iess["monto"], iess["vence"]), ("iess", "144.26", "2026-10-15"))
        pendientes = calculos.obligaciones_pendientes(self.tenant, date(2026, 10, 1))
        self.assertEqual([o["tipo"] for o in pendientes], ["iess"])

        r = self.client.post("/api/v1/finanzas/obligaciones/", {"tipo": "iess", "mes": "2026-09",
                                                                "fecha": "2026-10-10"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        egreso = Egreso.objects.get(pk=r.data["id"])
        self.assertEqual((egreso.monto, egreso.categoria.clave, egreso.periodo), (D("144.26"), "sueldos", self.mes))
        self.assertEqual(self.client.post("/api/v1/finanzas/obligaciones/", {"tipo": "iess", "mes": "2026-09"},
                                          format="json").status_code, 400)
        self.assertEqual(calculos.obligaciones_pendientes(self.tenant, date(2026, 10, 1)), [])
        # No se corrige a mano, pero se anula y vuelve a quedar pendiente.
        self.assertEqual(self.client.patch(f"/api/v1/finanzas/egresos/{egreso.id}/", {"monto": "1"},
                                           format="json").status_code, 400)
        self.client.post(f"/api/v1/finanzas/egresos/{egreso.id}/anular/", {"motivo": "Valor equivocado"},
                         format="json")
        self.assertFalse(calculos.obligaciones(self.tenant, self.mes)[0]["pagado"])

    def test_el_resumen_avisa_de_lo_pendiente(self):
        self.generar()
        r = self.client.get("/api/v1/finanzas/resumen/?mes=2026-10")
        self.assertEqual([(o["tipo"], o["monto"]) for o in r.data["obligaciones"]], [("iess", "144.26")])


class RetencionesTests(Base):
    def test_lo_retenido_en_liquidaciones_pagadas_se_debe_al_sri(self):
        PerfilLaboral.objects.create(tenant=self.tenant, usuario=self.doc_user, modalidad="honorarios",
                                     porcentaje=D("40"), emite_factura=True)
        self.cobro("500")
        liq = self.client.post("/api/v1/finanzas/liquidaciones/", {
            "profesional": str(self.doc_user.id), "desde": "2026-09-01", "hasta": "2026-09-30"},
            format="json").data
        self.assertEqual(calculos.obligaciones(self.tenant, self.mes), [])      # aún no se paga
        self.client.post(f"/api/v1/finanzas/liquidaciones/{liq['id']}/pagar/", {"fecha": "2026-09-30"},
                         format="json")
        sri = calculos.obligaciones(self.tenant, self.mes)[0]
        self.assertEqual((sri["tipo"], sri["monto"]), ("sri", "20.00"))
        r = self.client.post("/api/v1/finanzas/obligaciones/", {"tipo": "sri", "mes": "2026-09"}, format="json")
        self.assertEqual(Egreso.objects.get(pk=r.data["id"]).categoria.clave, "impuestos")
        # Lo pagado al SRI no se descuenta a nadie en la próxima liquidación.
        self.cobro("100", dia=date(2026, 10, 5))
        r = calculos.liquidacion(self.tenant, self.doc_user, date(2026, 10, 1), date(2026, 10, 31))
        self.assertEqual(r["descuentos"], D("0.00"))


class DecimosTests(ConEmpleada):
    def test_lo_acumulado_en_los_roles_y_su_pago(self):
        for mes in ("2026-09", "2026-10", "2026-11"):
            self.generar(mes)
        r = self.client.get("/api/v1/finanzas/decimos/?tipo=tercero&anio=2026")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data["desde"], r.data["hasta"], r.data["vence"]),
                         ("2025-12-01", "2026-11-30", "2026-12-24"))
        fila = r.data["filas"][0]
        self.assertEqual((fila["meses"], fila["monto"], fila["pagado"]), (3, "120.51", False))   # 3 × 40,17

        r = self.client.post("/api/v1/finanzas/decimos/", {"tipo": "tercero", "anio": 2026}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data["pendiente"], r.data["filas"][0]["pagado"]), ("0.00", True))
        self.assertTrue(Egreso.objects.filter(origen="decimo_tercero", profesional=self.recepcion,
                                              monto=D("120.51")).exists())
        self.assertEqual(self.client.post("/api/v1/finanzas/decimos/", {"tipo": "tercero", "anio": 2026},
                                          format="json").status_code, 400)

    def test_el_decimo_cuarto_depende_de_la_region(self):
        self.assertEqual(calculos.periodo_decimo("cuarto", 2027, "sierra"),
                         (date(2026, 8, 1), date(2027, 7, 31), date(2027, 8, 15)))
        self.assertEqual(calculos.periodo_decimo("cuarto", 2028, "costa"),
                         (date(2027, 3, 1), date(2028, 2, 29), date(2028, 3, 15)))
        self.generar()
        self.assertEqual(calculos.decimos(self.tenant, "cuarto", 2026)["filas"], [])       # Sierra: ago–jul
        self.assertEqual(calculos.decimos(self.tenant, "cuarto", 2027)["filas"][0]["monto"], "40.17")
        r = self.client.patch("/api/v1/finanzas/configuracion/", {"region": "costa"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(calculos.decimos(self.tenant, "cuarto", 2027)["filas"][0]["monto"], "40.17")
        self.assertEqual(calculos.decimos(self.tenant, "cuarto", 2026)["filas"], [])

    def test_quien_lo_cobra_cada_mes_no_acumula(self):
        self.perfil.decimo_tercero_mensual = True
        self.perfil.save()
        self.generar()
        self.assertEqual(calculos.decimos(self.tenant, "tercero", 2026)["filas"], [])


class LiquidacionAtrasadosTests(Base):
    def setUp(self):
        super().setUp()
        PerfilLaboral.objects.create(tenant=self.tenant, usuario=self.doc_user, modalidad="honorarios",
                                     porcentaje=D("50"))

    def liquidar(self, desde, hasta):
        return self.client.post("/api/v1/finanzas/liquidaciones/", {
            "profesional": str(self.doc_user.id), "desde": desde, "hasta": hasta}, format="json")

    def test_un_cobro_registrado_tarde_entra_en_la_siguiente(self):
        self.cobro("80", dia=date(2026, 8, 20))                    # antes de liquidar en Clinube: no entra
        self.cobro("100")
        self.assertEqual(self.liquidar("2026-09-01", "2026-09-30").data["base"], "100.00")
        tarde = self.cobro("60", dia=date(2026, 9, 25))           # se apuntó después de liquidar
        self.egreso("10", "laboratorio", dia=date(2026, 9, 28), profesional=self.doc_user,
                    descontar_al_profesional=True)
        self.cobro("40", dia=date(2026, 10, 3))
        r = self.liquidar("2026-10-01", "2026-10-31")
        self.assertEqual((r.data["base"], r.data["descuentos"], r.data["a_pagar"]), ("100.00", "10.00", "35.00"))   # 50 − 10 − 5 de retención
        cobro = next(c for c in r.data["detalle"]["cobros"] if c["id"] == str(tarde.id))
        self.assertTrue(cobro["atrasado"])
        # Y ya no vuelve a entrar.
        r = calculos.liquidacion(self.tenant, self.doc_user, date(2026, 11, 1), date(2026, 11, 30))
        self.assertEqual(r["base"], D("0.00"))

    def test_lo_descontado_no_se_toca_y_el_cobro_se_puede_pasar_a_otro(self):
        gasto = self.egreso("30", "laboratorio", profesional=self.doc_user, descontar_al_profesional=True)
        self.cobro("100")
        liq = self.liquidar("2026-09-01", "2026-09-30").data
        r = self.client.post(f"/api/v1/finanzas/egresos/{gasto.id}/anular/", {"motivo": "x"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn(f"N.º {liq['numero']:05d}", r.data["detail"])
        # Un cobro de otra persona sí se puede pasar a quien ya tiene liquidado ese mes.
        ajeno = self.cobro("70", profesional=self.admin)
        r = self.client.patch(f"/api/v1/finanzas/cobros/{ajeno.id}/", {"profesional": str(self.doc_user.id)},
                              format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.client.post(f"/api/v1/finanzas/liquidaciones/{liq['id']}/anular/", {}, format="json")
        self.assertEqual(self.client.post(f"/api/v1/finanzas/egresos/{gasto.id}/anular/", {"motivo": "x"},
                                          format="json").status_code, 200)


class CajaDesactualizadaTests(Base):
    def test_un_cobro_despues_del_cierre_lo_marca(self):
        hoy = timezone.localdate()
        self.cobro("50", dia=hoy)
        self.client.post("/api/v1/finanzas/caja/", {"fecha": hoy.isoformat(), "contado": "50"}, format="json")
        self.assertFalse(self.client.get(f"/api/v1/finanzas/caja/?fecha={hoy.isoformat()}").data["desactualizado"])
        self.cobro("20", dia=hoy)
        self.assertTrue(self.client.get(f"/api/v1/finanzas/caja/?fecha={hoy.isoformat()}").data["desactualizado"])


class AjustesTests(Base):
    def test_region_y_recargos(self):
        r = self.client.patch("/api/v1/finanzas/configuracion/", {"recargo_suplementarias": "400"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.client.patch("/api/v1/finanzas/configuracion/", {"region": "luna"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.client.get("/api/v1/finanzas/configuracion/")
        self.assertEqual((r.data["region"], r.data["recargo_extraordinarias"]), ("sierra", "100.00"))
