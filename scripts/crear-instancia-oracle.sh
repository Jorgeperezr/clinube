#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# Intenta crear la máquina de Clinube en Oracle Cloud (Always Free,
# Ampere A1). Lo usa scripts/oracle-local.sh, que lo repite desde el
# ordenador de quien administra mientras está encendido; antes lo lanzaba
# cada hora el flujo .github/workflows/oracle-instancia.yml (desactivado:
# gastaba los minutos de Actions). También sirve a mano con la OCI CLI
# configurada.
#
# Por defecto, un solo intento. Con DURACION_MIN, repite cada ESPERA_S
# segundos hasta crearla o hasta agotar ese tiempo. Cada 5 minutos no
# choca con el límite de peticiones de Oracle; si aun así lo pide
# («TooManyRequests»), se espera el doble. Si se corta la conexión
# (internet caído, el Mac que despierta), se espera y se sigue.
#
# Salida:
#   0  creada (escribe la IP en ${SALIDA_IP}), ya existía, o se acabó el
#      tiempo sin capacidad (entonces no escribe ${SALIDA_IP}).
#   1  cualquier otro error (credenciales, OCID mal puesto…): eso no se
#      arregla esperando.
#   4  sin conexión con Oracle: se puede volver a lanzar más tarde.
#
# Variables (las de OCI las lee la propia CLI de ~/.oci/config):
#   OCI_COMPARTIMENTO   OCID del compartimento (por omisión, el arrendamiento)
#   CLAVE_SSH_PUBLICA   la clave pública con la que se entrará por SSH
#   OCPUS / MEMORIA_GB / DISCO_GB   tamaño (1 / 6 / 100: dentro de lo gratis)
#   NOMBRE              nombre de la instancia (clinube)
#   SALIDA_IP           archivo donde dejar la IP pública al crearla
#   DURACION_MIN        minutos que se sigue intentando (0: un intento)
#   ESPERA_S            segundos entre intentos (300)
# ─────────────────────────────────────────────────────────────────────
set -uo pipefail

NOMBRE="${NOMBRE:-clinube}"
OCPUS="${OCPUS:-1}"
MEMORIA_GB="${MEMORIA_GB:-6}"
DISCO_GB="${DISCO_GB:-100}"
FORMA="VM.Standard.A1.Flex"
SALIDA_IP="${SALIDA_IP:-/dev/null}"
DURACION_MIN="${DURACION_MIN:-0}"
ESPERA_S="${ESPERA_S:-300}"

# En Actions, la hora UTC de sus registros; en el ordenador, la local.
hora() {
  if [ -n "${GITHUB_ACTIONS:-}" ]; then date -u '+%H:%M UTC'; else date '+%d/%m %H:%M'; fi
}

if [ -z "${OCI_COMPARTIMENTO:-}" ]; then
  OCI_COMPARTIMENTO="$(awk -F= '/^tenancy/ {gsub(/ /, "", $2); print $2; exit}' "${OCI_CLI_CONFIG_FILE:-${HOME}/.oci/config}" 2>/dev/null)"
fi
if [ -z "${OCI_COMPARTIMENTO}" ] || [ -z "${CLAVE_SSH_PUBLICA:-}" ]; then
  echo "Faltan OCI_COMPARTIMENTO o CLAVE_SSH_PUBLICA." >&2
  exit 1
fi

# ¿Es un fallo que se arregla solo? Sin conexión, un tiempo agotado o un
# error 5xx de Oracle. «Sin capacidad» también llega como 500: quien
# llama lo mira antes.
pasajero() {
  printf '%s' "$1" | grep -qiE 'Max retries exceeded|Failed to establish a new connection|Connection (aborted|refused|reset)|ConnectTimeout|ConnectionError|timed out|nodename nor servname|Name or service not known|Temporary failure in name resolution|Network is unreachable|No route to host|SSLError|RemoteDisconnected|"status": 5[0-9][0-9]'
}

# Lo que no se arregla esperando, dicho de forma que se entienda.
explicar() {
  case "$1" in
    *NotAuthenticated*)
      echo "Oracle no acepta la clave de API: el usuario, la huella o el arrendamiento de ~/.oci/config no corresponden a ella, o la clave pública no está agregada en Mi perfil → Claves de API." >&2 ;;
    *NotAuthorizedOrNotFound*)
      echo "Oracle no encuentra algo o no deja usarlo: suele ser un OCID mal copiado." >&2 ;;
    *LimitExceeded*|*QuotaExceeded*)
      echo "Oracle dice que se superó el límite o la cuota: ¿hay otra instancia A1 creada?" >&2 ;;
  esac
}

# Una consulta a Oracle: escribe lo que devuelve. Sale con 1 si falla de
# verdad (y deja el mensaje de Oracle) y con 4 si falla la conexión.
consulta() {
  local err salida estado
  err="$(mktemp)"
  salida="$(oci "$@" 2>"${err}")"
  estado=$?
  if [ "${estado}" -ne 0 ]; then
    if pasajero "$(cat "${err}")"; then
      echo "$(hora) Sin conexión con Oracle." >&2
      estado=4
    else
      cat "${err}" >&2
      explicar "$(cat "${err}")"
      estado=1
    fi
  fi
  rm -f "${err}"
  printf '%s' "${salida}"
  return "${estado}"
}

# ¿Ya existe una instancia con este nombre? Devuelve su OCID o nada.
# Always Free da para una: nunca se crea otra.
existente() {
  local r
  r="$(consulta compute instance list -c "${OCI_COMPARTIMENTO}" --all \
    --query "data[?\"display-name\"=='${NOMBRE}' && \"lifecycle-state\"!='TERMINATED' && \"lifecycle-state\"!='TERMINATING'] | [0].id" \
    --raw-output)" || return $?
  [ "${r}" = "null" ] && r=""
  printf '%s' "${r}"
}

