"""
Temas de una clínica, generados a partir de la paleta de su marca.

Al dar de alta una clínica (Plataforma) o después, desde su
Configuración, se da la paleta —de uno a seis colores, el primero el
principal— y con ella se generan sus temas: el que la clínica lleva de
fábrica y otros con los mismos colores combinados de otra forma. Cada
profesional puede elegir entre estos y los de Clinube (función
«temas_personales»); los documentos y la app del paciente siguen con el
de la clínica.

Se generan en el servidor por lo mismo que `temas.py` resuelve los
predefinidos: el panel, la app y los PDF tienen que pintar los mismos
colores. Un tema tiene la forma de un predefinido —principal, secundario
y, si la paleta trae un color muy oscuro, el de la navegación— y el panel
ajusta sus tonos para que el texto se lea (frontend/lib/theme.js), como
con cualquier otro: aquí se eligen colores de la marca, no se retocan.
"""

import colorsys
import re

from apps.configuration.temas import _hex

MAX_COLORES = 6
PREFIJO = "clinica:"


# ── Paleta ──────────────────────────────────────────────────────────────

def normalizar_paleta(valor):
    """
    La paleta como lista de «#rrggbb», sin repetidos y en el orden dado.

    Acepta una lista o un texto («#0e7490, #67E8F9 0b1220»), con o sin
    almohadilla y en forma corta (#abc). Lo que no sea un color se rechaza
    con ValueError en vez de descartarse en silencio: quien escribe
    «azul» tiene que enterarse de que no sirvió.
    """
    if valor in (None, ""):
        return []
    if isinstance(valor, str):
        trozos = [t for t in re.split(r"[\s,;]+", valor) if t]
    elif isinstance(valor, (list, tuple)):
        trozos = [str(t).strip() for t in valor if str(t).strip()]
    else:
        raise ValueError("La paleta tiene que ser una lista de colores.")

    colores, malos = [], []
    for trozo in trozos:
        texto = trozo if trozo.startswith("#") else f"#{trozo}"
        if len(texto) == 4:  # #abc → #aabbcc
            texto = "#" + "".join(c * 2 for c in texto[1:])
        color = _hex(texto)
        if not color:
            malos.append(trozo)
        elif color not in colores:
            colores.append(color)
    if malos:
        raise ValueError(f"No son colores: {', '.join(malos)}. Escríbelos como #RRGGBB.")
    if len(colores) > MAX_COLORES:
        raise ValueError(f"La paleta admite como mucho {MAX_COLORES} colores.")
    return colores


# ── Color ───────────────────────────────────────────────────────────────

def _rgb(color):
    return tuple(int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))


def _hls(color):
    return colorsys.rgb_to_hls(*_rgb(color))


def _de_hls(h, luz, s):
    r, g, b = colorsys.hls_to_rgb(h, max(0.0, min(1.0, luz)), max(0.0, min(1.0, s)))
    return "#" + "".join(f"{round(c * 255):02x}" for c in (r, g, b))


def _luminancia(color):
    def canal(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (canal(c) for c in _rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a, b):
    """Contraste WCAG entre dos colores (1 a 21)."""
    alta, baja = sorted((_luminancia(a), _luminancia(b)), reverse=True)
    return (alta + 0.05) / (baja + 0.05)


def _cromatico(color):
    """Un color de verdad: ni gris, ni casi blanco, ni casi negro."""
    _, luz, s = _hls(color)
    return s >= 0.18 and 0.10 <= luz <= 0.90


def _sirve_de_principal(color):
    """Saturado y no pálido: aguanta botones y el elemento activo."""
    _, luz, s = _hls(color)
    return s >= 0.25 and 0.12 <= luz <= 0.80


def _distancia_de_tono(a, b):
    ha, hb = _hls(a)[0], _hls(b)[0]
    return min(abs(ha - hb), 1 - abs(ha - hb))


# ── Temas ───────────────────────────────────────────────────────────────

def _tema(clave, nombre, descripcion, principal, secundario, nav=""):
    tema = {"clave": clave, "nombre": nombre, "descripcion": descripcion,
            "primary": principal, "secondary": secundario}
    # La navegación lleva texto blanco encima: solo un color muy oscuro.
    if nav and contraste(nav, "#ffffff") >= 7:
        tema["nav"] = nav
    return tema


def generar_temas(paleta):
    """
    Los temas de una paleta, el primero el que lleva la clínica de fábrica.

      · Principal: el primer color, con el siguiente de tono distinto de
        acento (o un tinte claro del principal si no hay otro).
      · Alterno: los dos al revés, si el segundo aguanta de principal.
      · Sobrio: el principal apagado, para jornadas largas.

    Una paleta sin color (negros, blancos, grises) da un único tema, en
    grises. El resultado no depende de nada más que de la paleta: la
    misma paleta da siempre los mismos temas.
    """
    colores = normalizar_paleta(paleta)
    if not colores:
        return []
    oscuro = next((c for c in colores if _hls(c)[1] <= 0.22), "")
    cromaticos = [c for c in colores if _cromatico(c)]

    if not cromaticos:
        base = next((c for c in colores if 0.15 <= _hls(c)[1] <= 0.60), "#404040")
        return [_tema("principal", "Principal", "La paleta de la clínica, en grises.",
                      base, "#9ca3af", oscuro)]

    principal, otros = cromaticos[0], cromaticos[1:]
    h, luz, s = _hls(principal)
    segundo = next((c for c in otros if _distancia_de_tono(c, principal) > 0.07),
                   otros[0] if otros else "")
    acento = segundo or _de_hls(h, 0.82, min(s, 0.60))

    temas = [_tema("principal", "Principal",
                   "El color principal de la marca, con el segundo de acento.",
                   principal, acento, oscuro)]
    if segundo and _sirve_de_principal(segundo):
        temas.append(_tema("alterno", "Alterno", "Los dos colores de la marca, al revés.",
                           segundo, principal, oscuro))
    if s >= 0.30:
        temas.append(_tema("sobrio", "Sobrio", "El color de la marca más apagado, para jornadas largas.",
                           _de_hls(h, min(max(luz, 0.28), 0.36), min(s, 0.45) * 0.7),
                           _de_hls(h, 0.72, 0.14),
                           oscuro or _de_hls(h, 0.11, min(s, 0.45))))
    return temas


def buscar(temas, clave):
    """El tema `clave` de la lista guardada, o None."""
    return next((t for t in (temas or []) if isinstance(t, dict) and t.get("clave") == clave), None)


def como_tema_de_la_clinica(tema):
    """El formato de `ClinicBranding.theme` para uno de estos temas."""
    salida = {"preset": PREFIJO + tema["clave"],
              "primary": tema["primary"], "secondary": tema["secondary"]}
    if tema.get("nav"):
        salida["nav"] = tema["nav"]
    return salida
