"""
Preferencias propias del profesional: por ahora, usar o no el
odontograma 3D.

Lo que se fija:
  - que cada cual cambie las suyas y SOLO las suyas;
  - que `/auth/me/` las devuelva, que es de donde las lee el panel;
  - que se diga si tienen efecto en la clínica (una preferencia sobre
    algo que la clínica no tiene contratado no hace nada, y el panel
    tiene que poder explicarlo);
  - que no se cuele nada que no sea una preferencia conocida.
"""

from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.common.funcionalidades import normalizar
from apps.common.models import Tenant

RUTA = "/api/v1/auth/me/preferencias/"


class PreferenciasTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica Pref", ruc="1790000098001")
        self.doctor = User.objects.create_user(
            email="doc@pref.ec", password="clave-larga-8gatos", role="doctor", tenant=self.tenant)
        self.otro = User.objects.create_user(
            email="otro@pref.ec", password="clave-larga-8gatos", role="doctor", tenant=self.tenant)
        self.client.force_authenticate(user=self.doctor)

    def test_por_defecto_el_3d_esta_encendido_si_la_clinica_lo_tiene(self):
        # El 3D es adicional: hasta que Plataforma lo active no está disponible.
        r = self.client.get(RUTA)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["preferencias"],
                         {"odontograma_3d": True, "acento": "", "barra_oculta": [], "tema": ""})
        self.assertEqual(r.data["disponibles"], {"odontograma_3d": False})
        self.tenant.funcionalidades = normalizar({"odontograma_3d": True})
        self.tenant.save(update_fields=["funcionalidades"])
        self.assertEqual(self.client.get(RUTA).data["disponibles"], {"odontograma_3d": True})

    def test_apagarlo_se_guarda_y_lo_ve_auth_me(self):
        r = self.client.patch(RUTA, {"odontograma_3d": False}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data["preferencias"]["odontograma_3d"])
        self.doctor.refresh_from_db()
        self.assertEqual(self.doctor.preferencias,
                         {"odontograma_3d": False, "acento": "", "barra_oculta": [], "tema": ""})
        self.assertFalse(self.client.get("/api/v1/auth/me/").data["preferencias"]["odontograma_3d"])

    def test_no_toca_las_de_otro(self):
        self.client.patch(RUTA, {"odontograma_3d": False}, format="json")
        self.otro.refresh_from_db()
        self.assertEqual(self.otro.preferencias, {})
        self.client.force_authenticate(user=self.otro)
        self.assertTrue(self.client.get(RUTA).data["preferencias"]["odontograma_3d"])

    def test_si_la_clinica_no_lo_tiene_se_dice(self):
        self.tenant.funcionalidades = normalizar({"odontograma_3d": False})
        self.tenant.save(update_fields=["funcionalidades"])
        r = self.client.get(RUTA)
        self.assertFalse(r.data["disponibles"]["odontograma_3d"])

    def test_claves_desconocidas_se_rechazan(self):
        r = self.client.patch(RUTA, {"es_admin": True}, format="json")
        self.assertEqual(r.status_code, 400)
        self.doctor.refresh_from_db()
        self.assertEqual(self.doctor.preferencias, {})

    def test_solo_verdadero_o_falso(self):
        r = self.client.patch(RUTA, {"odontograma_3d": "no"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_un_paciente_no_tiene_preferencias_de_panel(self):
        paciente = User.objects.create_user(
            email="pac@pref.ec", password="clave-larga-8gatos", role="patient", tenant=self.tenant)
        self.client.force_authenticate(user=paciente)
        self.assertEqual(self.client.get(RUTA).status_code, 403)
        self.assertEqual(self.client.patch(RUTA, {"odontograma_3d": False}, format="json").status_code, 403)

    def test_sin_sesion_no_hay_acceso(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(RUTA).status_code, 401)


class AparienciaTests(APITestCase):
    """El color de acento y la barra lateral de cada persona."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica Apariencia")
        self.yo = User.objects.create_user(
            email="yo@apariencia.ec", password="clave-larga-8gatos", role="reception", tenant=self.tenant)
        self.client.force_authenticate(user=self.yo)

    def test_se_guardan_y_las_devuelve_auth_me(self):
        r = self.client.patch(RUTA, {"acento": "vino", "barra_oculta": ["inventario", "reportes", "inventario"]},
                              format="json")
        self.assertEqual(r.status_code, 200, r.data)
        prefs = self.client.get("/api/v1/auth/me/").data["preferencias"]
        self.assertEqual(prefs["acento"], "vino")
        self.assertEqual(prefs["barra_oculta"], ["inventario", "reportes"])
        # Y no pisa el resto.
        self.assertTrue(prefs["odontograma_3d"])

    def test_volver_al_color_de_la_clinica(self):
        self.client.patch(RUTA, {"acento": "vino"}, format="json")
        self.assertEqual(self.client.patch(RUTA, {"acento": ""}, format="json").data["preferencias"]["acento"], "")

    def test_formas_no_validas(self):
        for cuerpo in ({"acento": 3}, {"acento": "<script>"}, {"barra_oculta": "inventario"},
                       {"barra_oculta": ["ok", 5]}, {"barra_oculta": [f"s{i}" for i in range(30)]}):
            self.assertEqual(self.client.patch(RUTA, cuerpo, format="json").status_code, 400, cuerpo)

    def test_lo_guardado_a_mano_y_roto_no_rompe_el_panel(self):
        self.yo.preferencias = {"acento": {"x": 1}, "barra_oculta": "todo", "tema": "<script>"}
        self.yo.save(update_fields=["preferencias"])
        prefs = self.client.get(RUTA).data["preferencias"]
        self.assertEqual((prefs["acento"], prefs["barra_oculta"], prefs["tema"]), ("", [], ""))


class TemaDeCadaPersonaTests(APITestCase):
    """
    Elegir el tema del panel: función «temas_personales», en prueba.

    Mientras no se publique, solo se puede en una clínica de prueba; en
    las demás, solo volver al de la clínica.
    """

    def setUp(self):
        self.prueba = Tenant.objects.create(name="Clínica de Pruebas Tema", es_prueba=True)
        self.normal = Tenant.objects.create(name="Clínica Normal Tema")
        self.de_prueba = User.objects.create_user(
            email="p@tema.ec", password="clave-larga-8gatos", role="doctor", tenant=self.prueba)
        self.de_normal = User.objects.create_user(
            email="n@tema.ec", password="clave-larga-8gatos", role="doctor", tenant=self.normal)

    def test_en_la_clinica_de_prueba_se_elige_y_lo_devuelve_auth_me(self):
        self.client.force_authenticate(user=self.de_prueba)
        for tema in ("clinube:bosque", "clinica:principal"):
            r = self.client.patch(RUTA, {"tema": tema}, format="json")
            self.assertEqual(r.status_code, 200, r.data)
            self.assertEqual(self.client.get("/api/v1/auth/me/").data["preferencias"]["tema"], tema)

    def test_en_una_clinica_normal_no_mientras_este_en_prueba(self):
        self.client.force_authenticate(user=self.de_normal)
        r = self.client.patch(RUTA, {"tema": "clinube:bosque"}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertIn("tema", r.data["detail"])
        # Volver al de la clínica sí se puede siempre.
        self.assertEqual(self.client.patch(RUTA, {"tema": ""}, format="json").status_code, 200)

    def test_publicada_la_tienen_todas(self):
        from apps.common.funcionalidades import publicar

        publicar("temas_personales", True)
        self.client.force_authenticate(user=self.de_normal)
        self.assertEqual(self.client.patch(RUTA, {"tema": "clinube:vino"}, format="json").status_code, 200)

    def test_formas_no_validas(self):
        self.client.force_authenticate(user=self.de_prueba)
        for tema in ("bosque", "otro:bosque", "clinica:<b>", "clinube:" + "x" * 40, 7):
            self.assertEqual(self.client.patch(RUTA, {"tema": tema}, format="json").status_code, 400, tema)
