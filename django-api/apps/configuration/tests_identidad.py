"""
Paleta, logotipos y temas de una clínica.

Se dan al crearla (Plataforma) o después (Configuración). Con la paleta
se generan los temas de la clínica, y el principal pasa a ser el suyo si
todavía tenía el de fábrica. Lo que no es imagen no se guarda, y un
error no se lleva por delante el logotipo que ya había.
"""

import io
import uuid

from django.test import SimpleTestCase
from django.urls import reverse
from PIL import Image, ImageDraw
from rest_framework.test import APITestCase

from apps.accounts.models import AuditLog, User
from apps.common.models import Tenant
from apps.configuration.branding import extract_palette
from apps.configuration.models import ClinicBranding
from apps.configuration.temas import resolver
from apps.configuration.temas_clinica import (
    como_tema_de_la_clinica,
    contraste,
    generar_temas,
    normalizar_paleta,
)

CLAVE = "clave-larga-8gatos"
MARCA = ["#0e7490", "#f59e0b", "#0b1220"]


def _png(color=(14, 116, 144), nombre="logo.png"):
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(buf, format="PNG")
    buf.seek(0)
    buf.name = nombre
    return buf


class PaletaTests(SimpleTestCase):
    def test_lista_o_texto_y_formas_cortas(self):
        self.assertEqual(normalizar_paleta("#0E7490, 67e8f9; #abc"), ["#0e7490", "#67e8f9", "#aabbcc"])
        self.assertEqual(normalizar_paleta(["#0e7490", "#0E7490"]), ["#0e7490"])
        self.assertEqual(normalizar_paleta(""), [])
        self.assertEqual(normalizar_paleta(None), [])

    def test_lo_que_no_es_un_color_se_dice(self):
        with self.assertRaisesMessage(ValueError, "azul"):
            normalizar_paleta(["#0e7490", "azul"])
        with self.assertRaises(ValueError):
            normalizar_paleta([f"#{i}{i}{i}{i}{i}{i}" for i in range(7)])
        with self.assertRaises(ValueError):
            normalizar_paleta({"principal": "#0e7490"})


class GenerarTemasTests(SimpleTestCase):
    def test_principal_alterno_y_sobrio(self):
        temas = generar_temas(MARCA)
        self.assertEqual([t["clave"] for t in temas], ["principal", "alterno", "sobrio"])
        principal, alterno = temas[0], temas[1]
        self.assertEqual((principal["primary"], principal["secondary"]), ("#0e7490", "#f59e0b"))
        self.assertEqual((alterno["primary"], alterno["secondary"]), ("#f59e0b", "#0e7490"))
        # El color muy oscuro de la paleta va a la navegación.
        self.assertEqual(principal["nav"], "#0b1220")
        for tema in temas:
            self.assertTrue(tema["nombre"] and tema["descripcion"], tema)

    def test_la_misma_paleta_da_siempre_los_mismos_temas(self):
        self.assertEqual(generar_temas(MARCA), generar_temas(list(MARCA)))

    def test_con_un_solo_color(self):
        temas = generar_temas(["#7b1e3c"])
        self.assertEqual(temas[0]["primary"], "#7b1e3c")
        self.assertNotIn("alterno", [t["clave"] for t in temas])
        self.assertNotEqual(temas[0]["secondary"], temas[0]["primary"])

    def test_una_paleta_sin_color_da_un_tema_en_grises(self):
        temas = generar_temas(["#ffffff", "#000000", "#555555"])
        self.assertEqual(len(temas), 1)
        for color in (temas[0]["primary"], temas[0]["secondary"]):
            canales = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
            self.assertLessEqual(max(canales) - min(canales), 24, color)

    def test_la_navegacion_lleva_texto_blanco_y_se_lee(self):
        for paleta in (MARCA, ["#1d6b3c"], ["#ff0000", "#00ff00"], ["#334155"], ["#fde68a"]):
            for tema in generar_temas(paleta):
                if "nav" in tema:
                    self.assertGreaterEqual(contraste(tema["nav"], "#ffffff"), 7, tema)

    def test_la_app_y_los_documentos_entienden_un_tema_de_la_clinica(self):
        tema = como_tema_de_la_clinica(generar_temas(MARCA)[0])
        self.assertEqual(tema["preset"], "clinica:principal")
        self.assertEqual(resolver(tema), ("#0e7490", "#f59e0b"))


