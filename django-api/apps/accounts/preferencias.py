"""
Preferencias de cada profesional.

A diferencia de las funcionalidades (`apps/common/funcionalidades.py`),
que decide el dueño de la plataforma para TODA una clínica, esto lo
decide cada persona para sí misma. Las dos cosas se combinan: una
preferencia solo tiene efecto si la clínica tiene contratada la
funcionalidad de la que depende. Un doctor no puede encenderse el
odontograma 3D si su clínica no lo tiene; sí puede apagárselo aunque la
clínica lo tenga, porque trabaja más cómodo con el clásico o porque su
equipo lo mueve con dificultad.

Igual que con las funcionalidades, las claves desconocidas se descartan
y las que faltan toman su valor por defecto, así que añadir una
preferencia nueva no necesita migración de datos.
"""

CATALOGO = {
    "odontograma_3d": {
        "etiqueta": "Odontograma 3D",
        "por_defecto": True,
        # Solo tiene efecto si la clínica tiene contratada esta funcionalidad.
        "funcionalidad": "odontograma_3d",
    },
}

POR_DEFECTO = {clave: d["por_defecto"] for clave, d in CATALOGO.items()}

# Apariencia del panel, también de cada persona (no dependen de nada
# contratado, así que no van en CATALOGO ni en `disponibles`):
#
#   · acento: el color de acento propio. "" = el de la clínica. Las
#     claves y sus colores están en frontend/lib/acentos.js; aquí solo
#     se comprueba la forma, y una clave que el panel no conozca se
#     ignora allí y se pinta con el de la clínica.
#   · barra_oculta: las secciones que esa persona quitó de su barra
#     lateral. Ocultar no quita permisos: la página sigue funcionando
#     si se entra por su dirección.
#   · tema: el tema de su panel. "" = el de la clínica; «clinica:<clave>»
#     es uno de los generados con la paleta de su clínica y
#     «clinube:<clave>», uno de los de Clinube (frontend/lib/theme.js).
#     Solo se puede elegir si la clínica tiene la función
#     «temas_personales» (eso lo comprueba la vista, que conoce la
#     clínica); aquí, la forma.
import re  # noqa: E402

APARIENCIA = {"acento": "", "barra_oculta": [], "tema": ""}
_CLAVE = re.compile(r"^[a-z_]{1,30}$")
_TEMA = re.compile(r"^(clinica|clinube):[a-z0-9_]{1,30}$")
MAX_OCULTAS = 20


def validar_apariencia(clave, valor):
    """Devuelve el valor limpio, o lanza ValueError con el motivo."""
    if clave == "acento":
        if not isinstance(valor, str) or (valor and not _CLAVE.match(valor)):
            raise ValueError("el acento tiene que ser el nombre de un color")
        return valor
    if clave == "tema":
        if not isinstance(valor, str) or (valor and not _TEMA.match(valor)):
            raise ValueError("el tema tiene que ser uno de los de la clínica o de Clinube")
        return valor
    if clave == "barra_oculta":
        if not isinstance(valor, list) or len(valor) > MAX_OCULTAS or \
                not all(isinstance(v, str) and _CLAVE.match(v) for v in valor):
            raise ValueError("la barra lateral tiene que ser una lista de secciones")
        return sorted(set(valor))
    raise ValueError("preferencia desconocida")


def normalizar(valores):
    """Lo guardado, completado con los valores por defecto y sin claves ajenas."""
    valores = valores if isinstance(valores, dict) else {}
    limpio = {clave: bool(valores.get(clave, defecto)) for clave, defecto in POR_DEFECTO.items()}
    for clave, defecto in APARIENCIA.items():
        try:
            limpio[clave] = validar_apariencia(clave, valores.get(clave, defecto))
        except ValueError:
            limpio[clave] = defecto
    return limpio
