"""
Alta de clínicas y solicitudes desde la página pública.

Odontología se crea sola, pero solo con el código que llega al correo.
Medicina y psicología quedan como solicitud para la plataforma.
"""

import re

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.common.models import SolicitudClinica, Tenant

URL = "/api/v1/publico/solicitudes/"
DATOS = {"tipo": "odontologia", "clinica": "Sonrisa Norte", "ciudad": "Quito", "nombre": "Lucía Mora",
         "correo": "Lucia@Ejemplo.ec", "telefono": "0991234567"}


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AltaOdontologiaTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def codigo(self):
        return re.search(r"\b(\d{6})\b", mail.outbox[-1].subject).group(1)

    def test_con_el_codigo_se_crea_la_clinica_y_su_administradora(self):
        r = self.client.post(URL, DATOS, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["estado"], "verificando")
        self.assertFalse(Tenant.objects.filter(name="Sonrisa Norte").exists())    # aún no
        self.assertEqual(mail.outbox[-1].to, ["lucia@ejemplo.ec"])

        confirmar = f"{URL}{r.data['id']}/confirmar/"
        self.assertEqual(self.client.post(confirmar, {"codigo": "000000", "password": "Larga-y-segura-26"},
                                          format="json").status_code, 400)
        self.assertEqual(self.client.post(confirmar, {"codigo": self.codigo(), "password": "123"},
                                          format="json").status_code, 400)          # contraseña débil
        r = self.client.post(confirmar, {"codigo": self.codigo(), "password": "Larga-y-segura-26"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)

        tenant = Tenant.objects.get(name="Sonrisa Norte")
        self.assertFalse(tenant.es_prueba)
        admin = User.objects.get(email="lucia@ejemplo.ec")
        self.assertEqual((admin.tenant, admin.role, admin.must_change_password), (tenant, "admin", False))
        self.assertTrue(admin.check_password("Larga-y-segura-26"))
        self.assertIn("ya está en", mail.outbox[-1].subject)
        # El código no sirve dos veces.
        self.assertEqual(self.client.post(confirmar, {"codigo": "1", "password": "x"}, format="json").status_code,
                         400)
        # Puede entrar.
        r = self.client.post("/api/v1/auth/login/", {"email": "lucia@ejemplo.ec", "password": "Larga-y-segura-26"},
                             format="json")
        self.assertEqual(r.status_code, 200)

    def test_cinco_intentos_y_el_codigo_caduca(self):
        r = self.client.post(URL, DATOS, format="json")
        confirmar = f"{URL}{r.data['id']}/confirmar/"
        bueno = self.codigo()
        SolicitudClinica.objects.filter(pk=r.data["id"]).update(intentos=5)
        r = self.client.post(confirmar, {"codigo": bueno, "password": "Larga-y-segura-26"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Tenant.objects.filter(name="Sonrisa Norte").exists())

    def test_correo_o_nombre_ya_usados(self):
        Tenant.objects.create(name="Sonrisa Norte")
        self.assertEqual(self.client.post(URL, DATOS, format="json").status_code, 400)
        User.objects.create_user(email="lucia@ejemplo.ec", password="x-larga-123", role="superadmin")
        r = self.client.post(URL, {**DATOS, "clinica": "Otra"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_el_robot_no_deja_nada(self):
        r = self.client.post(URL, {**DATOS, "sitio_web": "http://spam"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual((SolicitudClinica.objects.count(), len(mail.outbox)), (0, 0))


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class SolicitudMedicinaTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_queda_pendiente_avisa_y_la_plataforma_la_atiende(self):
        r = self.client.post(URL, {**DATOS, "tipo": "psicologia", "mensaje": "Somos dos psicólogas"},
                             format="json")
        self.assertEqual((r.status_code, r.data["estado"]), (201, "pendiente"))
        self.assertFalse(Tenant.objects.filter(name="Sonrisa Norte").exists())
        self.assertEqual(len(mail.outbox), 2)                              # a quien pide y a la plataforma
        self.assertTrue(any("Nueva solicitud" in m.subject for m in mail.outbox))

        sa = User.objects.create_user(email="sa@clinube.ec", password="x-larga-123", role="superadmin")
        self.client.force_authenticate(sa)
        lista = self.client.get("/api/v1/platform/solicitudes/").data
        self.assertEqual([s["tipo_nombre"] for s in lista], ["Psicología"])
        r = self.client.patch(f"/api/v1/platform/solicitudes/{lista[0]['id']}/",
                              {"estado": "atendida", "nota": "Llamada el lunes"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self.client.patch(f"/api/v1/platform/solicitudes/{lista[0]['id']}/",
                                           {"estado": "creada"}, format="json").status_code, 400)

    def test_solo_la_plataforma_ve_las_solicitudes(self):
        tenant = Tenant.objects.create(name="X")
        admin = User.objects.create_user(email="a@x.ec", password="x-larga-123", role="admin", tenant=tenant)
        self.client.force_authenticate(admin)
        self.assertEqual(self.client.get("/api/v1/platform/solicitudes/").status_code, 403)
