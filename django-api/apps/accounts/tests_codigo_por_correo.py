"""
El código de acceso del paciente por correo (apps/accounts/acceso_paciente.py).

La plataforma elige el canal; el paciente se identifica con su teléfono o
con su correo. Apagado (WhatsApp) todo sigue como antes.
"""

import smtplib
from unittest import mock

from django.core import mail
from django.core.cache import cache
from rest_framework.test import APITestCase

from apps.accounts.models import OTPCode, User
from apps.common.models import PlatformConfiguration, Tenant
from apps.patients.models import Patient

PEDIR = "/api/v1/auth/otp/request/"
ENTRAR = "/api/v1/auth/otp/verify/"


def _codigo_del_correo():
    cuerpo = mail.outbox[-1].body
    return next(linea.strip() for linea in cuerpo.splitlines() if linea.strip().isdigit())


class Base(APITestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.tenant = Tenant.objects.create(name="Clínica Correo")
        self.recepcion = User.objects.create_user(
            email="r@correo-clinica.ec", password="superseguro123", role="reception", tenant=self.tenant)
        self.paciente = Patient.objects.create(
            tenant=self.tenant, first_name="Ana", last_name="Vela", national_id="1711111111",
            phone="099 123 4567", email="Ana.Vela@Gmail.com")
        self.url = f"/api/v1/patients/{self.paciente.id}/app-access/"

    def canal(self, canal):
        config = PlatformConfiguration.get_solo()
        config.canal_codigo_paciente = canal
        config.save()

    def activar(self):
        self.client.force_authenticate(self.recepcion)
        r = self.client.post(self.url)
        self.client.force_authenticate(None)
        return r


class CanalTests(Base):
    def test_la_app_pregunta_el_canal_sin_sesion(self):
        self.assertEqual(self.client.get("/api/v1/auth/otp/canal/").data, {"canal": "whatsapp"})
        self.canal("correo")
        self.assertEqual(self.client.get("/api/v1/auth/otp/canal/").data, {"canal": "correo"})


class CodigoPorCorreoTests(Base):
    def setUp(self):
        super().setUp()
        self.canal("correo")

    def test_entra_con_su_correo_y_el_codigo_que_le_llega(self):
        self.assertEqual(self.activar().status_code, 200)
        with mock.patch("apps.accounts.views.send_whatsapp_template") as whatsapp:
            r = self.client.post(PEDIR, {"email": " ANA.vela@gmail.com "})
        self.assertEqual(r.status_code, 202, r.data)
        self.assertIn("an***@gmail.com", r.data["detail"])
        whatsapp.assert_not_called()
        self.assertEqual(mail.outbox[-1].to, ["ana.vela@gmail.com"])
        self.assertIn("Clínica Correo", mail.outbox[-1].body)

        r = self.client.post(ENTRAR, {"email": "ana.vela@gmail.com", "code": _codigo_del_correo()})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn("access", r.data)

    def test_una_app_que_aun_pide_el_telefono_recibe_el_codigo_en_el_correo(self):
        self.activar()
        r = self.client.post(PEDIR, {"phone": "0991234567"})
        self.assertEqual(r.status_code, 202, r.data)
        self.assertEqual(mail.outbox[-1].to, ["ana.vela@gmail.com"])
        r = self.client.post(ENTRAR, {"phone": "0991234567", "code": _codigo_del_correo()})
        self.assertEqual(r.status_code, 200, r.data)

    def test_un_correo_sin_acceso(self):
        r = self.client.post(PEDIR, {"email": "nadie@gmail.com"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Este correo no tiene acceso", r.data["detail"])
        self.assertEqual(mail.outbox, [])

    def test_lo_que_no_es_un_correo(self):
        r = self.client.post(PEDIR, {"email": "ana@"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("correo completo", r.data["detail"])

    def test_sin_telefono_ni_correo(self):
        self.assertEqual(self.client.post(PEDIR, {}).status_code, 400)

    def test_codigo_equivocado(self):
        self.activar()
        self.client.post(PEDIR, {"email": "ana.vela@gmail.com"})
        r = self.client.post(ENTRAR, {"email": "ana.vela@gmail.com", "code": "000000"
                                      if _codigo_del_correo() != "000000" else "111111"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["detail"], "Correo o código inválido.")

    def test_si_el_correo_no_sale_se_dice_y_el_codigo_no_queda_vivo(self):
        self.activar()
        with mock.patch("apps.accounts.acceso_paciente.send_mail", side_effect=smtplib.SMTPException("caído")), \
                self.assertLogs("apps.accounts.views", level="ERROR"):
            r = self.client.post(PEDIR, {"email": "ana.vela@gmail.com"})
        self.assertEqual(r.status_code, 503)
        self.assertIn("No se pudo enviar el correo", r.data["detail"])
        self.assertFalse(OTPCode.objects.filter(user__email="ana.vela@gmail.com").exists())

    def test_ficha_sin_correo(self):
        # Activada cuando el código iba por WhatsApp, y la ficha sin correo.
        self.canal("whatsapp")
        self.paciente.email = ""
        self.paciente.save()
        self.activar()
        self.canal("correo")
        r = self.client.post(PEDIR, {"phone": "0991234567"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("no tiene correo", r.data["detail"])

    def test_cuentas_activadas_antes_con_el_telefono_entran_con_el_correo_de_la_ficha(self):
        cuenta = User.objects.create_user(phone="+593991234567", role="patient", tenant=self.tenant)
        self.paciente.user = cuenta
        self.paciente.save()
        r = self.client.post(PEDIR, {"email": "ana.vela@gmail.com"})
        self.assertEqual(r.status_code, 202, r.data)
        self.assertEqual(mail.outbox[-1].to, ["ana.vela@gmail.com"])

    def test_el_mismo_correo_en_dos_fichas_sin_cuenta_con_correo(self):
        for n, telefono in ((1, "+593991111111"), (2, "+593992222222")):
            ficha = Patient.objects.create(
                tenant=self.tenant, first_name=f"Hijo{n}", last_name="Vela",
                national_id=f"17222222{n}2", email="familia@gmail.com")
            ficha.user = User.objects.create_user(phone=telefono, role="patient", tenant=self.tenant)
            ficha.save()
        r = self.client.post(PEDIR, {"email": "familia@gmail.com"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("varios pacientes", r.data["detail"])


class ConWhatsAppTests(Base):
    def test_identificarse_con_el_correo_manda_el_whatsapp_a_su_numero(self):
        self.activar()
        with mock.patch("apps.accounts.views.send_whatsapp_template") as whatsapp:
            r = self.client.post(PEDIR, {"email": "ana.vela@gmail.com"})
        self.assertEqual(r.status_code, 202, r.data)
        self.assertEqual(r.data["detail"], "Código enviado por WhatsApp.")
        self.assertEqual(whatsapp.call_args.kwargs["to_phone"], "+593991234567")
        self.assertEqual(mail.outbox, [])

    def test_activar_guarda_tambien_el_correo_para_poder_cambiar_de_canal(self):
        r = self.activar()
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["canal"], "whatsapp")
        self.paciente.refresh_from_db()
        self.assertEqual(self.paciente.user.email, "ana.vela@gmail.com")

    def test_si_el_correo_es_de_otra_persona_se_activa_sin_el(self):
        User.objects.create_user(email="ana.vela@gmail.com", password="superseguro123",
                                 role="doctor", tenant=self.tenant)
        self.assertEqual(self.activar().status_code, 200)
        self.paciente.refresh_from_db()
        self.assertIsNone(self.paciente.user.email)


class ActivarConCorreoTests(Base):
    def setUp(self):
        super().setUp()
        self.canal("correo")

    def test_el_telefono_ya_no_hace_falta(self):
        self.paciente.phone = ""
        self.paciente.save()
        r = self.activar()
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data["canal"], r.data["correo"]), ("correo", "ana.vela@gmail.com"))
        self.paciente.refresh_from_db()
        self.assertEqual((self.paciente.user.email, self.paciente.user.phone), ("ana.vela@gmail.com", None))

    def test_hace_falta_el_correo(self):
        self.paciente.email = ""
        self.paciente.save()
        r = self.activar()
        self.assertEqual(r.status_code, 400)
        self.assertIn("correo electrónico válido", r.data["detail"])

    def test_un_correo_del_equipo(self):
        User.objects.create_user(email="ana.vela@gmail.com", password="superseguro123",
                                 role="doctor", tenant=self.tenant)
        r = self.activar()
        self.assertEqual(r.status_code, 409)
        self.assertIn("persona del equipo", r.data["detail"])

    def test_un_correo_que_ya_entra_con_otra_ficha(self):
        self.activar()
        otra = Patient.objects.create(tenant=self.tenant, first_name="Eva", last_name="Vela",
                                      national_id="1733333333", email="ana.vela@gmail.com")
        self.client.force_authenticate(self.recepcion)
        r = self.client.post(f"/api/v1/patients/{otra.id}/app-access/")
        self.assertEqual(r.status_code, 409)
        self.assertIn("otra ficha", r.data["detail"])

    def test_un_telefono_del_equipo_no_estorba(self):
        User.objects.create_user(phone="+593991234567", email="aux@clinica.ec", password="superseguro123",
                                 role="auxiliary", tenant=self.tenant)
        r = self.activar()
        self.assertEqual(r.status_code, 200, r.data)
        self.paciente.refresh_from_db()
        self.assertEqual(self.paciente.user.email, "ana.vela@gmail.com")
        self.assertIsNone(self.paciente.user.phone)


class AvisoDePrivacidadTests(Base):
    def test_dice_quien_envia_el_codigo(self):
        texto = str(self.client.get("/api/v1/legal/privacidad/").data)
        self.assertIn("WhatsApp): envía los códigos para entrar en la app", texto)
        self.canal("correo")
        texto = str(self.client.get("/api/v1/legal/privacidad/").data)
        self.assertNotIn("WhatsApp): envía los códigos", texto)
        self.assertIn("los códigos para entrar en la app y los de recuperar una contraseña", texto)
