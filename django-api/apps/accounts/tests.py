from unittest import mock

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import OTPCode, User
from apps.common.models import Tenant


class AuthTests(APITestCase):
    def setUp(self):
        self.tenant = _con_whatsapp(Tenant.objects.create(name="Clínica Test", ruc="1234567890001"))
        self.admin = User.objects.create_user(
            email="admin@test.com", password="superseguro123", role="admin", tenant=self.tenant
        )

    def test_staff_login_ok(self):
        resp = self.client.post(
            reverse("staff-login"),
            {"email": "admin@test.com", "password": "superseguro123"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)
        self.assertEqual(resp.data["role"], "admin")

    def test_patient_cannot_use_staff_login(self):
        User.objects.create_user(phone="+593999999999", role="patient", tenant=self.tenant)
        resp = self.client.post(
            reverse("staff-login"), {"email": "", "password": ""}
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_otp_request_creates_code(self):
        # Solo para un paciente con el acceso a la app activado en su ficha.
        from apps.patients.models import Patient
        user = User.objects.create_user(phone="+593988888888", role="patient", tenant=self.tenant)
        Patient.objects.create(tenant=self.tenant, first_name="Ana", last_name="Código",
                               national_id="1700000001", phone="0988888888", user=user)
        with mock.patch("apps.accounts.views.send_whatsapp_template") as whatsapp:
            resp = self.client.post(reverse("otp-request"), {"phone": "098 888 8888"})
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        self.assertTrue(OTPCode.objects.filter(user=user).exists())
        self.assertEqual(whatsapp.call_args.kwargs["to_phone"], "+593988888888")

    def test_un_numero_sin_acceso_no_crea_cuenta_ni_envia_whatsapp(self):
        with mock.patch("apps.accounts.views.send_whatsapp_template") as whatsapp:
            resp = self.client.post(reverse("otp-request"), {"phone": "+593977777777"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("no tiene acceso", resp.data["detail"])
        self.assertFalse(User.objects.filter(phone="+593977777777").exists())
        whatsapp.assert_not_called()

    def test_only_admin_lists_users(self):
        reception = User.objects.create_user(
            email="recep@test.com", password="superseguro123", role="reception", tenant=self.tenant
        )
        self.client.force_authenticate(user=reception)
        resp = self.client.get(reverse("user-list"))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(reverse("user-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class MeEndpointTests(APITestCase):
    def test_me_returns_profile(self):
        from apps.common.models import Tenant
        tenant = Tenant.objects.create(name="T me")
        user = User.objects.create_user(
            email="me@test.com", password="superseguro123",
            role="reception", tenant=tenant, full_name="Laura Vera",
        )
        self.client.force_authenticate(user=user)
        resp = self.client.get("/api/v1/auth/me/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["role"], "reception")
        self.assertEqual(resp.data["full_name"], "Laura Vera")

    def test_me_requires_auth(self):
        resp = self.client.get("/api/v1/auth/me/")
        self.assertIn(resp.status_code, [401, 403])


class StaffUserCreationTests(APITestCase):
    def setUp(self):
        from apps.common.models import Tenant
        self.tenant = Tenant.objects.create(name="T staff")
        self.admin = User.objects.create_user(
            email="admin@staff.ec", password="superseguro123",
            role="admin", tenant=self.tenant,
        )

    def test_create_doctor_user_creates_doctor_profile(self):
        from apps.agenda.models import Doctor
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post("/api/v1/users/", {
            "email": "nueva.doctora@clinica.ec",
            "full_name": "Dra. Carla Ríos",
            "role": "doctor",
            "password": "ClaveSegura2026",
        })
        self.assertEqual(resp.status_code, 201, resp.content)
        user = User.objects.get(email="nueva.doctora@clinica.ec")
        self.assertEqual(user.full_name, "Dra. Carla Ríos")
        self.assertTrue(user.check_password("ClaveSegura2026"))
        # El perfil Doctor se creó solo y aparecerá en la agenda
        self.assertTrue(Doctor.objects.filter(user=user, tenant=self.tenant).exists())

    def test_reception_cannot_create_users(self):
        reception = User.objects.create_user(
            email="r@staff.ec", password="superseguro123",
            role="reception", tenant=self.tenant,
        )
        self.client.force_authenticate(user=reception)
        resp = self.client.post("/api/v1/users/", {
            "email": "x@x.ec", "role": "doctor", "password": "ClaveSegura2026",
        })
        self.assertEqual(resp.status_code, 403)


class AccesoDeRevisionTests(APITestCase):
    """El paciente de prueba que usan los revisores de App Store y Google Play."""

    def setUp(self):
        # El cupo de códigos (throttle «otp») vive en la caché y es común a
        # todas las pruebas: sin limpiarla, estas lo agotan para las demás.
        from django.core.cache import cache

        from apps.common.models import Tenant
        cache.clear()
        self.addCleanup(cache.clear)
        self.tenant = _con_whatsapp(Tenant.objects.create(name="Clínica Demostración"))
        self.revisor = self._paciente_con_acceso("+593900000001")

    def _paciente_con_acceso(self, telefono):
        from apps.patients.models import Patient
        user = User.objects.create_user(phone=telefono, role="patient", tenant=self.tenant)
        Patient.objects.create(tenant=self.tenant, first_name="Prueba", last_name=telefono[-4:],
                               national_id=telefono[-10:], phone=telefono, user=user)
        return user

    def _entrar(self, telefono, codigo):
        from unittest import mock
        with mock.patch("apps.accounts.views.send_whatsapp_template") as whatsapp:
            pedido = self.client.post(reverse("otp-request"), {"phone": telefono})
            entrada = self.client.post(reverse("otp-verify"), {"phone": telefono, "code": codigo})
        return pedido, entrada, whatsapp

    def test_entra_con_el_codigo_fijo_y_sin_whatsapp(self):
        with self.settings(APP_REVISION_TELEFONO="+593900000001", APP_REVISION_CODIGO="246810"):
            pedido, entrada, whatsapp = self._entrar("+593900000001", "246810")
        self.assertEqual(pedido.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(entrada.status_code, status.HTTP_200_OK)
        self.assertIn("access", entrada.data)
        whatsapp.assert_not_called()

    def test_sin_configurar_no_hay_acceso_de_revision(self):
        pedido, entrada, whatsapp = self._entrar("+593900000001", "246810")
        self.assertEqual(entrada.status_code, status.HTTP_400_BAD_REQUEST)
        whatsapp.assert_called_once()

    def test_el_codigo_fijo_no_sirve_para_otro_telefono(self):
        self._paciente_con_acceso("+593900000002")
        with self.settings(APP_REVISION_TELEFONO="+593900000001", APP_REVISION_CODIGO="246810"):
            _, entrada, whatsapp = self._entrar("+593900000002", "246810")
        self.assertEqual(entrada.status_code, status.HTTP_400_BAD_REQUEST)
        whatsapp.assert_called_once()

    def test_un_codigo_corto_desactiva_el_acceso(self):
        with self.settings(APP_REVISION_TELEFONO="+593900000001", APP_REVISION_CODIGO="12"):
            _, entrada, _ = self._entrar("+593900000001", "12")
        self.assertEqual(entrada.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_crea_la_cuenta_si_no_existe(self):
        with self.settings(APP_REVISION_TELEFONO="+593900000009", APP_REVISION_CODIGO="246810"):
            _, entrada, _ = self._entrar("+593900000009", "246810")
        self.assertEqual(entrada.status_code, status.HTTP_400_BAD_REQUEST)


def _con_whatsapp(tenant):
    """Estas pruebas son del código por WhatsApp: la clínica lo tiene contratado."""
    from apps.common.funcionalidades import normalizar
    from apps.common.models import PlatformConfiguration

    tenant.funcionalidades = normalizar({"whatsapp": True})
    tenant.save(update_fields=["funcionalidades"])
    config = PlatformConfiguration.get_solo()
    config.canal_codigo_paciente = "whatsapp"
    config.save()
    return tenant
