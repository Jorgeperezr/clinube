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
    }


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

def liquidacion(tenant, usuario, desde, hasta, ajustes=CERO):
    """
    Lo que le toca a un profesional por honorarios en un período:

        honorario  = % de lo cobrado a sus pacientes (o el monto fijo)
      − descuentos = gastos marcados para descontarle (laboratorio…)
      ± ajustes    = bonos o anticipos puestos a mano
      − retención  = Impuesto a la Renta, si factura a la clínica
      = a pagar
    """
    from apps.finanzas.models import ConfiguracionFinanzas, Egreso, PerfilLaboral

    perfil = PerfilLaboral.objects.filter(usuario=usuario).first() or PerfilLaboral(usuario=usuario)
    config = ConfiguracionFinanzas.de(tenant)
    ajustes = centavos(ajustes)

    pagos = cobros(tenant, desde, hasta).filter(profesional=usuario).select_related("patient")
    if perfil.base_honorarios == PerfilLaboral.BaseHonorarios.FIJO:
        base = CERO
        porcentaje = CERO
        honorario = centavos(perfil.monto_fijo)
    else:
        base = _suma(pagos, "amount")
        porcentaje = perfil.porcentaje
        honorario = pct(base, porcentaje)

    gastos = Egreso.objects.filter(
        tenant=tenant, profesional=usuario, descontar_al_profesional=True, anulado=False,
        fecha__gte=desde, fecha__lte=hasta).exclude(origen__in=("liquidacion", "rol"))
    descuentos = _suma(gastos)

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
            "cobros": [{"fecha": p.date.isoformat(), "paciente": p.patient.full_name,
                        "forma": FORMAS_COBRO.get(p.method, p.method), "monto": str(p.amount)}
                       for p in pagos.order_by("date")],
            "descuentos": [{"fecha": e.fecha.isoformat(), "concepto": e.concepto,
                            "monto": str(e.monto)} for e in gastos.order_by("fecha")],
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
        anticipos=CERO, prestamos_iess=CERO, otros_descuentos=CERO):
    """
    El rol de pagos de un mes, con el formato de siempre en Ecuador:

      INGRESOS: sueldo (proporcional a los días), horas extra, bonos y, si
      el trabajador lo pidió, décimos y fondos de reserva cada mes.
      DESCUENTOS: aporte personal al IESS, anticipos, préstamos.
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
    # Lo que aporta al IESS: sueldo, horas extra y bonos.
    aportable = sueldo + horas_extra + otros_ingresos

    decimo_tercero = centavos(aportable / 12)
    decimo_cuarto = centavos(Decimal(config.salario_basico) / 12 * dias / 30)
    con_fondos = _cumplio_un_anio(perfil.fecha_ingreso, fin)
    fondos = pct(aportable, config.fondos_reserva) if con_fondos else CERO

    ingresos = [("Sueldo" + (f" ({dias} días)" if dias < 30 else ""), sueldo)]
    if horas_extra:
        ingresos.append(("Horas extra", horas_extra))
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
    for nombre, valor in (("Anticipos", anticipos), ("Préstamos IESS", prestamos_iess),
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
    }


def _p(valor):
    return f"{Decimal(valor).normalize():f} %".replace(".", ",")