# Lo que hace falta para crearla, buscado una vez por ejecución. La
# imagen se busca y no se fija: Oracle publica una nueva cada pocas
# semanas y retira las viejas, y un OCID fijo dejaría de valer.
preparar() {
  AD="$(consulta iam availability-domain list -c "${OCI_COMPARTIMENTO}" --query 'data[0].name' --raw-output)" || return $?
  SUBRED="$(consulta network subnet list -c "${OCI_COMPARTIMENTO}" --all \
    --query 'data[?"prohibit-public-ip-on-vnic"==`false`] | [0].id' --raw-output)" || return $?
  IMAGEN="$(consulta compute image list -c "${OCI_COMPARTIMENTO}" --all \
    --operating-system "Canonical Ubuntu" --operating-system-version "24.04" \
    --shape "${FORMA}" --sort-by TIMECREATED --sort-order DESC \
    --query 'data[0].id' --raw-output)" || return $?
  local v
  for v in AD SUBRED IMAGEN; do
    if [ -z "${!v}" ] || [ "${!v}" = "null" ]; then
      echo "No se encontró ${v}. ¿Existe una subred pública (la crea el asistente de VCN)?" >&2
      return 1
    fi
  done
}

# Un intento. Devuelve 0 creada (deja INSTANCIA), 2 sin capacidad,
# 3 Oracle pide esperar, 4 sin conexión, 1 error de verdad.
intentar() {
  local clave salida estado
  clave="$(mktemp)"
  printf '%s\n' "${CLAVE_SSH_PUBLICA}" > "${clave}"
  # --no-retry: ante «sin capacidad» la CLI reintenta sola durante casi
  # dos minutos; aquí el ritmo de los intentos lo marca ESPERA_S.
  salida="$(oci --no-retry compute instance launch \
    --availability-domain "${AD}" \
    --compartment-id "${OCI_COMPARTIMENTO}" \
    --display-name "${NOMBRE}" \
    --shape "${FORMA}" \
    --shape-config "{\"ocpus\": ${OCPUS}, \"memoryInGBs\": ${MEMORIA_GB}}" \
    --image-id "${IMAGEN}" \
    --boot-volume-size-in-gbs "${DISCO_GB}" \
    --subnet-id "${SUBRED}" \
    --assign-public-ip true \
    --ssh-authorized-keys-file "${clave}" \
    --wait-for-state RUNNING --max-wait-seconds 900 \
    --query 'data.id' --raw-output 2>&1)"
  estado=$?
  rm -f "${clave}"
  if [ "${estado}" -eq 0 ]; then
    INSTANCIA="$(printf '%s\n' "${salida}" | grep -o 'ocid1\.instance[^" ]*' | tail -1)"
    return 0
  fi
  if printf '%s' "${salida}" | grep -qi "capacity"; then return 2; fi
  if printf '%s' "${salida}" | grep -qi "TooManyRequests"; then return 3; fi
  if pasajero "${salida}"; then return 4; fi
  echo "${salida}" >&2
  explicar "${salida}"
  return 1
}

INSTANCIA="$(existente)" || exit $?
if [ -n "${INSTANCIA}" ]; then
  echo "$(hora) La instancia «${NOMBRE}» ya existe: ${INSTANCIA}"
else
  preparar || exit $?
  FIN=$(( $(date +%s) + DURACION_MIN * 60 ))
  INTENTOS=0
  while :; do
    INTENTOS=$((INTENTOS + 1))
    intentar
    case $? in
      0) echo "$(hora) ¡Instancia creada en el intento ${INTENTOS}! ${INSTANCIA}"; break ;;
      2) echo "$(hora) Intento ${INTENTOS}: sin capacidad en ${AD}."; ESPERA="${ESPERA_S}" ;;
      3) echo "$(hora) Intento ${INTENTOS}: Oracle pide esperar (TooManyRequests)."; ESPERA=$((ESPERA_S * 2)) ;;
      4) echo "$(hora) Intento ${INTENTOS}: sin conexión con Oracle."; ESPERA="${ESPERA_S}" ;;
      *) exit 1 ;;
    esac
    if [ $(( $(date +%s) + ESPERA )) -ge "${FIN}" ]; then
      echo "$(hora) Sin máquina tras ${INTENTOS} intento(s). Se reintenta en la próxima vuelta."
      exit 0
    fi
    sleep "${ESPERA}"
    # Por si se creó por otro lado (Cloud Shell, la consola) o la creó el
    # intento anterior aunque se cortara la conexión mientras arrancaba.
    # Sin poder mirarlo no se lanza otro: podría salir una segunda.
    INSTANCIA="$(existente)"
    ESTADO=$?
    while [ "${ESTADO}" -eq 4 ] && [ $(( $(date +%s) + ESPERA_S )) -lt "${FIN}" ]; do
      sleep "${ESPERA_S}"
      INSTANCIA="$(existente)"
      ESTADO=$?
    done
    [ "${ESTADO}" -eq 0 ] || exit "${ESTADO}"
    if [ -n "${INSTANCIA}" ]; then
      echo "$(hora) La instancia «${NOMBRE}» ya existe: ${INSTANCIA}"
      break
    fi
  done
fi

IP="$(oci compute instance list-vnics --instance-id "${INSTANCIA}" \
  --query 'data[0]."public-ip"' --raw-output 2>/dev/null)"
[ "${IP}" = "null" ] && IP=""
echo "IP pública: ${IP:-(todavía sin asignar)}"
printf '%s\n' "${IP}" > "${SALIDA_IP}"
