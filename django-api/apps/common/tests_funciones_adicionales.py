"""
Funciones incluidas y adicionales.

El odontograma 3D y las rachas y logros los pidió una clínica cliente:
se agregan a pedido desde Plataforma y una clínica nueva no los trae.
Lo que se fija aquí es que eso siga siendo así, que el catálogo lo diga
para que Plataforma lo pinte solo, y que la app del paciente no enseñe
logros donde no los hay.
"""

from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.common.funcionalidades import CATALOGO, POR_DEFECTO, activa, normalizar
from apps.common.models import Tenant
from apps.patients.models import Patient

ADICIONALES = {"odontograma_3d", "logros"}


class CatalogoTests(APITestCase):
    def test_el_3d_y_los_logros_son_adicionales_y_apagados(self):
        for clave in ADICIONALES:
            self.assertEqual(CATALOGO[clave]["tipo"], "adicional")
            self.assertFalse(POR_DEFECTO[clave])
            self.assertTrue(CATALOGO[clave].get("origen"))

    def test_cada_funcion_dice_su_tipo(self):
        for clave, d in CATALOGO.items():
            self.assertIn(d["tipo"], ("incluida", "adicional"), clave)
            if d["tipo"] == "adicional":
                self.assertFalse(d["por_defecto"], f"{clave}: una adicional no viene de fábrica")

    def test_una_clinica_nueva_desde_plataforma_no_los_trae(self):
        sa = User.objects.create_user(email="sa@p.ec", password="superseguro123", role="superadmin", tenant=None)
        self.client.force_authenticate(sa)
        r = self.client.post("/api/v1/platform/clinics/", {"name": "Clínica Nueva"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        tenant = Tenant.objects.get(name="Clínica Nueva")
        for clave in ADICIONALES:
            self.assertFalse(activa(tenant, clave), clave)
        self.assertTrue(activa(tenant, "inventario"))

    def test_y_se_pueden_agregar_al_crearla(self):
        sa = User.objects.create_user(email="sa@p.ec", password="superseguro123", role="superadmin", tenant=None)
        self.client.force_authenticate(sa)
        r = self.client.post("/api/v1/platform/clinics/", {
            "name": "Clínica Completa", "funcionalidades": {"logros": True, "odontograma_3d": True},
        }, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        tenant = Tenant.objects.get(name="Clínica Completa")
        self.assertTrue(activa(tenant, "logros") and activa(tenant, "odontograma_3d"))

    def test_plataforma_lee_el_catalogo_de_la_api(self):
        sa = User.objects.create_user(email="sa@p.ec", password="superseguro123", role="superadmin", tenant=None)
        self.client.force_authenticate(sa)
        r = self.client.get(reverse("platform-funcionalidades"))
        self.assertEqual(r.status_code, 200)
        claves = {f["clave"]: f for f in r.data["funcionalidades"]}
        self.assertEqual(set(claves), set(CATALOGO))
        self.assertEqual(claves["logros"]["tipo"], "adicional")
        self.assertIn("adicional", r.data["tipos"])

    def test_el_catalogo_no_es_para_las_clinicas(self):
        t = Tenant.objects.create(name="C")
        admin = User.objects.create_user(email="a@c.ec", password="superseguro123", role="admin", tenant=t)
        self.client.force_authenticate(admin)
        self.assertEqual(self.client.get(reverse("platform-funcionalidades")).status_code, 403)

    def test_la_clinica_ve_las_adicionales_que_no_tiene(self):
        # Configuración → Módulos se las enseña para que pueda pedirlas.
        t = Tenant.objects.create(name="C")
        admin = User.objects.create_user(email="a@c.ec", password="superseguro123", role="admin", tenant=t)
        self.client.force_authenticate(admin)
        modulos = {m["clave"]: m for m in self.client.get("/api/v1/config/modulos/").data}
        self.assertEqual(modulos["logros"]["tipo"], "adicional")
        self.assertFalse(modulos["logros"]["contratado"])
        self.assertEqual(modulos["inventario"]["tipo"], "incluida")


class LogrosEnLaAppTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica App")
        self.user = User.objects.create_user(email="p@app.ec", password="superseguro123",
                                             role="patient", tenant=self.tenant)
        Patient.objects.create(tenant=self.tenant, first_name="Ana", last_name="Vega",
                               national_id="1", user=self.user)
        self.client.force_authenticate(self.user)

    def test_sin_la_funcion_la_app_no_ve_logros(self):
        self.assertEqual(self.client.get("/api/v1/app/clinica/").data["funciones"], {"logros": False})
        r = self.client.get("/api/v1/app/logros/")
        self.assertEqual((r.status_code, r.data), (200, []))

    def test_con_la_funcion_si(self):
        self.tenant.funcionalidades = normalizar({"logros": True})
        self.tenant.save(update_fields=["funcionalidades"])
        self.assertEqual(self.client.get("/api/v1/app/clinica/").data["funciones"], {"logros": True})
