"""
GET  /api/v1/patients/{id}/certificado-atencion/?fecha=   lo que se sabe de ese día
     (hora de la cita, quién atendió, diagnósticos) para rellenar el formulario.
POST /api/v1/patients/{id}/certificado-atencion/          el PDF.

No guarda nada clínico: el certificado se arma con lo que se indique y
queda constancia en la auditoría (quién lo emitió, para quién, con qué
número). El número es correlativo por clínica.
"""

import io
import re
from datetime import datetime, time

from django.http import FileResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import AuditLog
from apps.agenda.models import Appointment, Doctor
from apps.clinical.models import Diagnosis
from apps.common.permissions import HasRole
from apps.patients.models import Patient

PUEDE_EMITIR = [HasRole.for_roles("admin", "doctor", "reception")]
ACCION = "issue_attendance_certificate"


def _paciente(request, pk):
    return generics.get_object_or_404(Patient, pk=pk, tenant=request.tenant, is_active=True)


def _citas_del_dia(request, paciente, dia):
    inicio = timezone.make_aware(datetime.combine(dia, time.min))
    fin = timezone.make_aware(datetime.combine(dia, time.max))
    return Appointment.objects.filter(tenant=request.tenant, patient=paciente, scheduled_start__gte=inicio,
                                      scheduled_start__lte=fin).exclude(status__in=("cancelled", "no_show")) \
        .select_related("doctor__user").order_by("scheduled_start")


def _ciudad(direccion):
    """«Av. 6 de Diciembre N34-120, Quito» → «Quito»: el lugar del pie del certificado."""
    partes = [p.strip() for p in re.split(r"[,·\-–]", direccion or "") if p.strip()]
    ultima = partes[-1] if partes else ""
    return ultima if ultima and not any(ch.isdigit() for ch in ultima) and len(ultima) <= 40 else ""


class CertificadoAtencionView(APIView):
    permission_classes = PUEDE_EMITIR

    def get(self, request, pk):
        paciente = _paciente(request, pk)
        dia = parse_date(request.query_params.get("fecha") or "") or timezone.localdate()
        citas = list(_citas_del_dia(request, paciente, dia))
        cita = citas[0] if citas else None
        diagnosticos = Diagnosis.objects.filter(tenant=request.tenant, patient=paciente, date=dia)
        from apps.common.document_style import clinic_snapshot

        return Response({
            "fecha": dia.isoformat(),
            "hora_inicio": timezone.localtime(cita.scheduled_start).strftime("%H:%M") if cita else "",
            "hora_fin": timezone.localtime(citas[-1].scheduled_end).strftime("%H:%M")
            if cita and citas[-1].scheduled_end else "",
            "doctor": str(cita.doctor_id) if cita and cita.doctor_id else "",
            "diagnostico": "; ".join(f"{d.code} {d.description}".strip() for d in diagnosticos),
            "lugar": _ciudad(clinic_snapshot(request.tenant).get("address")),
            "hubo_cita": bool(cita),
        })

    def post(self, request, pk):
        from apps.clinical.certificado_pdf import build_certificado_pdf
        from apps.common.document_style import clinic_snapshot, get_document_style

        paciente = _paciente(request, pk)
        d = request.data
        dia = parse_date(str(d.get("fecha") or "")) or timezone.localdate()
        if dia > timezone.localdate():
            raise ValidationError({"fecha": "No se certifica una atención que todavía no ocurre."})
        inicio, fin = parse_time(str(d.get("hora_inicio") or "")), parse_time(str(d.get("hora_fin") or ""))
        if inicio and fin and fin <= inicio:
            raise ValidationError({"hora_fin": "La hora de salida tiene que ser después de la de llegada."})
        try:
            reposo = int(d.get("reposo_dias") or 0)
        except (TypeError, ValueError):
            reposo = -1
        if not 0 <= reposo <= 30:
            raise ValidationError({"reposo_dias": "Los días de reposo van de 0 a 30."})

        doctor = None
        if d.get("doctor"):
            doctor = Doctor.objects.filter(pk=d["doctor"], tenant=request.tenant).select_related("user").first()
            if doctor is None:
                raise ValidationError({"doctor": "Ese profesional no es de esta clínica."})
        doctor = doctor or Doctor.objects.filter(user=request.user, tenant=request.tenant).first()
        if doctor is None:
            raise ValidationError({"doctor": "Elige qué profesional firma el certificado."})

        numero = AuditLog.objects.filter(tenant=request.tenant, action=ACCION).count() + 1
        texto = lambda campo, largo: str(d.get(campo) or "").strip()[:largo]  # noqa: E731
        pdf = build_certificado_pdf(
            clinic=clinic_snapshot(request.tenant),
            professional={
                "full_name": doctor.full_name,
                "specialty": ", ".join(s.name for s in doctor.specialties.all()),
                "license_number": doctor.license_number,
                "signature_b64": doctor.signature_image or None,
            },
            patient={"full_name": paciente.full_name, "national_id": paciente.national_id, "sex": paciente.sex},
            atencion={
                "fecha": dia, "hora_inicio": inicio, "hora_fin": fin, "reposo_dias": reposo,
                "diagnostico": texto("diagnostico", 300), "procedimiento": texto("procedimiento", 300),
                "observaciones": texto("observaciones", 400), "numero": f"{numero:06d}",
            },
            style=get_document_style(request.tenant),
            lugar=texto("lugar", 60),
        )
        AuditLog.objects.create(tenant=request.tenant, user=request.user, action=ACCION, entity_type="Patient",
                                entity_id=str(paciente.id),
                                metadata={"numero": numero, "fecha": dia.isoformat(), "doctor": str(doctor.id),
                                          "reposo_dias": reposo})
        return FileResponse(io.BytesIO(pdf), content_type="application/pdf",
                            filename=f"certificado-{paciente.national_id}-{dia.isoformat()}.pdf")
