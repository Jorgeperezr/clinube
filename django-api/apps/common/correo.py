"""
El correo que sale de la plataforma: recuperar la contraseña del
personal y, si se elige ese canal, el código de acceso de la app del
paciente.

Antes había dos configuraciones y solo una funcionaba. Plataforma →
Configuración tenía un apartado «Correo saliente (SMTP)» que se guardaba
y no se usaba nunca: el envío leía únicamente EMAIL_HOST del `.env`. Quien
rellenaba el formulario creía tener el correo listo y los correos no
salían. Ahora:

  1. Si Plataforma tiene servidor SMTP, se usa ese (la contraseña se
     guarda cifrada, ver secretos.py).
  2. Si no, el del `.env` (EMAIL_HOST y compañía).
  3. Si tampoco, el correo se escribe en el registro y no sale.

Con Gmail: servidor smtp.gmail.com, puerto 587, el usuario es la propia
dirección y la contraseña, una «contraseña de aplicación» de 16 letras
(la normal no vale; ver DEPLOY.md, «Correo con Gmail»).
"""

import logging
import smtplib
import socket

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.backends.console import EmailBackend as ConsolaBackend
from django.core.mail.backends.smtp import EmailBackend as SMTPBackend

from apps.common import secretos

logger = logging.getLogger(__name__)


def _contrasena(guardada):
    """La contraseña de Plataforma en claro. Las anteriores al cifrado
    quedaron tal cual: se aceptan hasta que alguien guarde otra."""
    guardada = (guardada or "").strip()
    if guardada.startswith("v1:"):
        return secretos.descifrar(guardada)
    return guardada


def datos_smtp():
    """
    El servidor por el que sale el correo, o None si no hay ninguno.
    `origen` dice de dónde salió: «plataforma» o «entorno».
    """
    from apps.common.models import PlatformConfiguration

    config = PlatformConfiguration.objects.filter().first()
    if config is not None and (config.smtp_host or "").strip():
        puerto = config.smtp_port or 587
        return {
            "origen": "plataforma",
            "host": config.smtp_host.strip(),
            "port": puerto,
            "username": (config.smtp_user or "").strip(),
            "password": _contrasena(config.smtp_password),
            # 465 es SSL desde el principio; el resto (587, 25), STARTTLS.
            "use_ssl": puerto == 465,
            "use_tls": puerto != 465,
        }
    if settings.EMAIL_HOST:
        return {
            "origen": "entorno",
            "host": settings.EMAIL_HOST,
            "port": settings.EMAIL_PORT,
            "username": settings.EMAIL_HOST_USER,
            "password": settings.EMAIL_HOST_PASSWORD,
            "use_ssl": False,
            "use_tls": settings.EMAIL_USE_TLS,
        }
    return None


def remitente(datos):
    """
    Quién firma el correo. Gmail y la mayoría de servidores solo dejan
    enviar como la cuenta con la que se entra: si el remitente por
    omisión es el de relleno (no-responder@localhost), se usa esa cuenta
    con el nombre de la marca delante.
    """
    por_omision = settings.DEFAULT_FROM_EMAIL
    if datos and datos.get("username") and "@localhost" in por_omision and "@" in datos["username"]:
        return f"{settings.MARCA} <{datos['username']}>"
    return por_omision


class CorreoBackend(BaseEmailBackend):
    """EMAIL_BACKEND de la plataforma: elige el servidor en cada envío."""

    def send_messages(self, email_messages):
        datos = datos_smtp()
        if datos is None:
            return ConsolaBackend(fail_silently=self.fail_silently).send_messages(email_messages)
        de = remitente(datos)
        for mensaje in email_messages:
            if not mensaje.from_email or mensaje.from_email == settings.DEFAULT_FROM_EMAIL:
                mensaje.from_email = de
        conexion = SMTPBackend(
            host=datos["host"], port=datos["port"],
            username=datos["username"], password=datos["password"],
            use_tls=datos["use_tls"], use_ssl=datos["use_ssl"],
            timeout=settings.EMAIL_TIMEOUT, fail_silently=self.fail_silently,
        )
        return conexion.send_messages(email_messages)


def explicar_error(exc, datos):
    """Un fallo de envío dicho de forma que se sepa qué tocar."""
    servidor = f"{datos['host']}:{datos['port']}" if datos else "el servidor"
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        texto = f"{servidor} rechazó el usuario o la contraseña."
        if datos and "gmail" in datos["host"].lower():
            texto += (" Con Gmail no vale la contraseña normal: hace falta una «contraseña de "
                      "aplicación» (Cuenta de Google → Seguridad → Verificación en dos pasos → "
                      "Contraseñas de aplicaciones).")
        return texto
    if isinstance(exc, smtplib.SMTPSenderRefused):
        return f"{servidor} no deja enviar con ese remitente: usa como remitente la misma cuenta del usuario."
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return "El servidor rechazó la dirección de destino. Revisa que esté bien escrita."
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return f"{servidor} no respondió a tiempo. Revisa el servidor y el puerto (con Gmail, smtp.gmail.com y 587)."
    if isinstance(exc, (ConnectionError, socket.gaierror, OSError, smtplib.SMTPConnectError,
                        smtplib.SMTPServerDisconnected)):
        return f"No se pudo conectar con {servidor}. Revisa el servidor y el puerto (con Gmail, smtp.gmail.com y 587)."
    return f"El envío falló: {exc}"


def enviar_prueba(destino):
    """
    Manda un correo de prueba. Devuelve (True, texto) o (False, texto con
    lo que hay que arreglar). Nunca lanza.
    """
    datos = datos_smtp()
    if datos is None:
        return False, ("No hay correo configurado: rellena el servidor, el usuario y la contraseña "
                       "en «Correo saliente» y guarda antes de probar.")
    mensaje = EmailMessage(
        subject=f"Prueba de correo de {settings.MARCA}",
        body=(f"Este es un correo de prueba enviado desde {settings.MARCA}.\n\n"
              "Si lo estás leyendo, el correo de la plataforma funciona: la recuperación de "
              "contraseñas y los códigos de acceso por correo llegarán.\n"),
        to=[destino],
    )
    try:
        CorreoBackend(fail_silently=False).send_messages([mensaje])
    except Exception as exc:  # noqa: BLE001 — se traduce y se devuelve, no se oculta
        logger.warning("Correo de prueba fallido: %s", exc)
        return False, explicar_error(exc, datos)
    return True, f"Enviado a {destino} por {datos['host']}. Si no aparece, mira en «Spam»."
