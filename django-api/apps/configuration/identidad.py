"""
Logotipos, paleta y tema de una clínica.

Llegan por dos vías: el Super Administrador al darla de alta (Plataforma
→ Clínicas → Identidad visual) y su administración después
(Configuración → Identidad visual). Las dos pasan por aquí para validar
igual y regenerar los temas igual.

Todo se valida ANTES de tocar nada: si un archivo no sirve o el tema
elegido no existe, no se borra el logotipo anterior ni se cambia la
paleta. Quitar un archivo del disco no tiene marcha atrás.
"""

import json

from PIL import Image

from apps.configuration.temas_clinica import (
    PREFIJO,
    buscar,
    como_tema_de_la_clinica,
    generar_temas,
    normalizar_paleta,
)

# Campo → cómo se le nombra en un mensaje de error.
LOGOS = {
    "logo": "El logotipo",
    "logo_oscuro": "El logotipo para fondo oscuro",
    "icono": "El ícono",
}
FORMATOS = {"PNG", "JPEG", "WEBP", "GIF"}
TAMANO_MAXIMO = 4 * 1024 * 1024


def validar_imagen(archivo, nombre):
    """
    Una imagen de verdad, de un formato que pinta cualquier navegador.

    Sin esto se guardaba lo que llegara: un SVG con un script dentro,
    servido desde /media/, se ejecutaría en el dominio de la API.
    """
    if archivo.size > TAMANO_MAXIMO:
        raise ValueError(f"{nombre} pesa más de 4 MB.")
    try:
        with Image.open(archivo) as img:
            formato = img.format
            img.verify()
    except Exception:
        raise ValueError(f"{nombre} no es una imagen que se pueda usar (PNG, JPG, WEBP o GIF).") from None
    finally:
        archivo.seek(0)
    if formato not in FORMATOS:
        raise ValueError(f"{nombre} tiene que ser PNG, JPG, WEBP o GIF.")


def _verdadero(valor):
    return str(valor).strip().lower() in ("true", "1", "si", "sí")


def leer_paleta(datos):
    """La paleta del cuerpo: lista JSON (también como texto) o texto suelto."""
    valor = datos.get("paleta")
    if isinstance(valor, str) and valor.strip().startswith("["):
        try:
            valor = json.loads(valor)
        except ValueError:
            raise ValueError("La paleta no tiene un formato válido.") from None
    return normalizar_paleta(valor)


def leer_tema(datos):
    """El tema del cuerpo (objeto JSON, también como texto), o None si no viene."""
    tema = datos.get("theme")
    if tema is None:
        return None
    if isinstance(tema, str):
        try:
            tema = json.loads(tema)
        except ValueError:
            raise ValueError("El tema no tiene un formato válido.") from None
    if not isinstance(tema, dict):
        raise ValueError("El tema no tiene un formato válido.")
    return tema


def _tema_comprobado(tema, temas):
    """
    Uno de los generados («clinica:<clave>») se guarda con SUS colores,
    no con los que mande el panel; si ya no existe, es un error.
    """
    preset = str(tema.get("preset") or "default")
    if not preset.startswith(PREFIJO):
        return tema
    generado = buscar(temas, preset[len(PREFIJO):])
    if generado is None:
        raise ValueError("Ese tema ya no está entre los de la clínica.")
    return como_tema_de_la_clinica(generado)


def _tema_que_sigue_a_la_paleta(actual, temas, habia_paleta):
    """
    Que el tema de la clínica siga a su paleta sin pisar una elección:

      · si usa uno de sus temas generados, se recalcula con la paleta
        nueva (y si ese ya no sale, pasa al principal);
      · si todavía tiene el de fábrica y es su primera paleta —el alta—,
        se le pone el principal: para eso se dio la paleta;
      · si eligió uno de Clinube o sus colores a mano, se respeta.

    Devuelve el tema nuevo, o None si no hay que cambiarlo.
    """
    preset = str((actual or {}).get("preset") or "default")
    if preset.startswith(PREFIJO):
        if not temas:
            return {"preset": "default", "primary": "", "secondary": ""}
        return como_tema_de_la_clinica(buscar(temas, preset[len(PREFIJO):]) or temas[0])
    if preset == "default" and not habia_paleta and temas:
        return como_tema_de_la_clinica(temas[0])
    return None


def actualizar(branding, datos, archivos):
    """
    Aplica logotipos, paleta y tema a `branding` (sin guardar el registro).

    Admite `logo`, `logo_oscuro` e `icono` (archivos), `<campo>_clear`
    para quitarlos, `paleta` y `theme`. Lanza ValueError con el motivo si
    algo no vale, y en ese caso no ha cambiado nada.
    """
    # 1. Comprobarlo todo.
    nuevos = {}
    for campo, nombre in LOGOS.items():
        if campo in archivos:
            validar_imagen(archivos[campo], nombre)
            nuevos[campo] = archivos[campo]
    paleta = leer_paleta(datos) if "paleta" in datos else None
    temas = generar_temas(paleta) if paleta is not None else (branding.temas or [])
    tema = leer_tema(datos)
    if tema is not None:
        tema = _tema_comprobado(tema, temas)

    # 2. Aplicar.
    for campo in LOGOS:
        archivo_actual = getattr(branding, campo)
        if campo in nuevos or _verdadero(datos.get(f"{campo}_clear", "")):
            # Al reemplazar, el anterior se borra del disco: así no se
            # acumulan logotipos huérfanos de cada prueba.
            if archivo_actual:
                archivo_actual.delete(save=False)
            setattr(branding, campo, nuevos.get(campo))
    if paleta is not None:
        habia_paleta = bool(branding.paleta)
        branding.paleta, branding.temas = paleta, temas
        if tema is None:
            tema = _tema_que_sigue_a_la_paleta(branding.theme, temas, habia_paleta)
    if tema is not None:
        branding.theme = tema
