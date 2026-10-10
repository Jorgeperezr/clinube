"""
La clínica de pruebas y las funciones en prueba.

Lo nuevo nace «en prueba»: solo lo tienen las clínicas de prueba, y en
las demás no existe —ni en la API, ni en Configuración → Módulos— hasta
que el Super Administrador lo publica. Se comprueba el candado (la API),
no lo que enseña el panel, que es cortesía.
"""

from datetime import timedelta
from importlib import import_module
from io import StringIO

from django.apps import apps as registro
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import AuditLog, User
from apps.common.funcionalidades import CATALOGO, NACIDAS_EN_PRUEBA, activa, en_prueba, publicar
from apps.common.models import Tenant

BETA = "temas_personales"
CLAVE = "clave-larga-8gatos"


class FaseDelCatalogoTests(APITestCase):
    def test_elegir_tema_nace_en_prueba(self):
        self.assertEqual(CATALOGO[BETA].get("fase"), "prueba")
        self.assertIn(BETA, NACIDAS_EN_PRUEBA)
        self.assertIn(BETA, en_prueba())

    def test_cada_fase_es_una_de_las_dos(self):
        for clave, d in CATALOGO.items():
            self.assertIn(d.get("fase", "estable"), ("estable", "prueba"), clave)


class SoloEnLaClinicaDePruebasTests(APITestCase):
    def setUp(self):
        self.prueba = Tenant.objects.create(name="Clínica Sandbox", es_prueba=True)
        self.normal = Tenant.objects.create(name="Clínica Cliente")

    def test_la_tiene_la_de_pruebas_y_no_las_demas(self):
        self.assertTrue(activa(self.prueba, BETA))
        self.assertFalse(activa(self.normal, BETA))

    def test_ni_aunque_la_clinica_normal_la_tenga_marcada(self):
        self.normal.funcionalidades = {BETA: True}
        self.normal.save(update_fields=["funcionalidades"])
        self.assertFalse(activa(self.normal, BETA))

    def test_al_publicarla_llega_a_todas_y_se_puede_retirar(self):
        publicar(BETA, True)
        self.assertTrue(activa(self.normal, BETA))
        publicar(BETA, False)
        self.assertFalse(activa(self.normal, BETA))
        self.assertTrue(activa(self.prueba, BETA))

    def test_publicada_respeta_a_la_clinica_que_la_tiene_apagada(self):
        self.normal.funcionalidades = {BETA: False}
        self.normal.save(update_fields=["funcionalidades"])
        publicar(BETA, True)
        self.assertFalse(activa(self.normal, BETA))

    def test_lo_estable_no_se_publica_ni_se_retira(self):
        with self.assertRaises(ValueError):
            publicar("inventario", False)
        self.assertTrue(activa(self.normal, "inventario"))

    def test_modulos_no_le_nombra_lo_que_esta_en_prueba(self):
        admin = User.objects.create_user(email="adm@cliente.ec", password=CLAVE, role="admin",
                                         tenant=self.normal)
        self.client.force_authenticate(admin)
        claves = {m["clave"] for m in self.client.get(reverse("modulos-clinica")).data}
        self.assertNotIn(BETA, claves)
        self.assertIn("inventario", claves)

    def test_a_la_de_pruebas_si_y_dice_que_esta_en_prueba(self):
        admin = User.objects.create_user(email="adm@sandbox.ec", password=CLAVE, role="admin",
                                         tenant=self.prueba)
        self.client.force_authenticate(admin)
        modulos = {m["clave"]: m for m in self.client.get(reverse("modulos-clinica")).data}
        self.assertEqual(modulos[BETA]["fase"], "prueba")
        self.assertTrue(modulos[BETA]["activo"])
        self.assertEqual(modulos["inventario"]["fase"], "estable")

    def test_auth_me_dice_si_es_la_de_pruebas(self):
        de_prueba = User.objects.create_user(email="d@sandbox.ec", password=CLAVE, role="doctor",
                                             tenant=self.prueba)
        de_normal = User.objects.create_user(email="d@cliente.ec", password=CLAVE, role="doctor",
                                             tenant=self.normal)
        self.client.force_authenticate(de_prueba)
        me = self.client.get("/api/v1/auth/me/").data
        self.assertTrue(me["clinica_de_pruebas"])
        self.assertTrue(me["funcionalidades"][BETA])
        self.client.force_authenticate(de_normal)
        me = self.client.get("/api/v1/auth/me/").data
        self.assertFalse(me["clinica_de_pruebas"])
        self.assertFalse(me["funcionalidades"][BETA])


