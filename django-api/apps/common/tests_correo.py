"""
El correo de la plataforma (apps/common/correo.py): sale por el servidor
de Plataforma → Configuración o, si no lo hay, por el del entorno.
"""

import importlib
import smtplib
from unittest import mock

from django.apps import apps as registro_apps
from django.core.mail import EmailMessage
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import AuditLog, User
from apps.common import correo
from apps.common.models import PlatformConfiguration
from apps.common.secretos import cifrar

GMAIL = {"smtp_host": "smtp.gmail.com", "smtp_port": 587, "smtp_user": "clinube.ec@gmail.com"}


def _plataforma(**campos):
    config = PlatformConfiguration.get_solo()
    for campo, valor in campos.items():
        setattr(config, campo, valor)
    config.save()
    return config


@override_settings(EMAIL_HOST="", DEFAULT_FROM_EMAIL="Clinube <no-responder@localhost>")
class DatosSMTPTests(TestCase):
    def test_sin_nada_no_hay_correo(self):
        self.assertIsNone(correo.datos_smtp())

    @override_settings(EMAIL_HOST="smtp.entorno.ec", EMAIL_PORT=2525, EMAIL_HOST_USER="u",
                       EMAIL_HOST_PASSWORD="p", EMAIL_USE_TLS=True)
    def test_el_del_entorno(self):
        datos = correo.datos_smtp()
        self.assertEqual((datos["origen"], datos["host"], datos["port"]), ("entorno", "smtp.entorno.ec", 2525))

    @override_settings(EMAIL_HOST="smtp.entorno.ec")
    def test_el_de_plataforma_manda_y_la_contrasena_se_descifra(self):
        _plataforma(**GMAIL, smtp_password=cifrar("abcd efgh ijkl mnop"))
        datos = correo.datos_smtp()
        self.assertEqual((datos["origen"], datos["host"]), ("plataforma", "smtp.gmail.com"))
        self.assertEqual(datos["password"], "abcd efgh ijkl mnop")
        self.assertEqual((datos["use_tls"], datos["use_ssl"]), (True, False))

    def test_puerto_465_es_ssl(self):
        _plataforma(smtp_host="smtp.gmail.com", smtp_port=465)
        datos = correo.datos_smtp()
        self.assertEqual((datos["use_tls"], datos["use_ssl"]), (False, True))

    def test_una_contrasena_antigua_en_claro_sigue_valiendo(self):
        _plataforma(**GMAIL, smtp_password="enclaro")
        self.assertEqual(correo.datos_smtp()["password"], "enclaro")


@override_settings(EMAIL_HOST="", DEFAULT_FROM_EMAIL="Clinube <no-responder@localhost>")
class BackendTests(TestCase):
    def test_sin_servidor_se_escribe_en_el_registro(self):
        with mock.patch("apps.common.correo.ConsolaBackend") as consola:
            correo.CorreoBackend().send_messages([EmailMessage("a", "b", to=["x@y.ec"])])
        consola.return_value.send_messages.assert_called_once()

    def test_con_gmail_sale_por_gmail_y_firmado_con_la_cuenta(self):
        _plataforma(**GMAIL, smtp_password=cifrar("secreta"))
        mensaje = EmailMessage("a", "b", to=["x@y.ec"])
        with mock.patch("apps.common.correo.SMTPBackend") as smtp:
            correo.CorreoBackend().send_messages([mensaje])
        argumentos = smtp.call_args.kwargs
        self.assertEqual((argumentos["host"], argumentos["port"], argumentos["username"], argumentos["password"]),
                         ("smtp.gmail.com", 587, "clinube.ec@gmail.com", "secreta"))
        self.assertEqual(mensaje.from_email, "Clinube <clinube.ec@gmail.com>")

    @override_settings(DEFAULT_FROM_EMAIL="Clinube <hola@clinube.com>")
    def test_un_remitente_propio_se_respeta(self):
        _plataforma(**GMAIL)
        mensaje = EmailMessage("a", "b", to=["x@y.ec"])
        with mock.patch("apps.common.correo.SMTPBackend"):
            correo.CorreoBackend().send_messages([mensaje])
        self.assertEqual(mensaje.from_email, "Clinube <hola@clinube.com>")


