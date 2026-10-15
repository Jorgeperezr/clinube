"""
Certificado de atención odontológica.

El papel que el paciente lleva al trabajo, al colegio o al seguro para
justificar que estuvo en consulta. Sigue la forma habitual en Ecuador:
quien suscribe (con su registro profesional) CERTIFICA que el paciente,
con su cédula, fue atendido tal día de tal a tal hora; si hace falta, el
diagnóstico (CIE-10), lo que se hizo y los días de reposo; la fórmula
de cierre, el lugar y la fecha, y la firma y sello.

Usa el membrete, los colores y el pie de la clínica como el resto de
documentos (apps/common/document_style.py).
"""

import base64
import io
from datetime import timedelta

from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, KeepTogether, Paragraph, Spacer, Table, TableStyle

from apps.common.document_style import _esc

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]


def fecha_larga(d, con_dia=True):
    """date(2026, 10, 14) → «martes 14 de octubre de 2026»."""
    texto = f"{d.day} de {MESES[d.month - 1]} de {d.year}"
    return f"{DIAS[d.weekday()]} {texto}" if con_dia else texto


def _firma(signature_b64, ancho_mm=45, alto_mm=18):
    if not signature_b64:
        return None
    try:
        raw = signature_b64.split(",", 1)[1] if "," in signature_b64 else signature_b64
        return Image(io.BytesIO(base64.b64decode(raw)), width=ancho_mm * mm, height=alto_mm * mm,
                     kind="proportional")
    except Exception:
        return None


def build_certificado_pdf(clinic, professional, patient, atencion, style, lugar=""):
    """
    professional: {full_name, specialty, license_number, signature_b64}
    patient:      {full_name, national_id, sex ('H'|'M'|'')}
    atencion:     {fecha, hora_inicio, hora_fin, diagnostico, procedimiento,
                   reposo_dias, observaciones, numero}
    """
    buf = io.BytesIO()
    doc = style.platypus_doc(buf, title="Certificado de atención odontológica")
    ss = style.paragraph_styles()
    cuerpo = ParagraphStyle("cert", parent=ss["DocBody"], fontSize=style.size + 1.5,
                            leading=(style.size + 1.5) * 1.65, alignment=TA_JUSTIFY, spaceAfter=3 * mm)
    rotulo = ParagraphStyle("rot", parent=cuerpo, alignment=0, spaceAfter=1.5 * mm)

    fecha = atencion["fecha"]
    titulo_paciente = {"M": "la paciente", "H": "el paciente"}.get(patient.get("sex"), "el/la paciente")
    registro = professional.get("license_number")
    especialidad = professional.get("specialty") or "Odontología"

    historia = style.header_flowables(clinic=clinic)
    historia += style.title_flowables("Certificado de atención odontológica",
                                      meta=[("N.º", atencion.get("numero")), ("Fecha", fecha.strftime("%d/%m/%Y"))])
    historia.append(Spacer(1, 4 * mm))

    quien = f"Quien suscribe, <b>{_esc(professional['full_name'])}</b>, profesional de {_esc(especialidad.lower())}"
    if registro:
        quien += f", con registro profesional {_esc(registro)}"
    historia.append(Paragraph(f"{quien}, <b>CERTIFICA</b>:", cuerpo))

    horario = ""
    if atencion.get("hora_inicio"):
        horario = f", de {atencion['hora_inicio'].strftime('%H:%M')}"
        if atencion.get("hora_fin"):
            horario += f" a {atencion['hora_fin'].strftime('%H:%M')}"
        horario += " horas"
    nombre_clinica = clinic.get("name") or "esta clínica"
    historia.append(Paragraph(
        f"Que {titulo_paciente} <b>{_esc(patient['full_name'].upper())}</b>, con documento de identidad "
        f"N.º <b>{_esc(patient['national_id'])}</b>, acudió a consulta odontológica en "
        f"{_esc(nombre_clinica)} el día {fecha_larga(fecha)}{horario}.", cuerpo))

    if atencion.get("diagnostico"):
        historia.append(Paragraph(f"<b>Diagnóstico:</b> {_esc(atencion['diagnostico'])}", rotulo))
    if atencion.get("procedimiento"):
        historia.append(Paragraph(f"<b>Procedimiento realizado:</b> {_esc(atencion['procedimiento'])}", rotulo))
    dias = int(atencion.get("reposo_dias") or 0)
    if dias:
        hasta = fecha + timedelta(days=dias - 1)
        texto = (f"el día {fecha_larga(fecha, False)}" if dias == 1 else
                 f"desde el {fecha_larga(fecha, False)} hasta el {fecha_larga(hasta, False)}, inclusive")
        historia.append(Paragraph(
            f"<b>Reposo:</b> se indica reposo de {dias} día{'s' if dias > 1 else ''}, {texto}.", rotulo))
    if atencion.get("observaciones"):
        historia.append(Paragraph(f"<b>Observaciones:</b> {_esc(atencion['observaciones'])}", rotulo))

    historia.append(Spacer(1, 3 * mm))
    historia.append(Paragraph(
        "Es todo cuanto puedo certificar en honor a la verdad. El interesado puede hacer uso del "
        "presente certificado como estime conveniente.", cuerpo))
    historia.append(Paragraph(f"{_esc(lugar) + ', ' if lugar else ''}{fecha_larga(fecha, False)}.", cuerpo))

    # Firma y sello, centrados, con la firma dibujada si la tiene.
    firma = _firma(professional.get("signature_b64"))
    pie_firma = ParagraphStyle("pf", parent=ss["DocSmall"], alignment=1, fontSize=style.size,
                               leading=style.size * 1.35)
    lineas = [f"<b>{_esc(professional['full_name'])}</b>", _esc(especialidad)]
    if registro:
        lineas.append(f"Registro profesional {_esc(registro)}")
    ancho = 75 * mm
    filas = [[firma or Spacer(1, 18 * mm)], [Paragraph("<br/>".join(lineas), pie_firma)]]
    t = Table(filas, colWidths=[ancho], hAlign="CENTER")
    t.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("LINEABOVE", (0, 1), (0, 1), 0.6, style.secondary),
        ("TOPPADDING", (0, 1), (0, 1), 3),
    ]))
    historia += [Spacer(1, 16 * mm), KeepTogether([t, Spacer(1, 2 * mm),
                                                    Paragraph("Firma y sello", pie_firma)])]

    pie = style.page_furniture(clinic=clinic)
    doc.build(historia, onFirstPage=pie, onLaterPages=pie)
    return buf.getvalue()
