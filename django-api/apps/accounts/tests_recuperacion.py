"""
Recuperación de contraseña del personal por correo.

No tenía pruebas y el envío era silencioso: sin SMTP configurado el
correo no salía y nadie se enteraba. Aquí se fija que salga, que la
respuesta no revele si el correo existe y que un fallo quede registrado.
"""

from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import PasswordResetToken, User
from apps.common.models import Tenant

URL = "/api/v1/auth/recovery/request/"
GENERICA = "Si el correo existe, recibirás instrucciones."


class RecuperacionPorCorreo(APITestCase):
    def setUp(self):
        # El cupo de peticiones vive en la caché y se comparte entre pruebas.
        cache.clear()
        t = Tenant.objects.create(name="Clínica correo")
        self.doc = User.objects.create_user(email="doc@correo.ec", password="superseguro123",
                                            role="doctor", tenant=t)

    def test_el_personal_recibe_el_codigo(self):
        r = self.client.post(URL, {"email": "doc@correo.ec"})
        self.assertEqual(r.data["detail"], GENERICA)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["doc@correo.ec"])
        # El correo dice de dónde viene: sin marca parecía un aviso cualquiera.
        self.assertIn("Clinube", mail.outbox[0].subject)
        self.assertTrue(PasswordResetToken.objects.filter(user=self.doc).exists())

    def test_un_correo_desconocido_recibe_la_misma_respuesta_y_nada_sale(self):
        r = self.client.post(URL, {"email": "nadie@correo.ec"})
        self.assertEqual(r.data["detail"], GENERICA)
        self.assertEqual(mail.outbox, [])

    def test_si_el_smtp_falla_se_registra_y_la_respuesta_no_cambia(self):
        with mock.patch("apps.accounts.correos_personal._enviar", side_effect=OSError("smtp caído")), \
                self.assertLogs("apps.accounts.views", level="ERROR") as registro:
            r = self.client.post(URL, {"email": "doc@correo.ec"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["detail"], GENERICA)
        self.assertIn("EMAIL_HOST", registro.output[0])


CONFIRMAR = "/api/v1/auth/recovery/confirm/"


@override_settings(PANEL_URL="https://app.clinube.com")
class RecuperacionCompleta(APITestCase):
    """Del correo a la contraseña nueva, como lo hace la pantalla del panel."""

    def setUp(self):
        cache.clear()
        t = Tenant.objects.create(name="Clínica enlace")
        self.doc = User.objects.create_user(email="ana@correo.ec", password="superseguro123",
                                            role="doctor", tenant=t, full_name="Ana Ríos")
        self.doc.must_change_password = True
        self.doc.save(update_fields=["must_change_password"])

    def _token_del_correo(self):
        self.client.post(URL, {"email": "ana@correo.ec"})
        cuerpo = mail.outbox[-1].body
        self.assertIn("https://app.clinube.com/recuperar/?token=", cuerpo)
        self.assertIn("Hola, Ana Ríos:", cuerpo)
        return cuerpo.split("?token=")[1].split()[0]

    def test_el_enlace_del_correo_permite_elegir_otra_contrasena(self):
        token = self._token_del_correo()
        r = self.client.post(CONFIRMAR, {"token": token, "new_password": "LlaveDelConsultorio-93"})
        self.assertEqual(r.status_code, 200, r.data)
        self.doc.refresh_from_db()
        self.assertTrue(self.doc.check_password("LlaveDelConsultorio-93"))
        # La elige ella: deja de tener una temporal.
        self.assertFalse(self.doc.must_change_password)

    def test_el_enlace_sirve_una_sola_vez(self):
        token = self._token_del_correo()
        self.client.post(CONFIRMAR, {"token": token, "new_password": "LlaveDelConsultorio-93"})
        r = self.client.post(CONFIRMAR, {"token": token, "new_password": "OtraLlaveDistinta-41"})
        self.assertEqual(r.status_code, 400)

    def test_rige_la_misma_politica_de_contrasenas_que_en_el_panel(self):
        token = self._token_del_correo()
        r = self.client.post(CONFIRMAR, {"token": token, "new_password": "clinica2026"})
        self.assertEqual(r.status_code, 400)
        self.doc.refresh_from_db()
        self.assertTrue(self.doc.check_password("superseguro123"))
