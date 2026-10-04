#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# Copia de seguridad CIFRADA de toda la plataforma, en dos archivos:
#
#   clinica-AAAA-MM-DD_HHMM.sql.gz.enc    la base de datos completa
#   archivos-AAAA-MM-DD_HHMM.tar.gz.enc   radiografías, documentos, firmas
#
# Los dos con AES-256. Si BACKUP_REMOTO está configurado, se suben a otro
# proveedor con rclone; las copias viejas se borran solas (14 días en el
# servidor y 30 fuera, por omisión).
#
# Ojo con la diferencia, que importa: esto es una copia a nivel de
# PLATAFORMA, la hace quien administra el servidor y contiene los datos
# de todas las clínicas. La del panel (Configuración → Copia de
# seguridad) la hace la administración de UNA clínica y solo lleva los
# datos de esa clínica. No son sustitutas la una de la otra.
#
# Uso:
#   ./scripts/backup.sh                      # desarrollo
#   COMPOSE_FILE=docker-compose.prod.yml ./scripts/backup.sh   # producción
#
# Funciona con Docker y sin él: si no hay demonio, usa el pg_dump local.
#
# Requiere BACKUP_PASSPHRASE en el .env. Opcionales: BACKUP_REMOTO,
# BACKUP_REMOTO_DIAS y BACKUP_LOCAL_DIAS.
# GUARDAR ESA CLAVE APARTE DE LA COPIA: sin ella el archivo es
# irrecuperable, que es justamente el punto del cifrado.
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

# shellcheck source=lib-backup.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib-backup.sh"
cargar_entorno
exigir_frase
exigir_openssl
if [ -n "${BACKUP_REMOTO:-}" ]; then
    exigir_rclone
fi

BACKUP_DIR="${BACKUP_DIR:-$RAIZ/backups}"
mkdir -p "$BACKUP_DIR"

STAMP=$(date +%Y-%m-%d_%H%M)
OUTFILE="$BACKUP_DIR/clinica-$STAMP.sql.gz.enc"
ARCHIVOS="$BACKUP_DIR/archivos-$STAMP.tar.gz.enc"

echo "→ Conexión: $(describir_conexion)"
echo "→ Exportando la base «${POSTGRES_DB}»…"

# `set -o pipefail` ya está activo: si pg_dump falla a mitad, la tubería
# entera falla y no se queda un archivo cifrado a medias pareciendo
# válido. Es exactamente el caso que la verificación de abajo caza.
volcar "$POSTGRES_DB" | gzip | cifrar > "$OUTFILE"

SIZE=$(du -h "$OUTFILE" | cut -f1)
echo "✓ Copia cifrada: $OUTFILE ($SIZE)"

# ── Verificación ─────────────────────────────────────────────────────
# Antes aquí había un `gzip -t`, que comprueba que el archivo se
# descomprime y NADA MÁS. Un volcado cortado a la mitad comprime
# perfectamente y pasaba esa prueba: se anunciaba «correcto» una copia
# irrecuperable. Ahora se comprueba que el SQL termine donde debe.
echo "→ Verificando que el volcado esté completo…"
if dump_completo "$OUTFILE"; then
    echo "✓ El volcado se descifra y termina donde debe."
else
    echo "✗ El volcado está TRUNCADO. La copia no sirve." >&2
    echo "  Se conserva el archivo para poder diagnosticar: $OUTFILE" >&2
    exit 1
fi

# ── Archivos subidos ─────────────────────────────────────────────────
echo "→ Copiando los archivos subidos (radiografías, documentos, firmas)…"
volcar_archivos | cifrar > "$ARCHIVOS"
if N=$(descifrar "$ARCHIVOS" | tar -tzf - | grep -vc '/$'); then
    echo "✓ Archivos cifrados: $ARCHIVOS ($(du -h "$ARCHIVOS" | cut -f1), ${N} archivos)"
else
    # grep -c devuelve 1 si no cuenta nada: una clínica sin archivos aún.
    if descifrar "$ARCHIVOS" | tar -tzf - >/dev/null; then
        echo "✓ Archivos cifrados: $ARCHIVOS (todavía no hay archivos subidos)"
    else
        echo "✗ La copia de los archivos no se puede leer. No sirve." >&2
        exit 1
    fi
fi

podar_local "$BACKUP_DIR"

# ── Fuera del servidor ───────────────────────────────────────────────
if [ -n "${BACKUP_REMOTO:-}" ]; then
    echo "→ Subiendo las dos copias a ${BACKUP_REMOTO}…"
    for f in "$OUTFILE" "$ARCHIVOS"; do
        if ! subir_copia "$f"; then
            cat >&2 <<FIN
✗ NO se pudo subir $(basename "$f") a ${BACKUP_REMOTO}.
  La copia está en el servidor, pero si se pierde el servidor se pierde
  con él. Revisa la configuración con:   rclone lsd ${BACKUP_REMOTO%%:*}:
FIN
            exit 2
        fi
    done
    podar_remoto || echo "  (no se pudieron borrar las copias antiguas del destino; revisa los permisos)" >&2
    echo "✓ Copias guardadas fuera del servidor, en ${BACKUP_REMOTO}."
else
    cat >&2 <<FIN

⚠  SIN COPIA FUERA DEL SERVIDOR: BACKUP_REMOTO no está configurado.
   Si se pierde el servidor, se pierden también estas copias. Ver
   DEPLOY.md, «Copia fuera del servidor».
FIN
fi

cat <<FIN

Esta comprobación dice que el archivo está entero, no que sea
restaurable. Para saberlo hay que restaurarlo:

    ./scripts/verificar-backup.sh "$OUTFILE"

Conviene programarlo semanalmente (ver DEPLOY.md). Una copia que nadie
ha restaurado nunca no es una copia: es un archivo del que se supone algo.
FIN