class DesdePlataformaTests(APITestCase):
    def setUp(self):
        self.sa = User.objects.create_user(email="sa@pruebas.ec", password=CLAVE, role="superadmin",
                                           tenant=None)
        self.client.force_authenticate(self.sa)

    def test_se_marca_al_crearla_o_despues_y_queda_constancia(self):
        r = self.client.post(reverse("platform-clinics"), {"name": "Nueva de Pruebas", "es_prueba": True},
                             format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data["es_prueba"])
        r = self.client.post(reverse("platform-clinics"), {"name": "Nueva Normal"}, format="json")
        self.assertFalse(r.data["es_prueba"])
        r = self.client.patch(reverse("platform-clinic-detail", args=[r.data["id"]]),
                              {"es_prueba": True}, format="json")
        self.assertTrue(r.data["es_prueba"])
        registro_ = AuditLog.objects.filter(action="update_clinic").latest("created_at")
        self.assertTrue(registro_.metadata["es_prueba"])

    def test_el_catalogo_trae_la_fase_y_las_clinicas_de_prueba(self):
        Tenant.objects.create(name="Sandbox", es_prueba=True)
        r = self.client.get(reverse("platform-funcionalidades"))
        catalogo = {f["clave"]: f for f in r.data["funcionalidades"]}
        self.assertEqual(catalogo[BETA]["fase"], "prueba")
        self.assertTrue(catalogo[BETA]["nacio_en_prueba"])
        self.assertEqual(catalogo["inventario"]["fase"], "estable")
        self.assertFalse(catalogo["inventario"]["nacio_en_prueba"])
        self.assertEqual([c["name"] for c in r.data["clinicas_de_prueba"]], ["Sandbox"])

    def test_publicar_y_retirar_queda_en_la_auditoria(self):
        url = reverse("platform-funcionalidad", args=[BETA])
        r = self.client.patch(url, {"publicada": True}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["fase"], "estable")
        self.assertNotIn(BETA, en_prueba())
        r = self.client.patch(url, {"publicada": False}, format="json")
        self.assertEqual(r.data["fase"], "prueba")
        acciones = AuditLog.objects.filter(entity_id=BETA).values_list("action", flat=True)
        self.assertCountEqual(acciones, ["publish_feature", "unpublish_feature"])
        r = self.client.get(reverse("platform-audit"))
        self.assertIn("publish_feature", [x["action"] for x in r.data["results"]])

    def test_lo_que_no_se_puede_publicar(self):
        def publicar_(clave, valor=True):
            return self.client.patch(reverse("platform-funcionalidad", args=[clave]),
                                     {"publicada": valor}, format="json").status_code

        self.assertEqual(publicar_("inventario"), 400)
        self.assertEqual(publicar_("inventada"), 404)
        self.assertEqual(publicar_(BETA, "sí"), 400)

    def test_una_clinica_no_publica_nada(self):
        t = Tenant.objects.create(name="Lista", es_prueba=True)
        admin = User.objects.create_user(email="a@lista.ec", password=CLAVE, role="admin", tenant=t)
        self.client.force_authenticate(admin)
        r = self.client.patch(reverse("platform-funcionalidad", args=[BETA]), {"publicada": True},
                              format="json")
        self.assertEqual(r.status_code, 403)


class LaClinicaActualEsLaDePruebasTests(APITestCase):
    def test_la_migracion_marca_la_primera_que_se_creo(self):
        migracion = import_module("apps.common.migrations.0008_clinica_de_pruebas")
        primera = Tenant.objects.create(name="Primera")
        Tenant.objects.create(name="Segunda")
        Tenant.objects.filter(pk=primera.pk).update(created_at=timezone.now() - timedelta(days=30))
        migracion.marcar_la_actual(registro, None)
        self.assertEqual(list(Tenant.objects.filter(es_prueba=True).values_list("name", flat=True)),
                         ["Primera"])

    def test_la_migracion_respeta_una_ya_marcada(self):
        migracion = import_module("apps.common.migrations.0008_clinica_de_pruebas")
        Tenant.objects.create(name="Antigua")
        Tenant.objects.create(name="Elegida", es_prueba=True)
        migracion.marcar_la_actual(registro, None)
        self.assertEqual(list(Tenant.objects.filter(es_prueba=True).values_list("name", flat=True)),
                         ["Elegida"])

    def test_bootstrap_en_una_instalacion_nueva(self):
        call_command("bootstrap", stdout=StringIO())
        self.assertTrue(Tenant.objects.get(name="Clínica Principal").es_prueba)

    def test_bootstrap_no_crea_una_segunda_de_pruebas(self):
        Tenant.objects.create(name="Ya de pruebas", es_prueba=True)
        call_command("bootstrap", stdout=StringIO())
        self.assertFalse(Tenant.objects.get(name="Clínica Principal").es_prueba)

    def test_las_que_se_dan_de_alta_desde_plataforma_no_lo_son(self):
        sa = User.objects.create_user(email="sa@alta.ec", password=CLAVE, role="superadmin", tenant=None)
        self.client.force_authenticate(sa)
        r = self.client.post(reverse("platform-clinics"), {"name": "Cliente Uno"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertFalse(Tenant.objects.get(name="Cliente Uno").es_prueba)
