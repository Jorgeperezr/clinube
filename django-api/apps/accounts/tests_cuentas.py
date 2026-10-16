"""
Cuentas: el paciente crea la suya y su clínica la enlaza; el equipo entra
con Google o recibe una invitación con la marca de la clínica; el correo
es el canal de todos y WhatsApp, solo de quien lo contrata.
"""

from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import PasswordResetToken, User
from apps.common.funcionalidades import contratadas
from apps.common.models import PlatformConfiguration, Tenant
from apps.configuration.models import ClinicBranding
from apps.patients.models import Patient

PEDIR = "/api/v1/auth/otp/request/"
ENTRAR = "/api/v1/auth/otp/verify/"
CLAVE = "clave-larga-8gatos"


def _codigo():
    cuerpo = mail.outbox[-1].body
    return next(linea.strip() for linea in cuerpo.splitlines() if linea.strip().isdigit())


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   PANEL_URL="https://app.clinube.com")
class Base(APITestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.tenant = Tenant.objects.create(name="Sonrisa Sana")
        ClinicBranding.objects.create(tenant=self.tenant, display_name="Sonrisa Sana", email="hola@sonrisa.ec")
        self.admin = User.objects.create_user(email="admin@sonrisa.ec", password=CLAVE, role="admin",
                                              tenant=self.tenant, full_name="Ana Admin")


class PacienteCreaSuCuentaTests(Base):
    def test_crea_la_cuenta_espera_y_la_clinica_la_enlaza(self):
        r = self.client.post(PEDIR, {"email": "Lucia@Gmail.com", "crear": True, "nombre": "Lucía Paz"})
        self.assertEqual(r.status_code, 202, r.data)
        cuenta = User.objects.get(email="lucia@gmail.com")
        self.assertEqual((cuenta.role, cuenta.tenant_id), ("patient", None))
        tokens = self.client.post(ENTRAR, {"email": "lucia@gmail.com", "code": _codigo()}).data
        auth = {"HTTP_AUTHORIZATION": f"Bearer {tokens['access']}"}
        estado = self.client.get("/api/v1/app/cuenta/", **auth).data
        self.assertEqual((estado["enlazada"], estado["clinica"], estado["correo"]), (False, None, "lucia@gmail.com"))

        # La recepción ve en la ficha que ya tiene cuenta y la enlaza.
        ficha = Patient.objects.create(tenant=self.tenant, first_name="Lucía", last_name="Paz",
                                       national_id="1711111111", email="lucia@gmail.com")
        self.client.force_authenticate(self.admin)
        url = f"/api/v1/patients/{ficha.id}/app-access/"
        self.assertTrue(self.client.get(url).data["cuenta_propia"])
        r = self.client.post(url)
        self.assertEqual(r.status_code, 200, r.data)
        ficha.refresh_from_db()
        self.assertEqual(ficha.user_id, cuenta.id)
        self.client.force_authenticate(None)

        # Con un token nuevo ya ve su clínica y su ficha.
        self.client.post(PEDIR, {"email": "lucia@gmail.com"})
        tokens = self.client.post(ENTRAR, {"email": "lucia@gmail.com", "code": _codigo()}).data
        auth = {"HTTP_AUTHORIZATION": f"Bearer {tokens['access']}"}
        self.assertEqual(self.client.get("/api/v1/app/cuenta/", **auth).data["enlazada"], True)
        self.assertEqual(self.client.get("/api/v1/app/me/", **auth).status_code, 200)

    def test_el_correo_del_equipo_no_crea_paciente(self):
        r = self.client.post(PEDIR, {"email": "admin@sonrisa.ec", "crear": True, "nombre": "X"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(User.objects.filter(email="admin@sonrisa.ec").count(), 1)


class CanalTests(Base):
    def test_whatsapp_es_a_pedido_y_el_codigo_va_por_correo(self):
        self.assertFalse(contratadas(Tenant.objects.create(name="Nueva"))["whatsapp"])
        cuenta = User.objects.create_user(phone="+593991234567", email="pepe@gmail.com", role="patient",
                                          tenant=self.tenant)
        Patient.objects.create(tenant=self.tenant, first_name="Pepe", last_name="Ruiz", national_id="1722222222",
                               email="pepe@gmail.com", user=cuenta)
        config = PlatformConfiguration.get_solo()
        config.canal_codigo_paciente = "whatsapp"
        config.save()
        # Aunque la plataforma use WhatsApp, esta clínica no lo contrató: va por correo.
        with mock.patch("apps.accounts.views.send_whatsapp_template") as whatsapp:
            r = self.client.post(PEDIR, {"phone": "0991234567"})
        self.assertEqual(r.status_code, 202, r.data)
        whatsapp.assert_not_called()
        self.assertEqual(mail.outbox[-1].to, ["pepe@gmail.com"])


class GoogleTests(Base):
    URL = "/api/v1/auth/google/"

    def setUp(self):
        super().setUp()
        config = PlatformConfiguration.get_solo()
        config.google_client_id = "123.apps.googleusercontent.com"
        config.save()

    def entrar(self, correo, para="personal", nombre="Ana"):
        with mock.patch("apps.accounts.google.verificar",
                        return_value={"email": correo, "email_verified": True, "name": nombre}):
            return self.client.post(self.URL, {"credential": "x", "para": para}, format="json")

    def test_el_equipo_entra_y_se_anula_la_contrasena_temporal(self):
        self.admin.must_change_password = True
        self.admin.save()
        r = self.entrar("ADMIN@sonrisa.ec")
        self.assertEqual((r.status_code, r.data["role"], r.data["must_change_password"]), (200, "admin", False))
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.has_usable_password())

    def test_google_no_crea_personal(self):
        r = self.entrar("desconocido@gmail.com")
        self.assertEqual(r.status_code, 400)
        self.assertIn("administrador de tu clínica", r.data["detail"])

    def test_el_paciente_sin_cuenta_la_crea(self):
        r = self.entrar("nuevo@gmail.com", para="paciente", nombre="Nuevo Paciente")
        self.assertEqual((r.status_code, r.data["role"]), (200, "patient"))
        self.assertEqual(User.objects.get(email="nuevo@gmail.com").full_name, "Nuevo Paciente")

    def test_sin_configurar_o_token_falso(self):
        self.assertEqual(self.client.get("/api/v1/auth/google/config/").data["client_id"],
                         "123.apps.googleusercontent.com")
        with mock.patch("apps.accounts.google._claves", return_value={}):    # sin salir a internet
            r = self.client.post(self.URL, {"credential": "basura"}, format="json")
        self.assertEqual(r.status_code, 400)
        config = PlatformConfiguration.get_solo()
        config.google_client_id = ""
        config.save()
        self.assertEqual(self.entrar("admin@sonrisa.ec").status_code, 400)


class InvitacionTests(Base):
    def test_sin_contrasena_llega_la_invitacion_con_la_marca_de_la_clinica(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post("/api/v1/users/", {"email": "doc@sonrisa.ec", "full_name": "Diego Doc",
                                                "role": "doctor"}, format="json")
        self.assertEqual((r.status_code, r.data["invitacion"]), (201, "enviada"))
        correo = mail.outbox[-1]
        self.assertEqual(correo.to, ["doc@sonrisa.ec"])
        self.assertIn("Sonrisa Sana", correo.subject)
        self.assertIn("https://app.clinube.com/recuperar/?token=", correo.body)
        self.assertIn("Sonrisa Sana", correo.alternatives[0][0])
        doc = User.objects.get(email="doc@sonrisa.ec")
        self.assertFalse(doc.has_usable_password())
        self.assertTrue(PasswordResetToken.objects.filter(user=doc).exists())
        # Se puede volver a mandar.
        self.assertEqual(self.client.post(f"/api/v1/users/{doc.id}/invitar/").data["invitacion"], "enviada")

    def test_con_contrasena_no_se_invita(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post("/api/v1/users/", {"email": "rec@sonrisa.ec", "role": "reception",
                                                "password": "Una-clave-larga-26"}, format="json")
        self.assertEqual((r.status_code, r.data["invitacion"]), (201, None))
        self.assertEqual(mail.outbox, [])

    def test_la_recuperacion_lleva_la_marca_de_la_clinica(self):
        self.client.post("/api/v1/auth/recovery/request/", {"email": "admin@sonrisa.ec"})
        self.assertIn("Sonrisa Sana", mail.outbox[-1].alternatives[0][0])
