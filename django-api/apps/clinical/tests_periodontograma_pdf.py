"""
La historia clínica en PDF lleva el membrete de la clínica (logotipo y
color) y el periodontograma de la última exploración, dibujado con sus
líneas de margen y de fondo de bolsa. Igual el formulario 033, que
conserva su propio diseño pero ya no sale sin el logotipo.
"""

import io
from datetime import date
from unittest import mock

from PIL import Image
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.clinical.models import PeriodontalExam, PeriodontalTooth
from apps.clinical.periodontograma_pdf import Periodontograma, resumen
from apps.common.models import Tenant
from apps.patients.models import Patient

DIBUJAR = Periodontograma.draw


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (120, 60), (14, 116, 144)).save(buf, format="PNG")
    buf.seek(0)
    buf.name = "logo.png"
    return buf


class HistoriaConMembreteYPeriodontogramaTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Sonrisa Sana", ruc="1791234567001")
        self.admin = User.objects.create_user(email="admin@sonrisa.ec", password="superseguro123",
                                              role="admin", tenant=self.tenant)
        self.patient = Patient.objects.create(tenant=self.tenant, first_name="Ana", last_name="Paz",
                                              national_id="1102003001")
        self.client.force_authenticate(self.admin)
        r = self.client.patch("/api/v1/config/branding/", {"logo": _png()}, format="multipart")
        self.assertEqual(r.status_code, 200, r.content)

        self.exam = PeriodontalExam.objects.create(tenant=self.tenant, patient=self.patient,
                                                   date=date(2026, 10, 1))
        for code, presente, pd in (("16", True, [3, 5, 6, 2, 3, 4]), ("11", True, [2, 2, 3, 3, 2, 2]),
                                   ("46", False, [])):
            PeriodontalTooth.objects.create(
                tenant=self.tenant, exam=self.exam, tooth_code=code, is_present=presente,
                probing_depth=pd, gingival_margin=[0, 1, 0, -1, 0, 0] if pd else [],
                bleeding=[True, False, False, False, False, False] if pd else [])

    def _pdf(self, ruta):
        with mock.patch.object(Periodontograma, "draw", autospec=True, side_effect=DIBUJAR) as dibujo:
            r = self.client.get(f"/api/v1/patients/{self.patient.id}/{ruta}")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b"%PDF"))
        self.assertIn(b"/Subtype /Image", r.content)          # el logotipo de la clínica
        return dibujo

    def test_historia_clinica(self):
        self.assertTrue(self._pdf("clinical-record/export-pdf/").called)

    def test_formulario_033(self):
        self.assertTrue(self._pdf("form033/export-pdf/").called)

    def test_sin_exploracion_no_hay_periodontograma(self):
        self.exam.delete()
        self.assertFalse(self._pdf("clinical-record/export-pdf/").called)

    def test_resumen_cuenta_solo_las_piezas_presentes(self):
        piezas = {t.tooth_code: t for t in self.exam.teeth.all()}
        self.assertEqual(resumen(piezas), {"sondaje_medio": 3.1, "sangrado": 17, "bolsas": 2, "sitios": 12})
