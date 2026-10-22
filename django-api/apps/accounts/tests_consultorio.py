"""
El profesional que trabaja solo: administra su consultorio y atiende con
la misma cuenta. Y el administrador de una clínica que también atiende.
"""


from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.agenda.models import Doctor
from apps.common.models import Tenant

FIRMA = "/api/v1/doctors/me/signature/"


class AdministradorQueAtiendeTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Sonrisa Sana")
        self.admin = User.objects.create_user(email="admin@sonrisa.ec", password="clave-larga-8gatos",
                                              role="admin", tenant=self.tenant)
        self.client.force_authenticate(self.admin)

    def test_se_marca_atiende_y_ya_sale_en_la_agenda_y_firma(self):
        self.assertFalse(self.client.get("/api/v1/auth/me/").data["atiende"])
        self.assertEqual(self.client.get(FIRMA).status_code, 404)

        r = self.client.patch(f"/api/v1/users/{self.admin.id}/", {"atiende": True}, format="json")
        self.assertEqual((r.status_code, r.data["atiende"], r.data["role"]), (200, True, "admin"))
        me = self.client.get("/api/v1/auth/me/").data
        self.assertEqual((me["atiende"], me["role"], me["modalidad"]), (True, "admin", "clinica"))
        ids = [str(d["id"]) for d in self.client.get("/api/v1/doctors/").data["results"]]
        self.assertIn(str(Doctor.objects.get(user=self.admin).id), ids)

        r = self.client.post(FIRMA, {"license_number": "SENESCYT 1234"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)

        # Dejar de atender desactiva la ficha, no la borra: el registro sigue ahí.
        self.client.patch(f"/api/v1/users/{self.admin.id}/", {"atiende": False}, format="json")
        doctor = Doctor.objects.get(user=self.admin)
        self.assertEqual((doctor.is_active, doctor.license_number), (False, "SENESCYT 1234"))
        self.assertFalse(self.client.get("/api/v1/auth/me/").data["atiende"])
        self.client.patch(f"/api/v1/users/{self.admin.id}/", {"atiende": True}, format="json")
        self.assertTrue(Doctor.objects.get(user=self.admin).is_active)

    def test_recepcion_no_atiende(self):
        r = self.client.post("/api/v1/users/", {"email": "rec@sonrisa.ec", "role": "reception", "atiende": True,
                                                "password": "Una-clave-larga-26"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("atiende", r.data.get("error", {}).get("details", r.data))

    def test_otro_administrador_nace_atendiendo(self):
        r = self.client.post("/api/v1/users/", {"email": "socia@sonrisa.ec", "role": "admin", "atiende": True,
                                                "password": "Una-clave-larga-26"}, format="json")
        self.assertEqual((r.status_code, r.data["atiende"]), (201, True))
        self.assertTrue(Doctor.objects.filter(user__email="socia@sonrisa.ec", is_active=True).exists())


class ConsultorioDesdePlataformaTests(APITestCase):
    def setUp(self):
        dueno = User.objects.create_user(email="dueno@plataforma.ec", password="superseguro123",
                                         role="superadmin", tenant=None)
        self.client.force_authenticate(dueno)

    def test_el_consultorio_nace_con_su_profesional_atendiendo(self):
        r = self.client.post("/api/v1/platform/clinics/", {
            "name": "Consultorio Dra. Mora", "modalidad": "consultorio",
            "admin_email": "lucia@mora.ec", "admin_full_name": "Lucía Mora",
        }, format="json")
        self.assertEqual((r.status_code, r.data["modalidad"]), (201, "consultorio"))
        admin = User.objects.get(email="lucia@mora.ec")
        self.assertEqual(admin.role, "admin")
        self.assertTrue(Doctor.objects.filter(user=admin, is_active=True).exists())

    def test_una_clinica_que_pasa_a_consultorio(self):
        r = self.client.post("/api/v1/platform/clinics/", {
            "name": "Clínica Actual", "admin_email": "admin@actual.ec",
        }, format="json")
        admin = User.objects.get(email="admin@actual.ec")
        self.assertFalse(Doctor.objects.filter(user=admin).exists())
        r = self.client.patch(f"/api/v1/platform/clinics/{r.data['id']}/", {"modalidad": "consultorio"},
                              format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(Doctor.objects.filter(user=admin, is_active=True).exists())


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ConsultorioDesdeLaPaginaPublicaTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_alta_publica_de_un_consultorio(self):
        url = "/api/v1/publico/solicitudes/"
        r = self.client.post(url, {"tipo": "odontologia", "modalidad": "consultorio", "clinica": "Consultorio Paz",
                                   "ciudad": "Cuenca", "nombre": "Pablo Paz", "correo": "pablo@paz.ec"},
                             format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertFalse(Tenant.objects.filter(name="Consultorio Paz").exists())    # hasta que se apruebe
        sa = User.objects.create_user(email="sa@clinube.ec", password="x-larga-123", role="superadmin")
        self.client.force_authenticate(sa)
        r = self.client.post(f"/api/v1/platform/solicitudes/{r.data['id']}/aprobar/")
        self.assertEqual(r.status_code, 201, r.data)
        tenant = Tenant.objects.get(name="Consultorio Paz")
        self.assertEqual(tenant.modalidad, "consultorio")
        self.assertTrue(Doctor.objects.filter(user__email="pablo@paz.ec", is_active=True).exists())
