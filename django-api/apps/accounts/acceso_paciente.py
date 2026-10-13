"""
Cómo entra el paciente en la app: con quién se identifica y por dónde le
llega el código.

Se identifica con su teléfono o con su correo, el que pida la app. El
código le llega por el canal que haya elegido la plataforma
(Plataforma → Configuración): WhatsApp o correo. Las dos cosas van por
separado a propósito: si un día la plataforma pasa de WhatsApp a correo,
una app ya instalada que todavía pide el teléfono sigue funcionando, y
el código le llega al correo de su ficha.

Cada correo da acceso a una sola ficha, igual que cada teléfono: la
cuenta lleva el correo en `User.email`, que es único. Las cuentas que se
activaron antes con el teléfono no lo tienen; a esas se las encuentra
por el correo de su ficha.
"""

import logging

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from apps.accounts.models import User
from apps.common.telefonos import normalizar_telefono

logger = logging.getLogger(__name__)

WHATSAPP = "whatsapp"
CORREO = "correo"


def canal_codigo():
    """El canal elegido en Plataforma; WhatsApp si no hay configuración."""
    from apps.common.models import PlatformConfiguration

    config = PlatformConfiguration.objects.filter().first()
    return getattr(config, "canal_codigo_paciente", "") or WHATSAPP


def normalizar_correo(texto):
    """El correo en minúsculas y sin espacios, o "" si no es un correo."""
    correo = (texto or "").strip().lower()
    if not correo:
        return ""
    try:
        validate_email(correo)
    except ValidationError:
        return ""
    return correo


def ocultar(correo):
    """«jo***@gmail.com»: suficiente para reconocerlo sin publicarlo."""
    usuario, _, dominio = (correo or "").partition("@")
    if not dominio:
        return ""
    return f"{usuario[:2]}***@{dominio}"


def _pacientes():
    return User.objects.filter(role=User.Role.PATIENT, is_active=True,
                               patient_profile__isnull=False).select_related("tenant", "patient_profile")


def cuenta_por_correo(correo):
    """
    La cuenta de paciente de ese correo. Devuelve (cuenta, None) o
    (None, motivo) cuando hay más de una y no se sabe cuál es.
    """
    cuenta = _pacientes().filter(email__iexact=correo).first()
    if cuenta is not None:
        return cuenta, None
    # Activadas con el teléfono antes de que la cuenta guardara el correo.
    candidatas = list(_pacientes().filter(email__isnull=True, patient_profile__email__iexact=correo)[:2])
    if len(candidatas) > 1:
        return None, ("Ese correo está en las fichas de varios pacientes. Pide en la recepción "
                      "de tu clínica que lo revisen, o entra con tu teléfono.")
    return (candidatas[0] if candidatas else None), None


def cuenta_por_telefono(telefono):
    return _pacientes().filter(phone=telefono).first()


def identificar(datos):
    """
    La cuenta a partir de lo que mande la app: {"phone": …} o {"email": …}.
    Devuelve (cuenta, error); error es un texto para el paciente.
    """
    if datos.get("email"):
        correo = normalizar_correo(datos["email"])
        if not correo:
            return None, "Escribe tu correo completo, por ejemplo nombre@gmail.com."
        return cuenta_por_correo(correo)
    telefono = normalizar_telefono(datos.get("phone") or "")
    if not telefono:
        return None, "Escribe tu número de teléfono completo, por ejemplo 099 123 4567."
    return cuenta_por_telefono(telefono), None


def correo_de(cuenta):
    """Adónde se manda el código por correo: el de la cuenta o el de su ficha."""
    if cuenta.email:
        return cuenta.email
    ficha = getattr(cuenta, "patient_profile", None)
    return normalizar_correo(getattr(ficha, "email", ""))


def enviar_codigo_por_correo(cuenta, codigo, minutos):
    """Manda el código. Lanza si el correo no sale: quien llama lo dice."""
    from apps.accounts.correos_paciente import enviar_codigo

    enviar_codigo(cuenta, codigo, minutos, correo_de(cuenta))
