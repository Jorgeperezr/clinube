#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# Intenta crear la máquina de Clinube en Oracle Cloud (Always Free,
# Ampere A1). Lo lanza cada hora el flujo .github/workflows/oracle-
# instancia.yml, para no depender de dejar Cloud Shell abierto; también
# sirve a mano con la OCI CLI configurada.
#
# Por defecto, un solo intento. Con DURACION_MIN, repite cada ESPERA_S
# segundos hasta crearla o hasta agotar ese tiempo: GitHub descarta la
# mayoría de las ejecuciones programadas frecuentes (de 78 previstas en
# una noche corrieron 2), así que cada ejecución que sí corre intenta
# durante casi una hora. Cada 5 minutos no choca con el límite de
# peticiones de Oracle; si aun así lo pide («TooManyRequests»), se espera
# el doble.
#
# Salida, pensada para Actions:
#   0  creada (escribe la IP en ${SALIDA_IP}), ya existía, o se acabó el
#      tiempo sin capacidad: se reintenta en la próxima ejecución.
#   1  cualquier otro error (credenciales, OCID mal puesto…): eso no se
#      arregla esperando, y Actions avisa por correo.
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

hora() { date -u '+%H:%M UTC'; }

if [ -z "${OCI_COMPARTIMENTO:-}" ]; then
  OCI_COMPARTIMENTO="$(awk -F= '/^tenancy/ {gsub(/ /, "", $2); print $2; exit}' "${HOME}/.oci/config" 2>/dev/null)"
fi
if [ -z "${OCI_COMPARTIMENTO}" ] || [ -z "${CLAVE_SSH_PUBLICA:-}" ]; then
  echo "Faltan OCI_COMPARTIMENTO o CLAVE_SSH_PUBLICA." >&2
  exit 1
fi

# ¿Ya existe una instancia con este nombre? Devuelve su OCID o nada.
# Always Free da para una: nunca se crea otra.
existente() {
  local r
  r="$(oci compute instance list -c "${OCI_COMPARTIMENTO}" --all \
    --query "data[?\"display-name\"=='${NOMBRE}' && \"lifecycle-state\"!='TERMINATED' && \"lifecycle-state\"!='TERMINATING'] | [0].id" \
    --raw-output 2>&1)" || { echo "${r}" >&2; return 1; }
  [ "${r}" = "null" ] && r=""
  printf '%s' "${r}"
}

# Lo que hace falta para crearla, buscado una vez por ejecución. La
# imagen se busca y no se fija: Oracle publica una nueva cada pocas
# semanas y retira las viejas, y un OCID fijo dejaría de valer.
preparar() {
  AD="$(oci iam availability-domain list -c "${OCI_COMPARTIMENTO}" --query 'data[0].name' --raw-output)" || return 1
  SUBRED="$(oci network subnet list -c "${OCI_COMPARTIMENTO}" --all \
    --query 'data[?"prohibit-public-ip-on-vnic"==`false`] | [0].id' --raw-output)" || return 1
  IMAGEN="$(oci compute image list -c "${OCI_COMPARTIMENTO}" --all \
    --operating-system "Canonical Ubuntu" --operating-system-version "24.04" \
    --shape "${FORMA}" --sort-by TIMECREATED --sort-order DESC \
    --query 'data[0].id' --raw-output)" || return 1
  local v
  for v in AD SUBRED IMAGEN; do
    if [ -z "${!v}" ] || [ "${!v}" = "null" ]; then
      echo "No se encontró ${v}. ¿Existe una subred pública (la crea el asistente de VCN)?" >&2
      return 1
    fi
  done
}

# Un intento. Devuelve 0 creada (deja INSTANCIA), 2 sin capacidad,
# 3 Oracle pide esperar, 1 error de verdad.
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
  if printf '%s' "${salida}" | grep -qi "LimitExceeded"; then
    echo "Oracle dice que se superó el límite gratuito: ¿hay otra instancia A1 creada?" >&2
  fi
  echo "${salida}" >&2
  return 1
}

INSTANCIA="$(existente)" || exit 1
if [ -n "${INSTANCIA}" ]; then
  echo "$(hora) La instancia «${NOMBRE}» ya existe: ${INSTANCIA}"
else
  preparar || exit 1
  FIN=$(( $(date +%s) + DURACION_MIN * 60 ))
  INTENTOS=0
  while :; do
    INTENTOS=$((INTENTOS + 1))
    intentar
    case $? in
      0) echo "$(hora) ¡Instancia creada en el intento ${INTENTOS}! ${INSTANCIA}"; break ;;
      2) echo "$(hora) Intento ${INTENTOS}: sin capacidad en ${AD}."; ESPERA="${ESPERA_S}" ;;
      3) echo "$(hora) Intento ${INTENTOS}: Oracle pide esperar (TooManyRequests)."; ESPERA=$((ESPERA_S * 2)) ;;
      *) exit 1 ;;
    esac
    if [ $(( $(date +%s) + ESPERA )) -ge "${FIN}" ]; then
      echo "$(hora) Sin máquina tras ${INTENTOS} intento(s). Se reintenta en la próxima ejecución."
      exit 0
    fi
    sleep "${ESPERA}"
    # Por si se creó por otro lado (Cloud Shell, la consola) mientras tanto.
    INSTANCIA="$(existente)" || exit 1
    if [ -n "${INSTANCIA}" ]; then
      echo "$(hora) La instancia «${NOMBRE}» ya existe: ${INSTANCIA}"
      break
    fi
  done
fi

IP="$(oci compute instance list-vnics --instance-id "${INSTANCIA}" \
  --query 'data[0]."public-ip"' --raw-output 2>/dev/null)"
echo "IP pública: ${IP:-(todavía sin asignar)}"
printf '%s\n' "${IP}" > "${SALIDA_IP}"
