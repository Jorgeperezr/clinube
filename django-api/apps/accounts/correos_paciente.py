"""
Los correos que recibe el paciente: la bienvenida cuando la clínica le
activa la app y el código para entrar.

Salen con la cara de SU clínica —nombre, color y logotipo—, no con la de
Clinube: el paciente conoce a su dentista, no a la plataforma. Cada
correo va en HTML y en texto: los filtros de correo no deseado desconfían
de los que solo traen HTML, y hay lectores que no lo muestran.

El HTML está hecho a la antigua (tablas y estilos en línea) a propósito:
Gmail, Outlook y el Mail del iPhone ignoran las hojas de estilo y buena
parte del CSS moderno. Sin imágenes salvo el logotipo de la clínica, que
es lo único que el paciente reconoce de un vistazo: un correo lleno de
imágenes es lo primero que acaba en «Spam».

Las respuestas van a la clínica (Reply-To con su correo), no a Clinube.
"""

import colorsys
from html import escape

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

TINTA = "#0B1220"
SUAVE = "#5B6474"
FONDO = "#F3F5F8"
POR_DEFECTO = "#0E7490"


# ── La marca de la clínica ───────────────────────────────────────────

def _rgb(color):
    return tuple(int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))


def _contraste_con_blanco(color):
    def canal(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (canal(c) for c in _rgb(color))
    return 1.05 / (0.2126 * r + 0.7152 * g + 0.0722 * b + 0.05)


def color_legible(color):
    """
    El color de la clínica, oscurecido lo justo para que el texto blanco
    encima se lea (contraste 4,5:1). Un amarillo o un celeste claro, tal
    cual, harían ilegible el botón y la cabecera.
    """
    texto = str(color or "").strip().lower()
    if len(texto) != 7 or not texto.startswith("#"):
        return POR_DEFECTO
    try:
        h, luz, s = colorsys.rgb_to_hls(*_rgb(texto))
    except ValueError:
        return POR_DEFECTO
    while _contraste_con_blanco(texto) < 4.5 and luz > 0.05:
        luz -= 0.03
        r, g, b = colorsys.hls_to_rgb(h, luz, s)
        texto = "#" + "".join(f"{round(c * 255):02x}" for c in (r, g, b))
    return texto


def _base_publica():
    return (settings.PANEL_URL or "").rstrip("/")


def marca_de(tenant):
    """Nombre, color, logotipo y contacto de la clínica para el correo."""
    from apps.configuration.models import ClinicBranding
    from apps.configuration.temas import resolver

    branding = ClinicBranding.objects.filter(tenant=tenant).first() if tenant else None
    nombre = ((branding.display_name if branding else "") or getattr(tenant, "name", "")
              or settings.MARCA).strip()
    color = color_legible(resolver(branding.theme)[0] if branding else POR_DEFECTO)
    logo = ""
    base = _base_publica()
    # Solo con dirección pública: un enlace a «localhost» sería una imagen rota.
    if branding and branding.logo and base.startswith("https://"):
        logo = f"{base}{branding.logo.url}"
    return {
        "nombre": nombre,
        "color": color,
        "logo": logo,
        "correo": (branding.email if branding else "") or "",
        "telefono": (branding.phone if branding else "") or "",
        "direccion": (branding.address if branding else "") or "",
    }


# ── Piezas del HTML ──────────────────────────────────────────────────

def _cabecera(marca):
    if marca["logo"]:
        dentro = (f'<img src="{escape(marca["logo"])}" alt="{escape(marca["nombre"])}" height="48" '
                  'style="display:block;max-height:48px;max-width:220px;border:0;margin:0 auto;'
                  'background:#ffffff;border-radius:8px;padding:6px 10px;">')
    else:
        dentro = (f'<div style="font-size:22px;font-weight:700;color:#ffffff;letter-spacing:-0.2px;">'
                  f'{escape(marca["nombre"])}</div>')
    return (f'<tr><td style="background:{marca["color"]};padding:26px 24px;text-align:center;'
            f'border-radius:14px 14px 0 0;">{dentro}</td></tr>')


def _pie(marca, motivo):
    contacto = " · ".join(escape(x) for x in (marca["telefono"], marca["correo"], marca["direccion"]) if x)
    return (
        f'<tr><td style="padding:20px 28px 26px;border-top:1px solid #E5E8EE;color:{SUAVE};'
        'font-size:12.5px;line-height:1.6;">'
        f'<strong style="color:{TINTA};">{escape(marca["nombre"])}</strong>'
        + (f'<br>{contacto}' if contacto else "")
        + f'<br><br>{escape(motivo)}'
        f'<br>Enviado con {escape(settings.MARCA)}, el sistema de gestión de tu clínica.'
        '</td></tr>'
    )


def _documento(marca, titulo_oculto, cuerpo, motivo):
    """El esqueleto común: fondo gris, tarjeta blanca de 560 px."""
    return (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{escape(titulo_oculto)}</title></head>'
        f'<body style="margin:0;padding:0;background:{FONDO};">'
        # El texto de vista previa que enseña la bandeja de entrada.
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{escape(titulo_oculto)}</div>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{FONDO};">'
        '<tr><td align="center" style="padding:28px 12px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="max-width:560px;background:#ffffff;border-radius:14px;'
        "font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;"
        f'color:{TINTA};box-shadow:0 1px 3px rgba(11,18,32,0.08);">'
        + _cabecera(marca) + cuerpo + _pie(marca, motivo)
        + '</table></td></tr></table></body></html>'
    )


def _boton(texto, enlace, color):
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" style="margin:6px 0 4px;"><tr>'
        f'<td style="background:{color};border-radius:10px;">'
        f'<a href="{escape(enlace)}" style="display:inline-block;padding:13px 26px;color:#ffffff;'
        f'font-size:15px;font-weight:600;text-decoration:none;">{escape(texto)}</a>'
        '</td></tr></table>'
    )


