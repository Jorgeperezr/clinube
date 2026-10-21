#!/usr/bin/env bash
# Exporta el contrato del sistema a docs/contrato/ (rutas de la API,
# modelo de datos y esquema OpenAPI), generado desde el código.
# Lo usa la reimplementación en Java/Kotlin (clinube_java) como referencia:
# tras cambiar Clinube, se vuelve a exportar y el diff dice qué portar.
#
#   bash scripts/exportar-contrato.sh
set -euo pipefail
cd "$(dirname "$0")/.."
bash scripts/manage.sh exportar_contrato "$@"
