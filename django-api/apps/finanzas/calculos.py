"""
Las cuentas, separadas de las vistas para poder comprobarlas una a una.

Todo en Decimal y redondeado a centavos «a la mitad hacia arriba», que es
como redondea un contador a mano. Un float aquí acaba, tarde o temprano,
en un rol que no cuadra por un centavo.
"""

from calendar import monthrange
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Sum

CERO = Decimal("0.00")
CIEN = Decimal("100")


def centavos(valor):
    return Decimal(valor or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def pct(base, porcentaje):
    return centavos(Decimal(base) * Decimal(porcentaje) / CIEN)


def mes_de(texto):
    """'2026-10' → (date(2026,10,1), date(2026,10,31)). Vacío = mes actual."""
    from django.utils import timezone

    if texto:
        anio, mes = (int(x) for x in str(texto).split("-")[:2])
    else:
        hoy = timezone.localdate()
        anio, mes = hoy.year, hoy.month
    return date(anio, mes, 1), date(anio, mes, monthrange(anio, mes)[1])


def _suma(qs, campo="monto"):
    return centavos(qs.aggregate(t=Sum(campo))["t"] or 0)


# ── Lo que entra y lo que sale ───────────────────────────────────────

def cobros(tenant, desde, hasta):
    from apps.billing.models import Payment

    return Payment.objects.filter(tenant=tenant, date__gte=desde, date__lte=hasta)


def egresos_pagados(tenant, desde, hasta):
    from apps.finanzas.models import Egreso

    return Egreso.objects.filter(tenant=tenant, fecha__gte=desde, fecha__lte=hasta,
                                 anulado=False, estado=Egreso.Estado.PAGADO)


FORMAS_COBRO = {"cash": "Efectivo", "transfer": "Transferencia", "card": "Tarjeta"}


def resumen(tenant, desde, hasta):
    """El estado de un mes: lo cobrado, lo gastado y lo que queda pendiente."""
    from apps.billing.models import Installment
    from apps.finanzas.models import Egreso, Liquidacion, RolPagos

    pagos = cobros(tenant, desde, hasta)
    ingresos = _suma(pagos, "amount")
    por_forma = [{"forma": FORMAS_COBRO.get(m, m), "total": str(_suma(pagos.filter(method=m), "amount"))}
                 for m in FORMAS_COBRO]

    egresos = egresos_pagados(tenant, desde, hasta)
    total_egresos = _suma(egresos)
    por_categoria = [
        {"categoria": fila["categoria__nombre"], "total": str(centavos(fila["t"]))}
        for fila in egresos.values("categoria__nombre").annotate(t=Sum("monto")).order_by("-t")
    ]

    pendientes = Installment.objects.filter(
        tenant=tenant, status__in=[Installment.Status.PENDING, Installment.Status.OVERDUE])
    por_cobrar = centavos(sum((c.balance for c in pendientes.prefetch_related("payments")), CERO))
    from django.utils import timezone

    vencido = centavos(sum((c.balance for c in pendientes.filter(due_date__lt=timezone.localdate())
                            .prefetch_related("payments")), CERO))

    cuentas = Egreso.objects.filter(tenant=tenant, anulado=False, estado=Egreso.Estado.POR_PAGAR)
    honorarios_pendientes = _suma(Liquidacion.objects.filter(
        tenant=tenant, estado=Liquidacion.Estado.BORRADOR), "a_pagar")
    roles_pendientes = _suma(RolPagos.objects.filter(
        tenant=tenant, estado=RolPagos.Estado.BORRADOR), "neto")

    return {
        "desde": desde.isoformat(), "hasta": hasta.isoformat(),
        "ingresos": str(ingresos),
        "ingresos_por_forma": por_forma,
        "cobros": pagos.count(),
        "egresos": str(total_egresos),
        "egresos_por_categoria": por_categoria,
        "utilidad": str(ingresos - total_egresos),
        "margen": (str(centavos((ingresos - total_egresos) / ingresos * CIEN)) if ingresos else None),
        "por_cobrar": str(por_cobrar),
        "por_cobrar_vencido": str(vencido),
        "por_pagar": str(_suma(cuentas)),
        "por_pagar_vencido": str(_suma(cuentas.filter(vence__lt=timezone.localdate()))),
        "honorarios_pendientes": str(honorarios_pendientes),
        "roles_pendientes": str(roles_pendientes),
        "obligaciones": obligaciones_pendientes(tenant, desde),
    }


def obligaciones_pendientes(tenant, inicio):
    """IESS y SRI sin pagar del mes anterior (vencen en este) y del mes en curso."""
    anterior = date(inicio.year - 1, 12, 1) if inicio.month == 1 else date(inicio.year, inicio.month - 1, 1)
    return [o for m in (anterior, inicio) for o in obligaciones(tenant, m) if not o["pagado"]]


def serie(tenant, hasta, meses=6):
    """Ingresos y egresos de los últimos meses, para el gráfico."""
    filas = []
    anio, mes = hasta.year, hasta.month
    for _ in range(meses):
        desde_m = date(anio, mes, 1)
        hasta_m = date(anio, mes, monthrange(anio, mes)[1])
        ing = _suma(cobros(tenant, desde_m, hasta_m), "amount")
        egr = _suma(egresos_pagados(tenant, desde_m, hasta_m))
        filas.append({"mes": f"{anio}-{mes:02d}", "ingresos": str(ing), "egresos": str(egr),
                      "utilidad": str(ing - egr)})
        mes -= 1
        if mes == 0:
            anio, mes = anio - 1, 12
    return list(reversed(filas))


# ── Caja del día ─────────────────────────────────────────────────────

def caja(tenant, dia):
    """Lo que tendría que haber en efectivo al cerrar el día."""
    from apps.finanzas.models import CierreCaja, Egreso, FormaPago

    anterior = CierreCaja.objects.filter(tenant=tenant, fecha__lt=dia).order_by("-fecha").first()
    saldo_inicial = centavos(anterior.queda_en_caja) if anterior else CERO
    pagos = cobros(tenant, dia, dia).filter(method="cash").select_related("patient")
    salidas = Egreso.objects.filter(tenant=tenant, fecha=dia, anulado=False,
                                    estado=Egreso.Estado.PAGADO, forma_pago=FormaPago.EFECTIVO)
    entra = _suma(pagos, "amount")
    sale = _suma(salidas)
    return {
        "fecha": dia.isoformat(),
        "saldo_inicial": str(saldo_inicial),
        "viene_del_cierre": anterior.fecha.isoformat() if anterior else None,
        "cobros_efectivo": str(entra),
        "egresos_efectivo": str(sale),
        "esperado": str(saldo_inicial + entra - sale),
        "otros_cobros": str(_suma(cobros(tenant, dia, dia).exclude(method="cash"), "amount")),
        "movimientos": (
            [{"tipo": "cobro", "detalle": p.patient.full_name, "monto": str(p.amount)} for p in pagos]
            + [{"tipo": "egreso", "detalle": e.concepto, "monto": str(e.monto)} for e in salidas]
        ),
    }


# ── Honorarios ───────────────────────────────────────────────────────

def ya_liquidado(tenant, usuario):
    """
    Lo que ya entró en alguna liquidación vigente del profesional: los
    ids de cobros y de descuentos, y desde cuándo se le liquida en Clinube.
    Las liquidaciones antiguas sin ids se cubren por su rango de fechas.
    """
    from apps.finanzas.models import Liquidacion

    cobros_ids, descuentos_ids, rangos, inicio = set(), set(), [], None
    for liq in Liquidacion.objects.filter(tenant=tenant, profesional=usuario).exclude(
            estado=Liquidacion.Estado.ANULADA):
        d = liq.detalle or {}
        if any("id" in c for c in d.get("cobros", [])) or "cobros_ids" in d:
            cobros_ids.update(d.get("cobros_ids") or [c["id"] for c in d.get("cobros", []) if "id" in c])
            descuentos_ids.update(d.get("descuentos_ids") or [x["id"] for x in d.get("descuentos", []) if "id" in x])
        else:
            rangos.append((liq.desde, liq.hasta))
        inicio = liq.desde if inicio is None or liq.desde < inicio else inicio
    return cobros_ids, descuentos_ids, rangos, inicio


def _fuera(fecha, rangos):
    return not any(a <= fecha <= b for a, b in rangos)


def liquidacion(tenant, usuario, desde, hasta, ajustes=CERO):
    """
    Lo que le toca a un profesional por honorarios en un período:

        honorario  = % de lo cobrado a sus pacientes (o el monto fijo)
      − descuentos = gastos marcados para descontarle (laboratorio…)
      ± ajustes    = bonos o anticipos puestos a mano
      − retención  = Impuesto a la Renta, si factura a la clínica
      = a pagar

    Entran los cobros y descuentos del período y, además, los de fechas
    anteriores que no entraron en ninguna liquidación (un cobro registrado
    tarde con la fecha de un mes ya liquidado no se pierde).
    """
    from apps.billing.models import Payment
    from apps.finanzas.models import ORIGENES_CALCULADOS, ConfiguracionFinanzas, Egreso, PerfilLaboral

    perfil = PerfilLaboral.objects.filter(usuario=usuario).first() or PerfilLaboral(usuario=usuario)
    config = ConfiguracionFinanzas.de(tenant)
    ajustes = centavos(ajustes)
    hechos_c, hechos_d, rangos, inicio = ya_liquidado(tenant, usuario)

    def pendientes(qs, campo, hechos):
        filas = []
        for x in qs:
            f = getattr(x, campo)
            if str(x.id) in hechos or not _fuera(f, rangos):
                continue
            # Antes del período, solo lo que ya caía bajo liquidaciones de Clinube.
            if f < desde and (inicio is None or f < inicio):
                continue
            filas.append(x)
        return filas

    piso = min(desde, inicio) if inicio else desde
    pagos = pendientes(Payment.objects.filter(tenant=tenant, profesional=usuario, date__gte=piso, date__lte=hasta)
                       .select_related("patient").order_by("date"), "date", hechos_c)
    gastos = pendientes(Egreso.objects.filter(
        tenant=tenant, profesional=usuario, descontar_al_profesional=True, anulado=False,
        fecha__gte=piso, fecha__lte=hasta).exclude(origen__in=ORIGENES_CALCULADOS).order_by("fecha"),
        "fecha", hechos_d)

    if perfil.base_honorarios == PerfilLaboral.BaseHonorarios.FIJO:
        base = CERO
        porcentaje = CERO
        honorario = centavos(perfil.monto_fijo)
    else:
        base = centavos(sum((p.amount for p in pagos), CERO))
        porcentaje = perfil.porcentaje
        honorario = pct(base, porcentaje)
    descuentos = centavos(sum((e.monto for e in gastos), CERO))

    # Se retiene sobre lo que factura: su honorario y los bonos. Un
    # anticipo ya pagado no cambia lo que factura.
    retencion_pct = config.retencion_honorarios if perfil.emite_factura else CERO
    base_retencion = honorario + max(ajustes, CERO)
    retencion = pct(base_retencion, retencion_pct)
    a_pagar = centavos(honorario - descuentos + ajustes - retencion)

    return {
        "base": base, "porcentaje": porcentaje, "honorario": honorario,
        "descuentos": descuentos, "ajustes": ajustes,
        "retencion_porcentaje": retencion_pct, "retencion": retencion, "a_pagar": a_pagar,
        "detalle": {
            "modalidad": perfil.base_honorarios,
            "cobros": [{"id": str(p.id), "fecha": p.date.isoformat(), "paciente": p.patient.full_name,
                        "forma": FORMAS_COBRO.get(p.method, p.method), "monto": str(p.amount),
                        "atrasado": p.date < desde} for p in pagos],
            "descuentos": [{"id": str(e.id), "fecha": e.fecha.isoformat(), "concepto": e.concepto,
                            "monto": str(e.monto), "atrasado": e.fecha < desde} for e in gastos],
            "cobros_ids": [str(p.id) for p in pagos],
            "descuentos_ids": [str(e.id) for e in gastos],
        },
    }


# ── Rol de pagos ─────────────────────────────────────────────────────

def _cumplio_un_anio(fecha_ingreso, fin_mes):
    if not fecha_ingreso:
        return False
    try:
        aniversario = fecha_ingreso.replace(year=fecha_ingreso.year + 1)
    except ValueError:            # 29 de febrero
        aniversario = fecha_ingreso.replace(year=fecha_ingreso.year + 1, day=28)
    return aniversario <= fin_mes


def rol(tenant, empleado, mes, dias_trabajados=30, horas_extra=CERO, otros_ingresos=CERO,
        anticipos=CERO, prestamos_iess=CERO, otros_descuentos=CERO,
        horas_suplementarias=CERO, horas_extraordinarias=CERO):
    """
    El rol de pagos de un mes, con el formato de siempre en Ecuador:

      INGRESOS: sueldo (proporcional a los días), horas suplementarias
      (+50 %) y extraordinarias (+100 %) sobre el valor hora (sueldo/240),
      bonos y, si el trabajador lo pidió, décimos y fondos de reserva.
      DESCUENTOS: aporte personal al IESS, anticipos (los apuntados como
      egreso para descontárselos y los puestos a mano), préstamos.
      NETO A RECIBIR = ingresos − descuentos.

    Y aparte, lo que le cuesta a la clínica: aporte patronal y lo que se
    provisiona (décimos y fondos que se pagan después).
    """
    from apps.finanzas.models import ConfiguracionFinanzas, PerfilLaboral

    config = ConfiguracionFinanzas.de(tenant)
    perfil = PerfilLaboral.objects.filter(usuario=empleado).first() or PerfilLaboral(usuario=empleado)
    inicio, fin = mes_de(mes.strftime("%Y-%m") if hasattr(mes, "strftime") else mes)
    dias = max(0, min(30, int(dias_trabajados)))

    sueldo = centavos(Decimal(perfil.sueldo) * dias / 30)
    horas_extra, otros_ingresos = centavos(horas_extra), centavos(otros_ingresos)
    # Valor hora: sueldo mensual / 240 (30 días de 8 horas).
    valor_hora = Decimal(perfil.sueldo) / 240
    h50, h100 = Decimal(horas_suplementarias or 0), Decimal(horas_extraordinarias or 0)
    suplementarias = centavos(valor_hora * h50 * (CIEN + Decimal(config.recargo_suplementarias)) / CIEN)
    extraordinarias = centavos(valor_hora * h100 * (CIEN + Decimal(config.recargo_extraordinarias)) / CIEN)
    # Lo que aporta al IESS: sueldo, horas extra y bonos.
    aportable = sueldo + suplementarias + extraordinarias + horas_extra + otros_ingresos

    decimo_tercero = centavos(aportable / 12)
    decimo_cuarto = centavos(Decimal(config.salario_basico) / 12 * dias / 30)
    con_fondos = _cumplio_un_anio(perfil.fecha_ingreso, fin)
    fondos = pct(aportable, config.fondos_reserva) if con_fondos else CERO

    ingresos = [("Sueldo" + (f" ({dias} días)" if dias < 30 else ""), sueldo)]
    if suplementarias:
        ingresos.append((f"Horas suplementarias ({_n(h50)} h al {_p(config.recargo_suplementarias)})",
                         suplementarias))
    if extraordinarias:
        ingresos.append((f"Horas extraordinarias ({_n(h100)} h al {_p(config.recargo_extraordinarias)})",
                         extraordinarias))
    if horas_extra:
        ingresos.append(("Otras horas extra", horas_extra))
    if otros_ingresos:
        ingresos.append(("Bonos y comisiones", otros_ingresos))
    provisiones = []
    for nombre, valor, mensual in (
            ("Décimo tercer sueldo", decimo_tercero, perfil.decimo_tercero_mensual),
            ("Décimo cuarto sueldo", decimo_cuarto, perfil.decimo_cuarto_mensual),
            ("Fondos de reserva", fondos, perfil.fondos_reserva_mensual)):
        if not valor:
            continue
        (ingresos if mensual else provisiones).append((nombre, valor))
    vacaciones = centavos(aportable / 24)
    provisiones.append(("Vacaciones", vacaciones))

    aporte_personal = pct(aportable, config.aporte_personal_iess)
    descuentos = [("Aporte personal IESS " + _p(config.aporte_personal_iess), aporte_personal)]
    entregados = anticipos_entregados(tenant, empleado, inicio, fin)
    if entregados:
        descuentos.append(("Anticipos entregados en el mes", entregados))
    for nombre, valor in (("Otros anticipos", anticipos), ("Préstamos IESS", prestamos_iess),
                          ("Otros descuentos", otros_descuentos)):
        if centavos(valor):
            descuentos.append((nombre, centavos(valor)))

    total_ingresos = centavos(sum((v for _, v in ingresos), CERO))
    total_descuentos = centavos(sum((v for _, v in descuentos), CERO))
    neto = total_ingresos - total_descuentos

    patronal_pct = Decimal(config.aporte_patronal_iess) + Decimal(config.aporte_iece_secap)
    aporte_patronal = pct(aportable, patronal_pct)
    total_provisiones = centavos(sum((v for _, v in provisiones), CERO))
    costo = total_ingresos + aporte_patronal + total_provisiones

    def filas(lista):
        return [{"concepto": n, "valor": str(v)} for n, v in lista]

    return {
        "mes": inicio.strftime("%Y-%m"),
        "dias_trabajados": dias,
        "ingresos": filas(ingresos),
        "descuentos": filas(descuentos),
        "total_ingresos": str(total_ingresos),
        "total_descuentos": str(total_descuentos),
        "neto": str(neto),
        "aporte_patronal": str(aporte_patronal),
        "aporte_patronal_porcentaje": str(patronal_pct),
        "provisiones": filas(provisiones),
        "total_provisiones": str(total_provisiones),
        "costo_empleador": str(costo),
        "fondos_reserva_desde": None if con_fondos else "Desde el segundo año de trabajo",
        # Lo que se le debe al IESS por este rol (planilla del mes):
        "iess": {
            "aporte_personal": str(aporte_personal),
            "aporte_patronal": str(aporte_patronal),
            "fondos_reserva": str(fondos if not perfil.fondos_reserva_mensual else CERO),
            "prestamos": str(centavos(prestamos_iess)),
        },
        # Lo que se acumula para pagarle después (si no se mensualiza):
        "acumula": {
            "decimo_tercero": str(CERO if perfil.decimo_tercero_mensual else decimo_tercero),
            "decimo_cuarto": str(CERO if perfil.decimo_cuarto_mensual else decimo_cuarto),
        },
    }


def anticipos_entregados(tenant, empleado, desde, hasta):
    """Egresos del mes marcados para descontárselos (anticipos, préstamos de la clínica)."""
    from apps.finanzas.models import ORIGENES_CALCULADOS, Egreso

    return _suma(Egreso.objects.filter(
        tenant=tenant, profesional=empleado, descontar_al_profesional=True, anulado=False,
        fecha__gte=desde, fecha__lte=hasta).exclude(origen__in=ORIGENES_CALCULADOS))


def _n(valor):
    return f"{Decimal(valor).normalize():f}".replace(".", ",")


def _p(valor):
    return f"{Decimal(valor).normalize():f} %".replace(".", ",")


# ── Obligaciones: lo que se paga a terceros ──────────────────────────

def _siguiente_mes(inicio, dia):
    anio, mes = (inicio.year + 1, 1) if inicio.month == 12 else (inicio.year, inicio.month + 1)
    return date(anio, mes, min(dia, monthrange(anio, mes)[1]))


def _de_calculo(calculo, grupo, clave, lista, prefijo):
    """Valor del cálculo de un rol; los guardados antes de tener `grupo` se leen de la lista."""
    if grupo in calculo:
        return Decimal(calculo[grupo].get(clave) or 0)
    return sum((Decimal(f["valor"]) for f in calculo.get(lista, []) if f["concepto"].startswith(prefijo)),
               CERO)


def _pago_registrado(tenant, origen, periodo, profesional=None):
    from apps.finanzas.models import Egreso

    qs = Egreso.objects.filter(tenant=tenant, origen=origen, periodo=periodo, anulado=False)
    if profesional is not None:
        qs = qs.filter(profesional=profesional)
    return qs.first()


def obligaciones(tenant, inicio):
    """
    Lo que la clínica debe pagar por el mes que empieza en `inicio`:

      · Planilla del IESS: aporte personal (que se descontó en el rol) +
        aporte patronal + fondos de reserva no mensualizados + préstamos
        descontados. Vence el 15 del mes siguiente.
      · Retenciones al SRI: lo retenido a los profesionales en las
        liquidaciones pagadas ese mes (formulario 103). Vence el mes
        siguiente, el día que toque por el noveno dígito del RUC.
    """
    from apps.finanzas.models import Liquidacion, RolPagos

    fin = mes_de(inicio.strftime("%Y-%m"))[1]
    resultado = []

    roles = RolPagos.objects.filter(tenant=tenant, mes=inicio).exclude(
        estado=RolPagos.Estado.ANULADO).select_related("empleado")
    personal = patronal = fondos = prestamos = CERO
    for r in roles:
        c = r.calculo or {}
        personal += _de_calculo(c, "iess", "aporte_personal", "descuentos", "Aporte personal")
        patronal += Decimal(c.get("aporte_patronal") or 0)
        fondos += _de_calculo(c, "iess", "fondos_reserva", "provisiones", "Fondos de reserva")
        prestamos += _de_calculo(c, "iess", "prestamos", "descuentos", "Préstamos IESS")
    total = centavos(personal + patronal + fondos + prestamos)
    if total:
        resultado.append(_obligacion(tenant, "iess", "Planilla del IESS", inicio, total,
                                     _siguiente_mes(inicio, 15), [
                                         ("Aporte personal (descontado en los roles)", personal),
                                         ("Aporte patronal e IECE/SECAP", patronal),
                                         ("Fondos de reserva no mensualizados", fondos),
                                         ("Préstamos IESS descontados", prestamos),
                                     ], f"{roles.count()} rol{'es' if roles.count() != 1 else ''}"))

    liqs = Liquidacion.objects.filter(tenant=tenant, estado=Liquidacion.Estado.PAGADA,
                                      egreso__fecha__gte=inicio, egreso__fecha__lte=fin, retencion__gt=0) \
        .select_related("profesional")
    retenido = centavos(sum((q.retencion for q in liqs), CERO))
    if retenido:
        resultado.append(_obligacion(tenant, "sri", "Retenciones en la fuente al SRI", inicio, retenido,
                                     _siguiente_mes(inicio, 28),
                                     [(f"{q.profesional.full_name} — liquidación N.º {q.numero:05d}", q.retencion)
                                      for q in liqs],
                                     "Formulario 103; la fecha exacta depende del noveno dígito del RUC"))
    return resultado


def _obligacion(tenant, tipo, nombre, inicio, monto, vence, detalle, nota):
    pago = _pago_registrado(tenant, tipo, inicio)
    return {
        "tipo": tipo, "nombre": nombre, "periodo": inicio.strftime("%Y-%m"), "monto": str(monto),
        "vence": vence.isoformat(), "nota": nota,
        "detalle": [{"concepto": n, "valor": str(centavos(v))} for n, v in detalle if centavos(v)],
        "pagado": pago is not None, "egreso": str(pago.id) if pago else None,
        "fecha_pago": pago.fecha.isoformat() if pago else None,
        "diferencia": str(centavos(monto - pago.monto)) if pago else None,
    }


# ── Décimos acumulados ───────────────────────────────────────────────

def periodo_decimo(tipo, anio, region="sierra"):
    """(desde, hasta, vence) del décimo tercero o cuarto que se paga en `anio`."""
    if tipo == "tercero":
        return date(anio - 1, 12, 1), date(anio, 11, 30), date(anio, 12, 24)
    if region == "costa":
        return date(anio - 1, 3, 1), date(anio, 2, monthrange(anio, 2)[1]), date(anio, 3, 15)
    return date(anio - 1, 8, 1), date(anio, 7, 31), date(anio, 8, 15)


def decimos(tenant, tipo, anio):
    """
    Lo acumulado de un décimo para cada persona que no lo cobra cada mes,
    sumando lo provisionado en sus roles del período legal.
    """
    from apps.finanzas.models import ConfiguracionFinanzas, RolPagos

    region = ConfiguracionFinanzas.de(tenant).region
    desde, hasta, vence = periodo_decimo(tipo, anio, region)
    nombre = "Décimo tercer sueldo" if tipo == "tercero" else "Décimo cuarto sueldo"
    por_persona = {}
    for r in RolPagos.objects.filter(tenant=tenant, mes__gte=desde, mes__lte=hasta).exclude(
            estado=RolPagos.Estado.ANULADO).select_related("empleado"):
        valor = _de_calculo(r.calculo or {}, "acumula", f"decimo_{tipo}", "provisiones", nombre)
        if not valor:
            continue
        fila = por_persona.setdefault(r.empleado_id, {"empleado": r.empleado, "meses": 0, "monto": CERO})
        fila["meses"] += 1
        fila["monto"] += valor
    filas = []
    periodo = date(anio, 1, 1)
    for f in sorted(por_persona.values(), key=lambda x: x["empleado"].full_name):
        pago = _pago_registrado(tenant, f"decimo_{tipo}", periodo, f["empleado"])
        filas.append({"empleado": str(f["empleado"].id), "nombre": f["empleado"].full_name,
                      "meses": f["meses"], "monto": str(centavos(f["monto"])),
                      "pagado": pago is not None, "egreso": str(pago.id) if pago else None,
                      "fecha_pago": pago.fecha.isoformat() if pago else None})
    total = centavos(sum((Decimal(f["monto"]) for f in filas), CERO))
    pendiente = centavos(sum((Decimal(f["monto"]) for f in filas if not f["pagado"]), CERO))
    return {"tipo": tipo, "nombre": nombre, "anio": anio, "region": region,
            "desde": desde.isoformat(), "hasta": hasta.isoformat(), "vence": vence.isoformat(),
            "filas": filas, "total": str(total), "pendiente": str(pendiente)}
