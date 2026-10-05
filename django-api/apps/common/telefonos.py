"""
Teléfonos en un solo formato: E.164 (+593991234567).

La recepción los escribe como los dicta el paciente —«099 123 4567»,
«0991234567», «+593 99…»— y el paciente los teclea a su manera en la
app. Si no se comparan en el mismo formato, «0991234567» y
«+593991234567» son dos personas distintas y el código no llega nunca.

El prefijo por omisión es el de Ecuador: un número que empieza por 0 es
nacional. Un número con «+» o con «00» se respeta tal cual.
"""

import re

PREFIJO_PAIS = "+593"


def normalizar_telefono(texto, prefijo=PREFIJO_PAIS):
    """El teléfono en E.164, o "" si no parece un teléfono."""
    limpio = re.sub(r"[^\d+]", "", texto or "")
    if not limpio:
        return ""
    if limpio.startswith("+"):
        numero = "+" + re.sub(r"\D", "", limpio)
    elif limpio.startswith("00"):
        numero = "+" + limpio[2:]
    elif limpio.startswith(prefijo.lstrip("+")) and len(limpio) > 10:
        numero = "+" + limpio
    elif limpio.startswith("0"):
        numero = prefijo + limpio[1:]
    else:
        numero = prefijo + limpio
    # E.164: hasta 15 cifras. Menos de 8 no es un móvil de ningún país.
    cifras = len(numero) - 1
    return numero if 8 <= cifras <= 15 else ""
