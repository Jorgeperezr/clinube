"""
Confirmar asistencia desde la app: lo mismo que contestar «sí» al
recordatorio de WhatsApp, pero solo con las citas propias, futuras y que
la clínica aún espera que se confirmen.
"""

from apps.accounts.models import AuditLog
from apps.agenda.models import Appointment
from apps.app_paciente.tests_app_paciente import BaseApp


class ConfirmarCitaTests(BaseApp):
    def url(self, cita):
        return f"/api/v1/app/citas/{cita.id}/confirmar/"

    def test_la_cita_pendiente_se_puede_confirmar_y_queda_registrado(self):
        cita = self._cita(self.ana, estado="pending")
        self.como_ana()
        [c] = self.client.get("/api/v1/app/citas/").data["proximas"]
        self.assertTrue(c["se_puede_confirmar"])

        r = self.client.post(self.url(cita))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["estado"], "Confirmada")
        self.assertFalse(r.data["se_puede_confirmar"])
        cita.refresh_from_db()
        self.assertEqual(cita.status, Appointment.Status.CONFIRMED)
        self.assertTrue(AuditLog.objects.filter(action="confirm_appointment_app",
                                                entity_id=str(cita.id)).exists())

    def test_ni_la_ya_confirmada_ni_la_cancelada_ni_la_pasada(self):
        self.como_ana()
        for cita in (self._cita(self.ana, estado="confirmed"),
                     self._cita(self.ana, estado="cancelled"),
                     self._cita(self.ana, dentro_de_dias=-2, estado="pending")):
            self.assertEqual(self.client.post(self.url(cita)).status_code, 409, cita.status)

    def test_la_cita_de_otro_paciente_no_existe_para_ella(self):
        ajena = self._cita(self.otro, estado="pending")
        self.como_ana()
        self.assertEqual(self.client.post(self.url(ajena)).status_code, 404)
        ajena.refresh_from_db()
        self.assertEqual(ajena.status, Appointment.Status.PENDING)

    def test_el_personal_no_entra_por_aqui(self):
        cita = self._cita(self.ana, estado="pending")
        self.client.force_authenticate(user=self.doctor.user)
        self.assertEqual(self.client.post(self.url(cita)).status_code, 403)
