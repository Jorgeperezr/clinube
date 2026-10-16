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
    """El canal elegido en Plataforma; correo si no hay configuración."""
    from apps.common.models import PlatformConfiguration

    config = PlatformConfiguration.objects.filter().first()
    return getattr(config, "canal_codigo_paciente", "") or CORREO


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
    # También las cuentas que el paciente creó él mismo y que su clínica
    # aún no enlaza con la ficha: entran y ven que esperan el acceso.
    return User.objects.filter(role=User.Role.PATIENT, is_active=True).select_related("tenant")


def cuenta_por_correo(correo):
    """
    La cuenta de paciente de ese correo. Devuelve (cuenta, None) o
    (None, motivo) cuando hay más de una y no se sabe cuál es.
    """
    cuenta = _pacientes().filter(email__iexact=correo).first()
    if cuenta is not None:
        return cuenta, None
    # Activadas con el teléfono antes de que la cuenta guardara el correo.
    candidatas = list(_pacientes().filter(email__isnull=True, patient_profile__isnull=False,
                                          patient_profile__email__iexact=correo)[:2])
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


def canal_de_clinica(tenant):
    """
    WhatsApp solo si la plataforma lo usa (Plataforma → Configuración) Y
    la clínica tiene contratada la función de WhatsApp. En todo lo demás,
    correo: es el canal de todos y no le cuesta nada a la clínica.
    """
    from apps.common.funcionalidades import activa

    if canal_codigo() == WHATSAPP and tenant is not None and activa(tenant, "whatsapp"):
        return WHATSAPP
    return CORREO


def canal_para(datos, cuenta):
    """
    Por dónde mandar el código a esta cuenta. Por WhatsApp cuando su
    clínica lo tiene y la cuenta tiene teléfono; si no, por correo, también
    a una app antigua que todavía pide el teléfono.
    """
    if canal_de_clinica(cuenta.tenant if cuenta.tenant_id else None) == WHATSAPP and cuenta.phone:
        return WHATSAPP
    return CORREO


def crear_cuenta_propia(correo, nombre):
    """
    La cuenta que el paciente crea él mismo, sin clínica todavía. Cuando su
    clínica active el acceso en la ficha con este correo, se enlaza sola
    (apps/patients/acceso_app.py busca la cuenta por el correo).

    Si ya hubo una cuenta de paciente con ese correo y se le quitó el
    acceso, se reutiliza en vez de chocar con el correo único.
    """
    cuenta = User.objects.filter(email__iexact=correo, role=User.Role.PATIENT).first()
    if cuenta is not None:
        if not cuenta.is_active and not hasattr(cuenta, "patient_profile"):
            cuenta.is_active, cuenta.tenant = True, None
            cuenta.full_name = nombre or cuenta.full_name
            cuenta.save(update_fields=["is_active", "tenant", "full_name"])
        return cuenta
    return User.objects.create_user(email=correo, role=User.Role.PATIENT, tenant=None,
                                    full_name=(nombre or "").strip()[:150])
