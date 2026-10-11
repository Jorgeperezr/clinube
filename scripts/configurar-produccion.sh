#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# Crea el .env de producción en el servidor, con claves nuevas.
#
#   bash scripts/configurar-produccion.sh clinube.com
#
# Parte de .env.production.example y rellena lo que no hay que pensar:
#
#   · DJANGO_SECRET_KEY, POSTGRES_PASSWORD, INTERNAL_SERVICE_TOKEN,
#     BACKUP_PASSPHRASE y META_WEBHOOK_VERIFY_TOKEN, aleatorias y
#     generadas aquí mismo: no pasan por ningún chat ni correo.
#   · El dominio: el panel y la API en app.<dominio>.
#   · El remitente del correo se deja al formulario de Plataforma
#     (Configuración → Correo saliente), que firma con la cuenta de Gmail.
#
# No pisa un .env que ya exista: las claves de la base y de las copias no
# se pueden cambiar a la ligera (la base dejaría de abrir y las copias
# viejas no se podrían descifrar).
#
# Las variables van SIEMPRE entre llaves —${VAR}— (ver comprobar-guiones.sh).
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV="${RAIZ}/.env"
EJEMPLO="${RAIZ}/.env.production.example"

DOMINIO="$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]' | sed -e 's#^https\?://##' -e 's#/.*$##' -e 's/^app\.//')"
if [ -z "${DOMINIO}" ] || ! printf '%s' "${DOMINIO}" | grep -Eq '^[a-z0-9-]+(\.[a-z0-9-]+)+$'; then
    echo "Uso: bash scripts/configurar-produccion.sh clinube.com" >&2
    exit 2
fi
if [ -e "${ENV}" ]; then
    echo "Ya existe ${ENV}: no se toca." >&2
    echo "Si de verdad quieres empezar de cero (la base de datos todavía vacía), muévelo antes:" >&2
    echo "mv ${ENV} ${ENV}.anterior" >&2
    exit 1
fi
command -v python3 >/dev/null 2>&1 || { echo "Falta python3." >&2; exit 1; }

umask 077
python3 - "${EJEMPLO}" "${ENV}" "${DOMINIO}" <<'PY'
import re
import secrets
import sys

ejemplo, destino, dominio = sys.argv[1:4]
app = f"app.{dominio}"
valores = {
    "DJANGO_SECRET_KEY": secrets.token_urlsafe(64),
    "POSTGRES_PASSWORD": secrets.token_urlsafe(24),
    "INTERNAL_SERVICE_TOKEN": secrets.token_urlsafe(48),
    "BACKUP_PASSPHRASE": secrets.token_urlsafe(32),
    "META_WEBHOOK_VERIFY_TOKEN": secrets.token_urlsafe(24),
    "DJANGO_DEBUG": "False",
    "DJANGO_ALLOWED_HOSTS": app,
    "CSRF_TRUSTED_ORIGINS": f"https://{app}",
    "CORS_ALLOWED_ORIGINS": f"https://{app}",
    "SECURE_SSL_REDIRECT": "False",
    "NGINX_PUERTO": "127.0.0.1:80",
}
lineas = []
for linea in open(ejemplo, encoding="utf-8").read().splitlines():
    m = re.match(r"^([A-Z_]+)=", linea)
    if m and m.group(1) in valores:
        linea = f"{m.group(1)}={valores[m.group(1)]}"
    elif m and m.group(1) == "DEFAULT_FROM_EMAIL":
        # Sin remitente fijo: el correo sale firmado con la cuenta que se
        # ponga en Plataforma (Gmail no deja firmar con otra).
        linea = "# " + linea
    lineas.append(linea)
lineas += [
    "",
    "# --- Enlaces de los correos (recuperar contraseña) ---",
    f"PANEL_URL=https://{app}",
]
open(destino, "w", encoding="utf-8").write("\n".join(lineas) + "\n")
PY
chmod 600 "${ENV}"

PASE="$(grep '^BACKUP_PASSPHRASE=' "${ENV}" | cut -d= -f2-)"
echo "✓ Creado ${ENV} para https://app.${DOMINIO} (solo lo puede leer este usuario)."
echo ""
echo "IMPORTANTE — guarda AHORA esta clave de las copias de seguridad fuera del"
echo "servidor, en tu gestor de contraseñas o en papel. Sin ella las copias no se"
echo "pueden descifrar, y si el servidor se pierde, esta es la única copia:"
echo ""
echo "    ${PASE}"
echo ""
echo "No la pegues en chats ni correos. El resto de claves no hace falta guardarlas."
echo ""
echo "Siguiente paso (DEPLOY.md, «Pasos comunes», 4):"
echo "docker compose -f docker-compose.prod.yml up -d --build"