def _logo_de_dos_colores(fondo=(0, 0, 0, 0), suavizado=True):
    """Dos círculos que se tocan sobre fondo transparente. Dibujados en
    grande y reducidos, los bordes quedan suavizados, con mezclas de los
    dos colores."""
    lado = 4 if suavizado else 1
    imagen = Image.new("RGBA", (100 * lado, 50 * lado), fondo)
    dibujo = ImageDraw.Draw(imagen)
    dibujo.ellipse([v * lado / 4 for v in (10, 10, 190, 190)], fill=(109, 40, 217, 255))
    dibujo.ellipse([v * lado / 4 for v in (170, 40, 290, 160)], fill=(249, 115, 22, 255))
    if suavizado:
        imagen = imagen.resize((100, 50), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    imagen.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _tono(hexa):
    import colorsys
    r, g, b = (int(hexa[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hls(r, g, b)[0]


class ColoresDelLogotipoTests(SimpleTestCase):
    def test_los_de_la_marca_y_no_la_mezcla_de_los_bordes(self):
        colores = extract_palette(_logo_de_dos_colores())["colores"]
        self.assertEqual(len(colores), 2, colores)
        self.assertAlmostEqual(_tono(colores[0]), _tono("#6d28d9"), delta=0.03)
        self.assertAlmostEqual(_tono(colores[1]), _tono("#f97316"), delta=0.03)

    def test_lo_transparente_no_aporta_colores(self):
        # Hay programas que dejan un color debajo de lo transparente.
        datos = extract_palette(_logo_de_dos_colores(fondo=(0, 200, 0, 0), suavizado=False))
        self.assertAlmostEqual(_tono(datos["primary"]), _tono("#6d28d9"), delta=0.03)
        for color in datos["colores"]:
            self.assertGreater(abs(_tono(color) - _tono("#00c800")), 0.1, datos)


class IdentidadDesdePlataformaTests(APITestCase):
    def setUp(self):
        self.sa = User.objects.create_user(email="sa@identidad.ec", password=CLAVE, role="superadmin",
                                           tenant=None)
        self.client.force_authenticate(self.sa)
        r = self.client.post(reverse("platform-clinics"), {"name": "Clínica Con Marca"}, format="json")
        self.clinica = r.data["id"]
        self.url = reverse("platform-clinic-identidad", args=[self.clinica])

    def test_paleta_y_logotipos_al_crearla(self):
        r = self.client.patch(self.url, {
            "paleta": '["#0e7490", "#f59e0b", "#0b1220"]',
            "logo": _png(), "logo_oscuro": _png((240, 240, 240), "oscuro.png"),
            "icono": _png(nombre="icono.png"),
        }, format="multipart")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["paleta"], MARCA)
        self.assertEqual([t["clave"] for t in r.data["temas"]], ["principal", "alterno", "sobrio"])
        # Tenía el de fábrica: pasa al principal de su paleta.
        self.assertEqual(r.data["theme"]["preset"], "clinica:principal")
        for campo in ("logo_url", "logo_oscuro_url", "icono_url"):
            self.assertTrue(r.data[campo], campo)

        # Su personal lo ve en la identidad de su clínica.
        recepcion = User.objects.create_user(email="r@marca.ec", password=CLAVE, role="reception",
                                             tenant=Tenant.objects.get(pk=self.clinica))
        self.client.force_authenticate(recepcion)
        propia = self.client.get(reverse("clinic-branding")).data
        self.assertEqual(propia["theme"]["primary"], "#0e7490")
        self.assertEqual(len(propia["temas"]), 3)
        self.assertTrue(propia["icono_url"] and propia["logo_oscuro_url"])

        registro = AuditLog.objects.get(action="update_clinic_identity")
        self.assertEqual(set(registro.metadata["cambios"]), {"paleta", "logo", "logo_oscuro", "icono"})

    def test_si_la_clinica_ya_eligio_otro_tema_no_se_pisa(self):
        ClinicBranding.objects.create(tenant_id=self.clinica, theme={"preset": "bosque"})
        r = self.client.patch(self.url, {"paleta": ["#0e7490"]}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["theme"]["preset"], "bosque")
        self.assertEqual(r.data["temas"][0]["clave"], "principal")

    def test_con_uno_de_sus_temas_se_recalcula_al_cambiar_la_paleta(self):
        self.client.patch(self.url, {"paleta": ["#0e7490", "#f59e0b"]}, format="json")
        r = self.client.patch(self.url, {"paleta": ["#7b1e3c", "#f0c9d4"]}, format="json")
        self.assertEqual(r.data["theme"]["preset"], "clinica:principal")
        self.assertEqual(r.data["theme"]["primary"], "#7b1e3c")

    def test_sin_paleta_vuelve_al_de_clinube(self):
        self.client.patch(self.url, {"paleta": ["#0e7490"]}, format="json")
        r = self.client.patch(self.url, {"paleta": []}, format="json")
        self.assertEqual((r.data["paleta"], r.data["temas"]), ([], []))
        self.assertEqual(r.data["theme"]["preset"], "default")

    def test_lo_que_no_es_imagen_no_se_guarda_ni_borra_lo_que_habia(self):
        antes = self.client.patch(self.url, {"logo": _png()}, format="multipart").data["logo_url"]
        svg = io.BytesIO(b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>')
        svg.name = "logo.svg"
        r = self.client.patch(self.url, {"logo": svg}, format="multipart")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.client.get(self.url).data["logo_url"], antes)

    def test_un_color_mal_escrito(self):
        r = self.client.patch(self.url, {"paleta": ["#0e7490", "verde"]}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("verde", r.data["detail"])

    def test_quitar_un_logotipo(self):
        self.client.patch(self.url, {"icono": _png()}, format="multipart")
        r = self.client.patch(self.url, {"icono_clear": "true"}, format="multipart")
        self.assertIsNone(r.data["icono_url"])

    def test_solo_el_super_administrador(self):
        admin = User.objects.create_user(email="a@marca.ec", password=CLAVE, role="admin",
                                         tenant=Tenant.objects.get(pk=self.clinica))
        self.client.force_authenticate(admin)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.patch(self.url, {"paleta": ["#000000"]}, format="json").status_code, 403)

    def test_una_clinica_que_no_existe(self):
        url = reverse("platform-clinic-identidad", args=[uuid.uuid4()])
        self.assertEqual(self.client.get(url).status_code, 404)


class PrevisualizarTests(APITestCase):
    def setUp(self):
        self.sa = User.objects.create_user(email="sa@previa.ec", password=CLAVE, role="superadmin",
                                           tenant=None)
        self.client.force_authenticate(self.sa)

    def test_con_paleta_y_sin_guardar_nada(self):
        r = self.client.post(reverse("temas-previsualizar"), {"paleta": ["#0e7490", "#f59e0b"]},
                             format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["temas"][0]["primary"], "#0e7490")
        self.assertFalse(ClinicBranding.objects.exists())

    def test_sin_paleta_sale_del_logotipo(self):
        r = self.client.post(reverse("temas-previsualizar"), {"logo": _png((123, 30, 60))},
                             format="multipart")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data["paleta"])
        self.assertEqual(r.data["temas"][0]["primary"], r.data["paleta"][0])

    def test_tambien_para_la_administracion_de_una_clinica_pero_no_para_el_resto(self):
        t = Tenant.objects.create(name="Previa")
        for rol, esperado in (("admin", 200), ("doctor", 403)):
            u = User.objects.create_user(email=f"{rol}@previa.ec", password=CLAVE, role=rol, tenant=t)
            self.client.force_authenticate(u)
            r = self.client.post(reverse("temas-previsualizar"), {"paleta": ["#000000"]}, format="json")
            self.assertEqual(r.status_code, esperado, rol)


class IdentidadDesdeConfiguracionTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica Config Marca")
        self.admin = User.objects.create_user(email="a@cm.ec", password=CLAVE, role="admin",
                                              tenant=self.tenant)
        self.client.force_authenticate(self.admin)

    def test_da_su_paleta_y_elige_uno_de_sus_temas(self):
        r = self.client.patch(reverse("clinic-branding"), {"paleta": ["#0e7490", "#f59e0b"]}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["theme"]["preset"], "clinica:principal")
        r = self.client.patch(reverse("clinic-branding"),
                              {"theme": {"preset": "clinica:alterno", "primary": "#000000"}}, format="json")
        # Se guarda con SUS colores, no con los que mande el panel.
        self.assertEqual(r.data["theme"]["primary"], "#f59e0b")

    def test_un_tema_que_no_es_de_la_clinica(self):
        r = self.client.patch(reverse("clinic-branding"), {"theme": {"preset": "clinica:alterno"}},
                              format="json")
        self.assertEqual(r.status_code, 400)

    def test_el_logotipo_para_fondo_oscuro_y_el_icono(self):
        r = self.client.patch(reverse("clinic-branding"), {"logo_oscuro": _png(), "icono": _png()},
                              format="multipart")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data["logo_oscuro_url"] and r.data["icono_url"])

    def test_la_paleta_y_los_temas_no_se_escriben_sueltos(self):
        # Los temas salen siempre de la paleta: mandarlos a mano no hace nada.
        self.client.patch(reverse("clinic-branding"),
                          {"temas": [{"clave": "inventado", "primary": "#000000"}]}, format="json")
        self.assertEqual(self.client.get(reverse("clinic-branding")).data["temas"], [])
