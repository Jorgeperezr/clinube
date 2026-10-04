"""
Textos legales: el aviso de privacidad, las condiciones que acepta cada
clínica y la constancia de que se informó al paciente.
"""

from unittest import mock

from django.core.cache import cache
from rest_framework.test import APITestCase

from apps.accounts.models import AuditLog, User
from apps.common import legal
from apps.common.models import AceptacionCondiciones, PlatformConfiguration, Tenant
from apps.patients.models import AvisoPrivacidadEntregado, Patient


def _texto(doc):
    return " ".join(
        [s["titulo"] for s in doc["secciones"]]
        + [p for s in doc["secciones"] for p in s["parrafos"]]
    )


class AvisoPrivacidadTests(APITestCase):
    def setUp(self):
        cache.clear()

    def test_es_publico_y_dice_lo_que_tiene_que_decir(self):
        resp = self.client.get("/api/v1/legal/privacidad/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["version"], legal.AVISO_VERSION)
        texto = _texto(resp.data)
        # Dónde están los datos y quién más interviene.
        for nombre in ("Oracle", "Santiago de Chile", "Cloudflare", "WhatsApp", "transferencia internacional"):
            self.assertIn(nombre, texto)
        # Los derechos de la LOPDP y ante quién reclamar.
        for derecho in ("acceso", "rectificación", "eliminación", "oposición", "portabilidad",
                        "suspensión del tratamiento", "Superintendencia de Protección de Datos"):
            self.assertIn(derecho, texto)

    def test_sin_titular_configurado_lo_dice_en_vez_de_inventarlo(self):
        resp = self.client.get("/api/v1/legal/privacidad/")
        self.assertEqual(set(resp.data["pendientes"]), {"titular", "ruc", "correo"})
        self.assertIn("[pendiente de completar]", _texto(resp.data))

    def test_con_titular_configurado_lo_nombra(self):
        c = PlatformConfiguration.get_solo()
        c.titular_nombre = "Servicios Clínicos Pérez S.A.S."
        c.titular_ruc = "1790000000001"
        c.titular_correo = "privacidad@clinube.com"
        c.proveedor_correo = "Brevo"
        c.save()
        resp = self.client.get("/api/v1/legal/privacidad/")
        self.assertEqual(resp.data["pendientes"], [])
        texto = _texto(resp.data)
        for dato in ("Servicios Clínicos Pérez S.A.S.", "1790000000001", "privacidad@clinube.com", "Brevo"):
            self.assertIn(dato, texto)
        self.assertNotIn("pendiente de completar", texto)

    def test_no_lo_frena_el_cupo_de_anonimo(self):
        # Quien se equivoca varias veces de contraseña y luego pulsa el
        # enlace del aviso tiene que poder leerlo.
        for _ in range(30):
            self.client.post("/api/v1/auth/login/", {"email": "x@x.ec", "password": "x"})
        self.assertEqual(self.client.get("/api/v1/legal/privacidad/").status_code, 200)
        cache.clear()


class CondicionesTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.clinica = Tenant.objects.create(name="Clínica Sur")
        self.admin = User.objects.create_user(
            email="admin@sur.ec", password="superseguro123", role="admin",
            tenant=self.clinica, full_name="Marta Ruiz",
        )
        self.recepcion = User.objects.create_user(
            email="recep@sur.ec", password="superseguro123", role="reception", tenant=self.clinica,
        )

    def _me(self, usuario):
        self.client.force_authenticate(usuario)
        return self.client.get("/api/v1/auth/me/").data

    def _aceptar(self, version=legal.CONDICIONES_VERSION):
        return self.client.post("/api/v1/legal/condiciones/aceptar/", {"version": version}, format="json")

    def test_son_publicas(self):
        resp = self.client.get("/api/v1/legal/condiciones/")
        self.assertEqual(resp.status_code, 200)
        texto = _texto(resp.data)
        self.assertIn("encargada del tratamiento", texto)
        self.assertIn("escanear o probar la seguridad", texto)

    def test_la_administracion_las_tiene_pendientes_hasta_aceptarlas(self):
        self.assertTrue(self._me(self.admin)["condiciones_pendientes"])
        resp = self._aceptar()
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertFalse(self._me(self.admin)["condiciones_pendientes"])

        a = AceptacionCondiciones.objects.get(tenant=self.clinica)
        self.assertEqual(a.version, legal.CONDICIONES_VERSION)
        self.assertEqual((a.nombre, a.correo), ("Marta Ruiz", "admin@sur.ec"))
        self.assertIsNotNone(a.created_at)
        self.assertTrue(AuditLog.objects.filter(action="accept_terms", tenant=self.clinica).exists())

    def test_aceptarlas_dos_veces_no_duplica(self):
        self.client.force_authenticate(self.admin)
        self._aceptar()
        self.assertEqual(self._aceptar().status_code, 200)
        self.assertEqual(AceptacionCondiciones.objects.count(), 1)

    def test_el_resto_del_personal_no_las_acepta_ni_las_tiene_pendientes(self):
        self.assertFalse(self._me(self.recepcion)["condiciones_pendientes"])
        self.assertEqual(self._aceptar().status_code, 403)

    def test_no_se_acepta_una_version_que_no_es_la_vigente(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self._aceptar("1999.01").status_code, 409)
        self.assertFalse(AceptacionCondiciones.objects.exists())

    def test_una_version_nueva_hay_que_aceptarla_otra_vez(self):
        self.client.force_authenticate(self.admin)
        self._aceptar()
        with mock.patch.object(legal, "CONDICIONES_VERSION", "2099.01"):
            self.assertTrue(self._me(self.admin)["condiciones_pendientes"])

    def test_lo_que_acepta_una_clinica_no_vale_para_otra(self):
        self.client.force_authenticate(self.admin)
        self._aceptar()
        otra = Tenant.objects.create(name="Otra")
        admin_otra = User.objects.create_user(
            email="admin@otra.ec", password="superseguro123", role="admin", tenant=otra,
        )
        self.assertTrue(self._me(admin_otra)["condiciones_pendientes"])


class AvisoEntregadoTests(APITestCase):
    def setUp(self):
        self.clinica = Tenant.objects.create(name="Clínica Sur")
        self.recepcion = User.objects.create_user(
            email="recep@sur.ec", password="superseguro123", role="reception",
            tenant=self.clinica, full_name="Laura Paz",
        )
        self.paciente = Patient.objects.create(
            tenant=self.clinica, first_name="Rosa", last_name="Díaz", national_id="1212121212",
        )
        self.url = f"/api/v1/patients/{self.paciente.id}/aviso-privacidad/"
        self.client.force_authenticate(self.recepcion)

    def test_se_registra_con_version_fecha_y_quien(self):
        self.assertFalse(self.client.get(self.url).data["al_dia"])
        resp = self.client.post(self.url, {}, format="json")
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertTrue(resp.data["al_dia"])
        entrega = resp.data["entregas"][0]
        self.assertEqual(entrega["version"], legal.AVISO_VERSION)
        self.assertEqual(entrega["registrado_por"], "Laura Paz")
        self.assertIsNotNone(entrega["fecha"])

    def test_registrarlo_dos_veces_no_duplica(self):
        self.client.post(self.url, {}, format="json")
        self.assertEqual(self.client.post(self.url, {}, format="json").status_code, 200)
        self.assertEqual(AvisoPrivacidadEntregado.objects.count(), 1)

    def test_si_el_aviso_cambia_vuelve_a_estar_pendiente(self):
        self.client.post(self.url, {}, format="json")
        with mock.patch.object(legal, "AVISO_VERSION", "2099.01"):
            datos = self.client.get(self.url).data
        self.assertFalse(datos["al_dia"])
        self.assertEqual(len(datos["entregas"]), 1)

    def test_medio_no_valido(self):
        self.assertEqual(self.client.post(self.url, {"medio": "paloma"}, format="json").status_code, 400)

    def test_no_se_registra_en_un_paciente_de_otra_clinica(self):
        otra = Tenant.objects.create(name="Otra")
        ajeno = Patient.objects.create(tenant=otra, first_name="Luis", last_name="Mora", national_id="1")
        resp = self.client.post(f"/api/v1/patients/{ajeno.id}/aviso-privacidad/", {}, format="json")
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(AvisoPrivacidadEntregado.objects.exists())

    def test_el_doctor_no_lo_registra(self):
        doctor = User.objects.create_user(
            email="doc@sur.ec", password="superseguro123", role="doctor", tenant=self.clinica,
        )
        self.client.force_authenticate(doctor)
        self.assertEqual(self.client.post(self.url, {}, format="json").status_code, 403)