@override_settings(EMAIL_HOST="")
class PruebaTests(TestCase):
    def test_sin_configurar(self):
        ok, texto = correo.enviar_prueba("a@b.ec")
        self.assertFalse(ok)
        self.assertIn("No hay correo configurado", texto)

    def test_gmail_con_la_contrasena_normal(self):
        _plataforma(**GMAIL, smtp_password=cifrar("la-normal"))
        with mock.patch("apps.common.correo.SMTPBackend") as smtp:
            smtp.return_value.send_messages.side_effect = smtplib.SMTPAuthenticationError(535, b"no")
            ok, texto = correo.enviar_prueba("a@b.ec")
        self.assertFalse(ok)
        self.assertIn("contraseña de aplicación", texto)

    def test_servidor_que_no_existe(self):
        _plataforma(smtp_host="smtp.noexiste.ec", smtp_port=587)
        with mock.patch("apps.common.correo.SMTPBackend") as smtp:
            smtp.return_value.send_messages.side_effect = OSError("Name or service not known")
            ok, texto = correo.enviar_prueba("a@b.ec")
        self.assertFalse(ok)
        self.assertIn("No se pudo conectar con smtp.noexiste.ec:587", texto)

    def test_sale(self):
        _plataforma(**GMAIL)
        with mock.patch("apps.common.correo.SMTPBackend"):
            ok, texto = correo.enviar_prueba("a@b.ec")
        self.assertTrue(ok)
        self.assertIn("Enviado a a@b.ec", texto)


@override_settings(EMAIL_HOST="")
class PlataformaTests(APITestCase):
    def setUp(self):
        self.sa = User.objects.create_user(email="sa@clinube.ec", password="superseguro123",
                                           role="superadmin", tenant=None)
        self.client.force_authenticate(self.sa)

    def test_correo_de_prueba_a_quien_lo_pide(self):
        _plataforma(**GMAIL)
        with mock.patch("apps.common.correo.SMTPBackend") as smtp:
            r = self.client.post("/api/v1/platform/config/correo-de-prueba/", {})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(smtp.return_value.send_messages.call_args.args[0][0].to, ["sa@clinube.ec"])
        self.assertTrue(AuditLog.objects.filter(action="test_email").exists())

    def test_correo_de_prueba_sin_configurar(self):
        r = self.client.post("/api/v1/platform/config/correo-de-prueba/", {"destino": "a@b.ec"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("No hay correo configurado", r.data["detail"])

    def test_solo_el_super_administrador(self):
        tenant_user = User.objects.create_user(email="adm@c.ec", password="superseguro123", role="admin")
        self.client.force_authenticate(tenant_user)
        self.assertEqual(self.client.post("/api/v1/platform/config/correo-de-prueba/", {}).status_code, 403)

    def test_la_configuracion_dice_por_donde_sale(self):
        self.assertEqual(self.client.get("/api/v1/platform/config/").data["correo_origen"], "")
        self.client.patch("/api/v1/platform/config/", GMAIL, format="json")
        datos = self.client.get("/api/v1/platform/config/").data
        self.assertEqual((datos["correo_origen"], datos["canal_codigo_paciente"]), ("plataforma", "whatsapp"))

    def test_no_se_pasa_a_correo_sin_correo(self):
        r = self.client.patch("/api/v1/platform/config/", {"canal_codigo_paciente": "correo"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("correo de prueba", str(r.data["error"]["details"]["canal_codigo_paciente"]))
        r = self.client.patch("/api/v1/platform/config/", {**GMAIL, "canal_codigo_paciente": "correo"},
                              format="json")
        self.assertEqual(r.status_code, 200, r.data)


class MigracionTests(TestCase):
    def test_cifra_la_contrasena_que_estaba_en_claro(self):
        from apps.common.secretos import descifrar

        _plataforma(smtp_password="enclaro")
        migracion = importlib.import_module("apps.common.migrations.0009_canal_y_correo")
        migracion.cifrar_contrasena_smtp(registro_apps, None)
        guardada = PlatformConfiguration.get_solo().smtp_password
        self.assertTrue(guardada.startswith("v1:"))
        self.assertEqual(descifrar(guardada), "enclaro")
        # Dos veces no la cifra dos veces.
        migracion.cifrar_contrasena_smtp(registro_apps, None)
        self.assertEqual(descifrar(PlatformConfiguration.get_solo().smtp_password), "enclaro")