def _paso(numero, titulo, detalle_html, color):
    return (
        '<tr><td style="padding:0 0 16px;">'
        '<table role="presentation" cellpadding="0" cellspacing="0"><tr>'
        f'<td valign="top" style="width:34px;"><div style="width:28px;height:28px;border-radius:14px;'
        f'background:{color};color:#ffffff;font-size:14px;font-weight:700;text-align:center;'
        f'line-height:28px;">{numero}</div></td>'
        f'<td valign="top" style="padding-left:10px;font-size:15px;line-height:1.5;">'
        f'<strong>{escape(titulo)}</strong><br><span style="color:{SUAVE};">{detalle_html}</span></td>'
        '</tr></table></td></tr>'
    )


def _primer_nombre(cuenta):
    return (getattr(cuenta, "full_name", "") or "").split(" ")[0]


def _enviar(asunto, texto, html, destino, marca):
    mensaje = EmailMultiAlternatives(
        subject=asunto, body=texto, to=[destino],
        reply_to=[marca["correo"]] if marca["correo"] else None,
    )
    mensaje.attach_alternative(html, "text/html")
    mensaje.send()


# ── El código para entrar ────────────────────────────────────────────

def enviar_codigo(cuenta, codigo, minutos, destino):
    marca = marca_de(cuenta.tenant)
    nombre = _primer_nombre(cuenta)
    saludo = f"Hola, {nombre}:" if nombre else "Hola:"
    asunto = f"{codigo} es tu código para entrar en la app de {marca['nombre']}"

    texto = (
        f"{saludo}\n\n"
        f"Tu código para entrar en la app de {marca['nombre']} es:\n\n"
        f"    {codigo}\n\n"
        f"Vale durante {minutos} minutos y una sola vez.\n\n"
        "Nadie de la clínica te lo pedirá nunca: no se lo des a nadie.\n"
        "Si no lo pediste tú, ignora este correo; sin el código nadie puede entrar.\n\n"
        f"{marca['nombre']}\n"
    )
    cifras = "".join(
        f'<td style="width:44px;height:54px;border:1px solid #D6DBE3;border-radius:10px;'
        f'background:#F7F9FB;text-align:center;font-size:28px;font-weight:700;'
        f"font-family:'SF Mono',Menlo,Consolas,monospace;color:{TINTA};\">{escape(c)}</td>"
        '<td style="width:6px;"></td>'
        for c in codigo
    )
    cuerpo = (
        '<tr><td style="padding:30px 28px 8px;">'
        f'<p style="margin:0 0 6px;font-size:15px;color:{SUAVE};">{escape(saludo)}</p>'
        '<h1 style="margin:0 0 18px;font-size:22px;line-height:1.3;">Tu código para entrar en la app</h1>'
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 18px;"><tr>{cifras}</tr></table>'
        f'<p style="margin:0 0 14px;font-size:15px;line-height:1.55;">Escríbelo en la app de '
        f'<strong>{escape(marca["nombre"])}</strong>. Vale durante <strong>{minutos} minutos</strong> '
        'y una sola vez.</p>'
        f'<p style="margin:0 0 6px;padding:12px 14px;background:#FFF8E6;border-radius:10px;'
        'font-size:13.5px;line-height:1.5;color:#7A5300;">🔒 Nadie de la clínica te lo pedirá nunca. '
        'Si no lo pediste tú, ignora este correo: sin el código nadie puede entrar.</p>'
        '</td></tr>'
    )
    html = _documento(marca, f"Tu código es {codigo}. Vale {minutos} minutos.", cuerpo,
                      "Recibes este correo porque alguien pidió entrar en la app con tu dirección.")
    _enviar(asunto, texto, html, destino, marca)


