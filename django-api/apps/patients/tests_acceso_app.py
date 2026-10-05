"""Acceso a la app del paciente desde su ficha (apps/patients/acceso_app.py)."""

from unittest import mock

from django.core.cache import cache
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.common.funcionalidades import normalizar
from apps.common.models import Tenant
from apps.patients.models import Patient


class AccesoAppTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.tenant = Tenant.objects.create(name="Clínica Acceso")
        self.recepcion = User.objects.create_user(
            email="r@acceso.ec", password="superseguro123", role="reception", tenant=self.tenant)
        self.paciente = Patient.objects.create(
            tenant=self.tenant, first_name="Ana", last_name="Vela",
            national_id="1711111111", phone="099 123 4567")
        self.url = f"/api/v1/patients/{self.paciente.id}/app-access/"
        self.client.force_authenticate(self.recepcion)

    def _activar(self):
        return self.client.post(self.url)

    def test_activar_crea_la_cuenta_con_el_telefono_normalizado(self):
        r = self._activar()
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data["activo"])
        self.assertEqual(r.data["telefono"], "+593991234567")
        self.paciente.refresh_from_db()
        cuenta = self.paciente.user
        self.assertEqual((cuenta.phone, cuenta.role, cuenta.tenant_id), ("+593991234567", "patient", self.tenant.id))
        self.assertEqual(cuenta.full_name, "Ana Vela")
        # Dos veces no duplica nada.
        self.assertEqual(self._activar().status_code, 200)
        self.assertEqual(User.objects.filter(phone="+593991234567").count(), 1)

    def test_con_el_acceso_el_paciente_entra_y_ve_su_ficha(self):
        self._activar()
        self.client.force_authenticate(None)
        with mock.patch("apps.accounts.views.send_whatsapp_template") as whatsapp:
            self.assertEqual(self.client.post("/api/v1/auth/otp/request/", {"phone": "0991234567"}).status_code, 202)
        codigo = whatsapp.call_args.kwargs["variables"]["1"]
        r = self.client.post("/api/v1/auth/otp/verify/", {"phone": "+593 99 123 4567", "code": codigo})
        self.assertEqual(r.status_code, 200, r.data)
        me = self.client.get("/api/v1/app/me/", HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        self.assertEqual(me.status_code, 200, me.data)
        self.client.force_authenticate(self.recepcion)
        self.assertIsNotNone(self.client.get(self.url).data["ultimo_ingreso"])

    def test_quitar_el_acceso_cierra_la_sesion(self):
        self._activar()
        self.client.force_authenticate(None)
        with mock.patch("apps.accounts.views.send_whatsapp_template") as whatsapp:
            self.client.post("/api/v1/auth/otp/request/", {"phone": "0991234567"})
        tokens = self.client.post("/api/v1/auth/otp/verify/", {
            "phone": "0991234567", "code": whatsapp.call_args.kwargs["variables"]["1"]}).data

        self.client.force_authenticate(self.recepcion)
        r = self.client.delete(self.url)
        self.assertFalse(r.data["activo"])
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/v1/app/me/", HTTP_AUTHORIZATION=f"Bearer {tokens['access']}").status_code, 401)
        self.assertEqual(self.client.post("/api/v1/auth/token/refresh/", {"refresh": tokens["refresh"]}).status_code, 401)
        with mock.patch("apps.accounts.views.send_whatsapp_template") as whatsapp:
            self.assertEqual(self.client.post("/api/v1/auth/otp/request/", {"phone": "0991234567"}).status_code, 400)
        whatsapp.assert_not_called()

    def test_sin_telefono_valido_se_explica(self):
        self.paciente.phone = "099"
        self.paciente.save()
        r = self._activar()
        self.assertEqual(r.status_code, 400)
        self.assertIn("teléfono", r.data["detail"])
        self.assertFalse(self.client.get(self.url).data["telefono_valido"])

    def test_el_telefono_de_una_persona_del_equipo_no_se_usa(self):
        User.objects.create_user(email="d@acceso.ec", password="superseguro123", role="doctor",
                                 tenant=self.tenant, phone="+593991234567")
        self.assertEqual(self._activar().status_code, 409)

    def test_un_numero_entra_a_una_sola_ficha(self):
        self._activar()
        hermana = Patient.objects.create(tenant=self.tenant, first_name="Eva", last_name="Vela",
                                         national_id="1722222222", phone="0991234567")
        r = self.client.post(f"/api/v1/patients/{hermana.id}/app-access/")
        self.assertEqual(r.status_code, 409)
        self.assertIn("otra ficha", r.data["detail"])

    def test_si_la_otra_ficha_se_borro_el_numero_queda_libre(self):
        self._activar()
        self.paciente.soft_delete()
        nueva = Patient.objects.create(tenant=self.tenant, first_name="Ana", last_name="Vela",
                                       national_id="1711111111", phone="0991234567")
        self.assertEqual(self.client.post(f"/api/v1/patients/{nueva.id}/app-access/").status_code, 200)
        self.paciente.refresh_from_db()
        self.assertIsNone(self.paciente.user)

    def test_si_cambia_de_telefono_el_acceso_va_con_el_nuevo(self):
        self._activar()
        vieja = User.objects.get(phone="+593991234567")
        self.paciente.refresh_from_db()
        self.paciente.phone = "0987654321"
        self.paciente.save()
        # El panel avisa de que la app sigue con el número anterior.
        estado = self.client.get(self.url).data
        self.assertEqual((estado["telefono"], estado["telefono_ficha"]), ("+593991234567", "+593987654321"))
        self.assertEqual(self._activar().data["telefono"], "+593987654321")
        vieja.refresh_from_db()
        self.assertFalse(vieja.is_active)

    def test_sin_la_funcion_de_la_app_no_se_activa(self):
        self.tenant.funcionalidades = normalizar({"app_paciente": False})
        self.tenant.save()
        r = self._activar()
        self.assertEqual(r.status_code, 403)
        self.assertFalse(self.client.get(self.url).data["funcion_activa"])

    def test_un_doctor_no_da_accesos(self):
        doctor = User.objects.create_user(email="doc@acceso.ec", password="superseguro123",
                                          role="doctor", tenant=self.tenant)
        self.client.force_authenticate(doctor)
        self.assertEqual(self._activar().status_code, 403)

    def test_otra_clinica_no_ve_la_ficha(self):
        otra = Tenant.objects.create(name="Otra")
        ajena = User.objects.create_user(email="r@otra.ec", password="superseguro123",
                                         role="reception", tenant=otra)
        self.client.force_authenticate(ajena)
        self.assertEqual(self._activar().status_code, 404)
