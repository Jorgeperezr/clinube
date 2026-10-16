"""
Correos al equipo de una clínica, con la marca de SU clínica (logotipo,
color y datos de contacto), igual que los que reciben los pacientes
(correos_paciente.py):

  · la invitación al darle de alta: elige tu contraseña o entra con Google;
  · el enlace para recuperar la contraseña.

Antes la recuperación salía como texto plano firmado por la plataforma, y
quien la recibía no sabía de qué clínica era.
"""

from html import escape

from django.conf import settings

from apps.accounts.correos_paciente import SUAVE, _boton, _documento, _enviar, marca_de

ROLES = {"admin": "administración", "reception": "recepción", "doctor": "profesional",
         "auxiliary": "auxiliar"}


def _p(html):
    return f'<p style="margin:0 0 14px;font-size:15px;line-height:1.55;">{html}</p>'


def _saludo(user):
    return f"Hola, {user.full_name}:" if user.full_name else "Hola:"


def enviar_invitacion(user, enlace, horas, con_google):
    marca = marca_de(user.tenant)
    rol = ROLES.get(user.role, "equipo")
    asunto = f"{marca['nombre']} te dio acceso a {settings.MARCA}"
    google = (f"\nTambién puedes entrar con tu cuenta de Google ({user.email}) desde la pantalla de inicio."
              if con_google else "")
    texto = (f"{_saludo(user)}\n\n{marca['nombre']} te dio acceso a {settings.MARCA} ({rol}).\n\n"
             f"Elige tu contraseña aquí: {enlace}\nEl enlace vale {horas} horas.{google}\n\n"
             f"Entras con tu correo: {user.email}\n")
    cuerpo = (
        '<tr><td style="padding:30px 28px 8px;">'
        + _p(f'<span style="color:{SUAVE};">{escape(_saludo(user))}</span>')
        + f'<h1 style="margin:0 0 16px;font-size:22px;line-height:1.3;">Ya tienes acceso a {escape(marca["nombre"])}</h1>'
        + _p(f"Te dieron de alta en {escape(settings.MARCA)} como <strong>{escape(rol)}</strong>. "
             f"Entras con tu correo <strong>{escape(user.email)}</strong>.")
        + _boton("Elegir mi contraseña", enlace, marca["color"])
        + _p(f'<br><span style="color:{SUAVE};font-size:13.5px;">El enlace vale {horas} horas y se usa una sola vez.'
             + (" También puedes entrar con tu cuenta de Google desde la pantalla de inicio, con este mismo correo."
                if con_google else "") + "</span>")
        + "</td></tr>"
    )
    html = _documento(marca, asunto, cuerpo, "Recibes este correo porque tu clínica te dio de alta en su equipo.")
    _enviar(asunto, texto, html, user.email, marca)


def enviar_recuperacion(user, enlace, minutos):
    marca = marca_de(user.tenant)
    asunto = f"Restablecer tu contraseña de {settings.MARCA}"
    texto = (f"{_saludo(user)}\n\nPara elegir una contraseña nueva, abre este enlace:\n\n{enlace}\n\n"
             f"Vale {minutos} minutos y se puede usar una sola vez.\n"
             "Si no lo pediste tú, ignora este correo: tu contraseña no cambia.\n")
    cuerpo = (
        '<tr><td style="padding:30px 28px 8px;">'
        + _p(f'<span style="color:{SUAVE};">{escape(_saludo(user))}</span>')
        + '<h1 style="margin:0 0 16px;font-size:22px;line-height:1.3;">Elige una contraseña nueva</h1>'
        + _p(f"Pediste restablecer la contraseña de tu cuenta de {escape(marca['nombre'])}.")
        + _boton("Elegir contraseña", enlace, marca["color"])
        + _p(f'<br><span style="color:{SUAVE};font-size:13.5px;">El enlace vale {minutos} minutos y se usa '
             "una sola vez. Si no lo pediste tú, ignora este correo: tu contraseña no cambia.</span>")
        + "</td></tr>"
    )
    html = _documento(marca, asunto, cuerpo, "Recibes este correo porque alguien pidió restablecer tu contraseña.")
    _enviar(asunto, texto, html, user.email, marca)