# ── La bienvenida ────────────────────────────────────────────────────

def enviar_bienvenida(cuenta, destino, canal, dato_de_entrada):
    """
    «Ya puedes usar la app»: qué es, cómo descargarla y con qué entrar.
    `canal` es por dónde le llegará el código; `dato_de_entrada`, el
    teléfono o el correo con el que tiene que identificarse.
    """
    marca = marca_de(cuenta.tenant)
    nombre = _primer_nombre(cuenta)
    saludo = f"Hola, {nombre}:" if nombre else "Hola:"
    base = _base_publica()
    descargar = f"{base}/descargar/" if base else ""
    por_correo = canal == "correo"
    con_que = "tu correo" if por_correo else "tu número de teléfono"
    llega = "por correo" if por_correo else "por WhatsApp"
    asunto = f"{marca['nombre']} te invita a su app: tus citas y tu saldo en el teléfono"

    texto = (
        f"{saludo}\n\n"
        f"{marca['nombre']} te ha dado acceso a su app. Desde el teléfono podrás ver y confirmar "
        "tus citas, consultar tu saldo, leer las indicaciones de tu tratamiento y escribir a la clínica.\n\n"
        "Cómo entrar:\n"
        f"1. Descarga la app Clinube{': ' + descargar if descargar else ' en App Store o Google Play'}\n"
        f"2. Entra con {con_que}: {dato_de_entrada}\n"
        f"3. Escribe el código de 6 cifras que te llegará {llega}.\n\n"
        "No necesitas contraseña: cada vez que entres te llegará un código nuevo.\n\n"
        f"Si no esperabas este correo, escríbenos y lo revisamos.\n\n{marca['nombre']}\n"
    )
    pasos = (
        _paso(1, "Descarga la app Clinube",
              "Está en App Store (iPhone) y Google Play (Android).", marca["color"])
        + _paso(2, f"Entra con {con_que}",
                f'<strong style="color:{TINTA};">{escape(dato_de_entrada)}</strong>', marca["color"])
        + _paso(3, "Escribe el código de 6 cifras",
                f"Te llegará {llega} en unos segundos. No necesitas contraseña.", marca["color"])
    )
    ventajas = "".join(
        f'<tr><td style="padding:4px 0;font-size:14.5px;line-height:1.5;">'
        f'<span style="color:{marca["color"]};font-weight:700;">✓</span>&nbsp; {escape(v)}</td></tr>'
        for v in ("Ver tus próximas citas y confirmarlas con un toque",
                  "Consultar tu saldo y tus pagos",
                  "Leer las indicaciones de tu tratamiento",
                  "Escribir a la clínica o pedir una cita")
    )
    cuerpo = (
        '<tr><td style="padding:30px 28px 6px;">'
        f'<p style="margin:0 0 6px;font-size:15px;color:{SUAVE};">{escape(saludo)}</p>'
        f'<h1 style="margin:0 0 12px;font-size:23px;line-height:1.3;">Ya puedes usar la app de '
        f'{escape(marca["nombre"])}</h1>'
        f'<p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:{SUAVE};">Tu clínica te dio acceso. '
        'Tendrás tu información a mano, sin llamar ni esperar.</p>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:#F7F9FB;border-radius:12px;margin:0 0 20px;"><tr><td style="padding:16px 18px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{ventajas}</table>'
        '</td></tr></table>'
        '<h2 style="margin:0 0 14px;font-size:17px;">Cómo entrar</h2>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{pasos}</table>'
        + (_boton("Descargar la app", descargar, marca["color"]) if descargar else "")
        + '</td></tr>'
    )
    html = _documento(marca, f"Tus citas y tu saldo de {marca['nombre']}, en tu teléfono.", cuerpo,
                      f"Recibes este correo porque {marca['nombre']} activó tu acceso a la app. "
                      "Si no esperabas este correo, respóndelo y la clínica lo revisará.")
    _enviar(asunto, texto, html, destino, marca)
