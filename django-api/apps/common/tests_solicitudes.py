"""
Solicitudes de alta desde la página pública.

Nada se crea solo: la solicitud queda pendiente, la plataforma la aprueba
y entonces se crea la clínica, con un administrador que elige su
contraseña con el enlace que le llega al correo.
"""

import re
from datetime import datetime, timedelta

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import AuditLog, User
from apps.common.models import SolicitudClinica, Tenant

URL = "/api/v1/publico/solicitudes/"
DATOS = {"tipo": "odontologia", "clinica": "Sonrisa Norte", "ciudad": "Quito", "nombre": "Lucía Mora",
         "correo": "Lucia@Ejemplo.ec", "telefono": "0991234567"}


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class SolicitudPublicaTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_odontologia_queda_pendiente_y_no_crea_nada(self):
        r = self.client.post(URL, DATOS, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data["estado"], r.data["plazo_horas"]), ("pendiente", None))
        self.assertFalse(Tenant.objects.filter(name="Sonrisa Norte").exists())
        self.assertFalse(User.objects.filter(email="lucia@ejemplo.ec").exists())
        recibida, aviso = sorted(mail.outbox, key=lambda m: "Nueva solicitud" in m.subject)
        self.assertEqual(recibida.to, ["lucia@ejemplo.ec"])
        self.assertIn("a la brevedad", recibida.body)
        self.assertIn("Nueva solicitud", aviso.subject)
        self.assertIn("/panel/plataforma/?tab=solicitudes", aviso.body)

    def test_medicina_y_psicologia_prometen_doce_horas(self):
        for tipo, correo in (("medicina", "m@ejemplo.ec"), ("psicologia", "p@ejemplo.ec")):
            mail.outbox.clear()
            r = self.client.post(URL, {**DATOS, "tipo": tipo, "correo": correo, "clinica": f"Consulta {tipo}"},
                                 format="json")
            self.assertEqual((r.status_code, r.data["plazo_horas"]), (201, 12), r.data)
            self.assertTrue(any("hasta 12 horas" in m.body for m in mail.outbox))

    def test_correo_o_nombre_ya_usados(self):
        Tenant.objects.create(name="Sonrisa Norte")
        self.assertEqual(self.client.post(URL, DATOS, format="json").status_code, 400)
        User.objects.create_user(email="lucia@ejemplo.ec", password="x-larga-123", role="superadmin")
        r = self.client.post(URL, {**DATOS, "clinica": "Otra"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_no_se_repite_una_solicitud_pendiente(self):
        self.assertEqual(self.client.post(URL, DATOS, format="json").status_code, 201)
        r = self.client.post(URL, {**DATOS, "clinica": "Otro nombre"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("revisando", str(r.data))

    def test_el_robot_no_deja_nada(self):
        r = self.client.post(URL, {**DATOS, "sitio_web": "http://spam"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual((SolicitudClinica.objects.count(), len(mail.outbox)), (0, 0))

    def test_la_ruta_del_codigo_ya_no_existe(self):
        r = self.client.post(URL, DATOS, format="json")
        r = self.client.post(f"{URL}{r.data['id']}/confirmar/", {"codigo": "123456", "password": "x"},
                             format="json")
        self.assertEqual(r.status_code, 404)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   PANEL_URL="https://app.clinube.com")
class AprobacionTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.sa = User.objects.create_user(email="sa@clinube.ec", password="x-larga-123", role="superadmin")

    def solicitar(self, **extra):
        r = self.client.post(URL, {**DATOS, **extra}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.client.force_authenticate(self.sa)
        return r.data["id"]

    def enlace(self):
        return re.search(r"https://app\.clinube\.com/recuperar/\?token=([\w-]+)&bienvenida=1",
                         mail.outbox[-1].body).group(1)

    def test_aprobar_crea_la_clinica_y_su_administradora_elige_la_contrasena(self):
        sid = self.solicitar()
        lista = self.client.get("/api/v1/platform/solicitudes/").data
        self.assertEqual([(s["estado"], s["plazo_horas"]) for s in lista], [("pendiente", None)])

        r = self.client.post(f"/api/v1/platform/solicitudes/{sid}/aprobar/",
                             {"clinica": "Sonrisa Norte Quito"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data["estado"], r.data["correo_enviado"], r.data["admin_pendiente"]),
                         ("creada", True, True))
        tenant = Tenant.objects.get(name="Sonrisa Norte Quito")
        self.assertTrue(tenant.funcionalidades["formulario_033"])
        admin = User.objects.get(email="lucia@ejemplo.ec")
        self.assertEqual((admin.tenant, admin.role), (tenant, "admin"))
        self.assertFalse(admin.has_usable_password())
        self.assertIn("Aprobamos", mail.outbox[-1].subject)
        self.assertEqual(mail.outbox[-1].to, ["lucia@ejemplo.ec"])
        self.assertTrue(AuditLog.objects.filter(action="approve_clinic_request", tenant=None).exists())

        # Con el enlace elige su contraseña y entra.
        self.client.force_authenticate(None)
        r = self.client.post("/api/v1/auth/recovery/confirm/",
                             {"token": self.enlace(), "new_password": "Larga-y-segura-26"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        r = self.client.post("/api/v1/auth/login/", {"email": "lucia@ejemplo.ec", "password": "Larga-y-segura-26"},
                             format="json")
        self.assertEqual(r.status_code, 200, r.data)

        self.client.force_authenticate(self.sa)
        fila = self.client.get("/api/v1/platform/solicitudes/").data[0]
        self.assertFalse(fila["admin_pendiente"])
        # No se aprueba dos veces.
        self.assertEqual(self.client.post(f"/api/v1/platform/solicitudes/{sid}/aprobar/").status_code, 409)

    def test_reenviar_el_enlace_mientras_no_entra(self):
        sid = self.solicitar()
        self.client.post(f"/api/v1/platform/solicitudes/{sid}/aprobar/")
        antes = len(mail.outbox)
        r = self.client.post(f"/api/v1/platform/solicitudes/{sid}/reenviar/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(mail.outbox), antes + 1)
        admin = User.objects.get(email="lucia@ejemplo.ec")
        admin.set_password("Larga-y-segura-26")
        admin.save()
        self.assertEqual(self.client.post(f"/api/v1/platform/solicitudes/{sid}/reenviar/").status_code, 400)

    def test_consultorio_de_psicologia_atiende_y_sin_formulario_033(self):
        from apps.agenda.models import Doctor

        sid = self.solicitar(tipo="psicologia", modalidad="consultorio")
        fila = self.client.get("/api/v1/platform/solicitudes/").data[0]
        self.assertEqual(fila["plazo_horas"], 12)
        creada = SolicitudClinica.objects.get(pk=sid).created_at
        self.assertEqual(datetime.fromisoformat(fila["responder_antes"]), creada + timedelta(hours=12))
        r = self.client.post(f"/api/v1/platform/solicitudes/{sid}/aprobar/")
        self.assertEqual(r.status_code, 201, r.data)
        tenant = Tenant.objects.get(name="Sonrisa Norte")
        self.assertEqual(tenant.modalidad, "consultorio")
        self.assertFalse(tenant.funcionalidades["formulario_033"])
        self.assertTrue(Doctor.objects.filter(user__email="lucia@ejemplo.ec", is_active=True).exists())

    def test_si_el_correo_se_ocupo_mientras_esperaba_no_se_crea(self):
        sid = self.solicitar()
        User.objects.create_user(email="lucia@ejemplo.ec", password="x-larga-123", role="superadmin")
        r = self.client.post(f"/api/v1/platform/solicitudes/{sid}/aprobar/")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Tenant.objects.filter(name="Sonrisa Norte").exists())
        self.assertEqual(SolicitudClinica.objects.get(pk=sid).estado, "pendiente")

    def test_descartar_con_y_sin_aviso(self):
        sid = self.solicitar()
        antes = len(mail.outbox)
        r = self.client.patch(f"/api/v1/platform/solicitudes/{sid}/",
                              {"estado": "descartada", "nota": "Datos falsos"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(mail.outbox), antes)
        # Una descartada no se aprueba sin volver a pendiente.
        self.assertEqual(self.client.post(f"/api/v1/platform/solicitudes/{sid}/aprobar/").status_code, 400)
        self.client.patch(f"/api/v1/platform/solicitudes/{sid}/", {"estado": "pendiente"}, format="json")
        self.client.patch(f"/api/v1/platform/solicitudes/{sid}/", {"estado": "descartada", "avisar": True},
                          format="json")
        self.assertEqual(len(mail.outbox), antes + 1)
        self.assertIn("no podemos abrir", mail.outbox[-1].body)
        self.assertEqual(self.client.patch(f"/api/v1/platform/solicitudes/{sid}/", {"estado": "creada"},
                                           format="json").status_code, 400)

    def test_una_creada_no_cambia_de_estado(self):
        sid = self.solicitar()
        self.client.post(f"/api/v1/platform/solicitudes/{sid}/aprobar/")
        r = self.client.patch(f"/api/v1/platform/solicitudes/{sid}/", {"estado": "descartada"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_solo_la_plataforma_ve_y_aprueba(self):
        sid = self.solicitar()
        tenant = Tenant.objects.create(name="X")
        admin = User.objects.create_user(email="a@x.ec", password="x-larga-123", role="admin", tenant=tenant)
        self.client.force_authenticate(admin)
        self.assertEqual(self.client.get("/api/v1/platform/solicitudes/").status_code, 403)
        self.assertEqual(self.client.post(f"/api/v1/platform/solicitudes/{sid}/aprobar/").status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post(f"/api/v1/platform/solicitudes/{sid}/aprobar/").status_code, 401)
        self.assertFalse(Tenant.objects.filter(name="Sonrisa Norte").exists())
