"""
Certificado de atención y membrete de los documentos.

El certificado es el papel que el paciente lleva al trabajo: tiene que
decir quién certifica (con su registro), a quién, qué día y a qué hora,
y llevar un número que no se repita. Y todos los documentos tienen que
caber en su hoja: el pie de una receta A5 se salía por los dos lados y
los documentos compuestos con Platypus perdían el logotipo.
"""

from datetime import datetime, timedelta

from django.core.cache import cache
from django.test import SimpleTestCase
from django.utils import timezone
from reportlab.pdfbase.pdfmetrics import stringWidth
from rest_framework.test import APITestCase

from apps.accounts.models import AuditLog, User
from apps.agenda.models import Appointment, Doctor
from apps.clinical.certificado_pdf import fecha_larga
from apps.clinical.certificado_views import _ciudad
from apps.common.document_style import _cabe, get_document_style
from apps.common.models import Tenant
from apps.patients.models import Patient

CLAVE = "clave-larga-8gatos"


class CertificadoTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.tenant = Tenant.objects.create(name="Clínica Cert", ruc="1792345678001")
        self.recepcion = User.objects.create_user(email="rec@cert.ec", password=CLAVE, role="reception",
                                                  tenant=self.tenant, full_name="Rosa")
        user = User.objects.create_user(email="doc@cert.ec", password=CLAVE, role="doctor",
                                        tenant=self.tenant, full_name="Dra. Elena Ruiz")
        self.doctor = Doctor.objects.create(tenant=self.tenant, user=user, license_number="MSP-123")
        self.paciente = Patient.objects.create(tenant=self.tenant, first_name="Ana", last_name="Pérez",
                                               national_id="0102030405", phone="0991111111", sex="M")
        self.url = f"/api/v1/patients/{self.paciente.id}/certificado-atencion/"
        self.client.force_authenticate(self.recepcion)

    def test_se_rellena_con_la_cita_del_dia(self):
        hoy = timezone.localdate()
        inicio = timezone.make_aware(datetime.combine(hoy, datetime.min.time()).replace(hour=10, minute=30))
        Appointment.objects.create(tenant=self.tenant, patient=self.paciente, doctor=self.doctor,
                                   scheduled_start=inicio, scheduled_end=inicio + timedelta(minutes=45),
                                   status="completed")
        r = self.client.get(f"{self.url}?fecha={hoy.isoformat()}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.data["hora_inicio"], r.data["hora_fin"], r.data["doctor"]),
                         ("10:30", "11:15", str(self.doctor.id)))

    def test_genera_el_pdf_numerado_y_lo_deja_en_la_auditoria(self):
        cuerpo = {"fecha": timezone.localdate().isoformat(), "hora_inicio": "10:30", "hora_fin": "11:00",
                  "doctor": str(self.doctor.id), "reposo_dias": 2, "lugar": "Quito"}
        r = self.client.post(self.url, cuerpo, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(b"".join(r.streaming_content).startswith(b"%PDF"))
        self.client.post(self.url, cuerpo, format="json")
        numeros = sorted(a.metadata["numero"] for a in AuditLog.objects.filter(
            action="issue_attendance_certificate"))
        self.assertEqual(numeros, [1, 2])

    def test_lo_que_no_se_certifica(self):
        manana = (timezone.localdate() + timedelta(days=1)).isoformat()
        for extra in ({"fecha": manana}, {"reposo_dias": 31}, {"hora_inicio": "11:00", "hora_fin": "10:00"}):
            r = self.client.post(self.url, {"doctor": str(self.doctor.id), **extra}, format="json")
            self.assertEqual(r.status_code, 400, extra)
        # Recepción no es doctora: tiene que elegir quién firma.
        self.assertEqual(self.client.post(self.url, {}, format="json").status_code, 400)

    def test_ni_otra_clinica_ni_un_paciente(self):
        otra = Tenant.objects.create(name="Otra")
        ajeno = User.objects.create_user(email="x@otra.ec", password=CLAVE, role="admin", tenant=otra)
        self.client.force_authenticate(ajeno)
        self.assertEqual(self.client.get(self.url).status_code, 404)


class TextoTests(SimpleTestCase):
    def test_fecha_y_ciudad(self):
        self.assertEqual(fecha_larga(datetime(2026, 10, 14).date()), "miércoles 14 de octubre de 2026")
        self.assertEqual(_ciudad("Av. 6 de Diciembre N34-120 y Portugal, Quito"), "Quito")
        self.assertEqual(_ciudad("Calle 10 N.º 5"), "")


class MembreteTests(SimpleTestCase):
    CLINICA = {"name": "Clínica Odontológica Especializada Sonrisa Andina del Norte", "ruc": "1792345678001",
               "address": "Av. 6 de Diciembre N34-120 y Portugal, edificio Torre Azul, Quito",
               "phone": "02 245 6789 · 099 123 4567", "email": "contacto@sonrisaandinadelnorte.ec"}

    def test_el_contacto_se_reparte_sin_salirse_de_un_a5(self):
        estilo = get_document_style().for_page("A5")
        ancho = estilo.content_width - 30
        lineas = estilo._lineas_de_contacto(self.CLINICA, {}, ancho, estilo.size - 1.5)
        self.assertTrue(lineas[0].startswith("RUC 1792345678001"))
        self.assertGreater(len(lineas), 1)
        # No se pierde ninguna pieza: todas en algún renglón.
        for pieza in ("Torre Azul, Quito", "Tel. 02 245 6789", "contacto@sonrisaandinadelnorte.ec"):
            self.assertIn(pieza, " · ".join(lineas))

    def test_lo_que_no_cabe_se_recorta_con_puntos(self):
        texto = _cabe("x" * 500, "Helvetica", 8, 200)
        self.assertTrue(texto.endswith("…"))
        self.assertLessEqual(stringWidth(texto, "Helvetica", 8), 200)
        self.assertEqual(_cabe("corto", "Helvetica", 8, 200), "corto")

    def test_el_pie_cabe_y_conserva_fecha_y_pagina(self):
        from reportlab.pdfgen import canvas

        dibujado = []

        class Espia(canvas.Canvas):
            def drawCentredString(self, x, y, text, *a, **k):
                dibujado.append(text)
                return super().drawCentredString(x, y, text, *a, **k)

        estilo = get_document_style().for_page("A5")
        import io

        c = Espia(io.BytesIO(), pagesize=estilo.page_size)
        estilo.draw_footer(c, page_number=1, total_pages=1, clinic=self.CLINICA)
        pie = dibujado[-1]
        self.assertLessEqual(stringWidth(pie, estilo.font, estilo.size - 2), estilo.content_width)
        self.assertIn("Página 1 de 1", pie)
