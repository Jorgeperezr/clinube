"""
Los papeles de finanzas: comprobante de cobro, liquidación de honorarios
y rol de pagos. Con el membrete, los colores y el pie de cada clínica
(apps.common.document_style), como el resto de sus documentos.

El comprobante de cobro NO es una factura: lo dice en el propio papel.
La factura válida en Ecuador es la electrónica del SRI, y la clínica la
emite con su facturador. Esto es la constancia de que se pagó.
"""

import io
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle

from apps.common.document_style import clinic_snapshot, fecha_documento, get_document_style


def dinero(valor):
    """$1.234,56 — como se escribe en Ecuador."""
    v = Decimal(valor or 0).quantize(Decimal("0.01"))
    entero, dec = f"{abs(v):,.2f}".split(".")
    return f"{'-' if v < 0 else ''}${entero.replace(',', '.')},{dec}"


_UNIDADES = ["", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez",
             "once", "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho",
             "diecinueve", "veinte", "veintiuno", "veintidós", "veintitrés", "veinticuatro",
             "veinticinco", "veintiséis", "veintisiete", "veintiocho", "veintinueve"]
_DECENAS = ["", "", "", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa"]
_CENTENAS = ["", "ciento", "doscientos", "trescientos", "cuatrocientos", "quinientos", "seiscientos",
             "setecientos", "ochocientos", "novecientos"]


def _hasta_mil(n):
    if n == 0:
        return ""
    if n == 100:
        return "cien"
    c, resto = divmod(n, 100)
    partes = [_CENTENAS[c]] if c else []
    if resto < 30:
        partes.append(_UNIDADES[resto])
    else:
        d, u = divmod(resto, 10)
        partes.append(_DECENAS[d] + (f" y {_UNIDADES[u]}" if u else ""))
    return " ".join(p for p in partes if p)


def _apocope(texto):
    """«uno» → «un» y «veintiuno» → «veintiún» delante de «mil» o de «dólares»."""
    if texto.endswith("veintiuno"):
        return texto[:-len("veintiuno")] + "veintiún"
    if texto == "uno" or texto.endswith(" uno"):
        return texto[:-3] + "un"
    return texto


def en_letras(valor):
    """
    «Ciento veintiún con 50/100 dólares»: la cantidad en letras que llevan
    los recibos de aquí. Hasta 999.999,99, de sobra para una clínica.
    """
    v = Decimal(valor or 0).quantize(Decimal("0.01"))
    entero = int(abs(v))
    cent = int((abs(v) - entero) * 100)
    miles, unidades = divmod(entero, 1000)
    partes = []
    if miles:
        partes.append("mil" if miles == 1 else f"{_apocope(_hasta_mil(miles))} mil")
    if unidades:
        partes.append(_apocope(_hasta_mil(unidades)))
    texto = " ".join(partes) or "cero"
    return f"{texto[0].upper()}{texto[1:]} con {cent:02d}/100 dólares"


def _doc(tenant, titulo, meta, cuerpo, tamano=None):
    style = get_document_style(tenant)
    if tamano:
        style = style.for_page(tamano)
    clinic = clinic_snapshot(tenant)
    buf = io.BytesIO()
    doc = style.platypus_doc(buf, title=titulo)
    historia = style.header_flowables(clinic=clinic) + style.title_flowables(titulo, meta=meta)
    historia += cuerpo(style)
    pie = style.page_furniture(clinic=clinic)
    doc.build(historia, onFirstPage=pie, onLaterPages=pie)
    return buf.getvalue()


def _tabla(style, encabezado, filas, anchos, totales=None, alinear_derecha=(-1,)):
    datos = [encabezado] + filas + ([totales] if totales else [])
    t = Table(datos, colWidths=[style.content_width * a for a in anchos], repeatRows=1)
    cmds = list(style.table_style()._cmds)
    for col in alinear_derecha:
        cmds.append(("ALIGN", (col, 0), (col, -1), "RIGHT"))
    if totales:
        cmds += [("FONTNAME", (0, -1), (-1, -1), style.font_bold),
                 ("LINEABOVE", (0, -1), (-1, -1), 1, style.primary)]
    t.setStyle(TableStyle(cmds))
    return t


def _firmas(style, izquierda, derecha):
    # Línea dibujada y no «______»: en A5 el subrayado no cabía y saltaba
    # de renglón, dejando un guion suelto bajo cada firma.
    ss = style.paragraph_styles()
    ancho = style.content_width
    t = Table([[Paragraph(izquierda, ss["DocSmall"]), "", Paragraph(derecha, ss["DocSmall"])]],
              colWidths=[ancho * 0.42, ancho * 0.16, ancho * 0.42])
    t.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LINEABOVE", (0, 0), (0, 0), 0.6, colors.HexColor("#555555")),
        ("LINEABOVE", (2, 0), (2, 0), 0.6, colors.HexColor("#555555")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    return KeepTogether([Spacer(1, 22 * mm), t])


# ── Comprobante de cobro ─────────────────────────────────────────────

def comprobante_cobro(tenant, pago, numero):
    paciente = pago.patient

    def cuerpo(style):
        ss = style.paragraph_styles()
        partes = [style.fields_table([
            [("Recibí de", paciente.full_name, 2), ("Cédula / RUC", paciente.national_id)],
            [("Fecha", fecha_documento(pago.date)), ("Forma de pago", pago.get_method_display()),
             ("Atendido por", pago.profesional.full_name if pago.profesional_id else "")],
        ], columnas=3), Spacer(1, 4 * mm)]
        concepto = "Abono a su plan de pago" + (f" (cuota {pago.installment.number})"
                                               if pago.installment_id else "")
        if not pago.installment_id:
            concepto = "Pago por servicios odontológicos"
        partes.append(_tabla(style, ["Concepto", "Valor"], [[concepto, dinero(pago.amount)]],
                             [0.75, 0.25], totales=["TOTAL RECIBIDO", dinero(pago.amount)]))
        partes += [Spacer(1, 3 * mm),
                   Paragraph(f"<b>Son:</b> {en_letras(pago.amount)}", ss["DocBody"]),
                   _firmas(style, "Recibido por", "Paciente"),
                   Spacer(1, 4 * mm),
                   Paragraph("Este comprobante acredita el pago recibido. No es una factura: la "
                             "factura electrónica la emite la clínica por el sistema del SRI.",
                             ss["DocSmall"])]
        return partes

    return _doc(tenant, "Comprobante de cobro", [("N.º", f"{numero:06d}")], cuerpo, tamano="A5")


# ── Liquidación de honorarios ────────────────────────────────────────

def liquidacion(tenant, liq):
    perfil = getattr(liq.profesional, "perfil_laboral", None)
    detalle = liq.detalle or {}

    def cuerpo(style):
        ss = style.paragraph_styles()
        partes = [style.fields_table([
            [("Profesional", liq.profesional.full_name, 2), ("Cédula / RUC", getattr(perfil, "cedula", ""))],
            [("Período", f"{fecha_documento(liq.desde)} al {fecha_documento(liq.hasta)}", 2),
             ("Estado", liq.get_estado_display())],
        ], columnas=3)]

        cobros = detalle.get("cobros") or []
        if cobros:
            partes += [style.section_flowable("Cobros a sus pacientes", 1),
                       _tabla(style, ["Fecha", "Paciente", "Forma", "Monto"],
                              [[fecha_documento(c["fecha"]) + (" *" if c.get("atrasado") else ""),
                                c["paciente"], c["forma"], dinero(c["monto"])] for c in cobros],
                              [0.16, 0.48, 0.16, 0.20], totales=["", "Total cobrado", "", dinero(liq.base)])]
        descuentos = detalle.get("descuentos") or []
        if descuentos:
            partes += [style.section_flowable("Descuentos", 2 if cobros else 1),
                       _tabla(style, ["Fecha", "Concepto", "Monto"],
                              [[fecha_documento(d["fecha"]) + (" *" if d.get("atrasado") else ""),
                                d["concepto"], dinero(d["monto"])] for d in descuentos], [0.16, 0.64, 0.20])]
        if any(x.get("atrasado") for x in cobros + descuentos):
            partes.append(Paragraph("* De antes del período: se registró después de liquidarlo.",
                                    ss["DocSmall"]))

        if detalle.get("modalidad") == "fijo":
            linea_honorario = "Honorario fijo del período"
        else:
            linea_honorario = f"Honorario ({str(liq.porcentaje).replace('.', ',')} % de {dinero(liq.base)})"
        filas = [[linea_honorario, dinero(liq.honorario)]]
        if liq.descuentos:
            filas.append(["(−) Descuentos", dinero(-liq.descuentos)])
        if liq.ajustes:
            filas.append(["(±) Ajustes" + (f": {liq.nota}" if liq.nota else ""), dinero(liq.ajustes)])
        if liq.retencion:
            filas.append([f"(−) Retención en la fuente {str(liq.retencion_porcentaje).replace('.', ',')} %",
                          dinero(-liq.retencion)])
        partes += [style.section_flowable("Resumen"),
                   _tabla(style, ["Concepto", "Valor"], filas, [0.75, 0.25],
                          totales=["VALOR A PAGAR", dinero(liq.a_pagar)]),
                   Spacer(1, 3 * mm),
                   Paragraph(f"<b>Son:</b> {en_letras(liq.a_pagar)}", ss["DocBody"])]
        if liq.retencion:
            partes.append(Paragraph(
                "La retención se declara al SRI y se entrega al profesional su comprobante de "
                "retención electrónico.", ss["DocSmall"]))
        partes.append(_firmas(style, "Elaborado por", "Recibí conforme"))
        return partes

    return _doc(tenant, "Liquidación de honorarios", [("N.º", f"{liq.numero:05d}")], cuerpo)


# ── Rol de pagos ─────────────────────────────────────────────────────

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]


def rol_pagos(tenant, rol):
    perfil = getattr(rol.empleado, "perfil_laboral", None)
    c = rol.calculo or {}
    mes = f"{MESES[rol.mes.month - 1].capitalize()} {rol.mes.year}"

    def cuerpo(style):
        ss = style.paragraph_styles()
        partes = [style.fields_table([
            [("Trabajador", rol.empleado.full_name, 2), ("Cédula", getattr(perfil, "cedula", ""))],
            [("Cargo", getattr(perfil, "cargo", "")), ("Mes", mes), ("Días trabajados", c.get("dias_trabajados"))],
        ], columnas=3), Spacer(1, 4 * mm)]

        ingresos = c.get("ingresos") or []
        descuentos = c.get("descuentos") or []
        alto = max(len(ingresos), len(descuentos))
        filas = []
        for i in range(alto):
            a = ingresos[i] if i < len(ingresos) else None
            b = descuentos[i] if i < len(descuentos) else None
            filas.append([a["concepto"] if a else "", dinero(a["valor"]) if a else "",
                          b["concepto"] if b else "", dinero(b["valor"]) if b else ""])
        partes.append(_tabla(style, ["Ingresos", "Valor", "Descuentos", "Valor"], filas,
                             [0.32, 0.18, 0.32, 0.18],
                             totales=["Total ingresos", dinero(c.get("total_ingresos")),
                                      "Total descuentos", dinero(c.get("total_descuentos"))],
                             alinear_derecha=(1, 3)))
        neto = Table([["NETO A RECIBIR", dinero(c.get("neto"))]],
                     colWidths=[style.content_width * 0.82, style.content_width * 0.18])
        neto.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), style.primary), ("TEXTCOLOR", (0, 0), (-1, -1), "#ffffff"),
            ("FONTNAME", (0, 0), (-1, -1), style.font_bold), ("FONTSIZE", (0, 0), (-1, -1), style.size + 1),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"), ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ]))
        partes += [Spacer(1, 3 * mm), neto, Spacer(1, 2 * mm),
                   Paragraph(f"<b>Son:</b> {en_letras(c.get('neto'))}", ss["DocBody"])]

        provisiones = c.get("provisiones") or []
        partes += [style.section_flowable("Lo que aporta y provisiona la clínica"),
                   _tabla(style, ["Concepto", "Valor"],
                          [[f"Aporte patronal IESS ({str(c.get('aporte_patronal_porcentaje', '')).replace('.', ',')} %)",
                            dinero(c.get("aporte_patronal"))]]
                          + [[p["concepto"] + " (provisión)", dinero(p["valor"])] for p in provisiones],
                          [0.75, 0.25], totales=["Costo total para la clínica", dinero(c.get("costo_empleador"))]),
                   Paragraph("Las provisiones no se descuentan al trabajador: se le pagan en su fecha "
                             "(décimos), al IESS (fondos de reserva) o al salir de vacaciones.",
                             ss["DocSmall"]),
                   _firmas(style, "Empleador", "Recibí conforme — " + rol.empleado.full_name)]
        return partes

    return _doc(tenant, "Rol de pagos", [("Mes", mes)], cuerpo)
