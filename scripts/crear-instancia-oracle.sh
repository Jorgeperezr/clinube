#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# Intenta crear UNA VEZ la máquina de Clinube en Oracle Cloud (Always
# Free, Ampere A1) y termina. Lo lanza cada media hora el flujo
# .github/workflows/oracle-instancia.yml, para no depender de dejar
# Cloud Shell abierto; también sirve a mano con la OCI CLI configurada.
#
# Por qué un intento y no un bucle: en Santiago casi nunca hay máquinas
# A1 libres, y un bucle cada minuto choca con el límite de peticiones de
# Oracle («TooManyRequests»). Un intento cada media hora, sin parar,
# gasta poco y no molesta a nadie.
#
# Salida, pensada para Actions:
#   0  creada (escribe la IP en ${SALIDA_IP}), ya existía, o no había
#      capacidad / Oracle pidió esperar: se reintenta en la próxima vuelta.
#   1  cualquier otro error (credenciales, OCID mal puesto…): eso no se
#      arregla esperando, y Actions avisa por correo.
#
# Variables (las de OCI las lee la propia CLI de ~/.oci/config):
#   OCI_COMPARTIMENTO   OCID del compartimento (por omisión, el arrendamiento)
#   CLAVE_SSH_PUBLICA   la clave pública con la que se entrará por SSH
#   OCPUS / MEMORIA_GB / DISCO_GB   tamaño (1 / 6 / 100: dentro de lo gratis)
#   NOMBRE              nombre de la instancia (clinube)
#   SALIDA_IP           archivo donde dejar la IP pública al crearla
# ─────────────────────────────────────────────────────────────────────
set -uo pipefail

NOMBRE="${NOMBRE:-clinube}"
OCPUS="${OCPUS:-1}"
MEMORIA_GB="${MEMORIA_GB:-6}"
DISCO_GB="${DISCO_GB:-100}"
FORMA="VM.Standard.A1.Flex"
SALIDA_IP="${SALIDA_IP:-/dev/null}"

hora() { date -u '+%H:%M UTC'; }

if [ -z "${OCI_COMPARTIMENTO:-}" ]; then
  OCI_COMPARTIMENTO="$(awk -F= '/^tenancy/ {gsub(/ /, "", $2); print $2; exit}' "${HOME}/.oci/config" 2>/dev/null)"
fi
if [ -z "${OCI_COMPARTIMENTO}" ] || [ -z "${CLAVE_SSH_PUBLICA:-}" ]; then
  echo "Faltan OCI_COMPARTIMENTO o CLAVE_SSH_PUBLICA." >&2
  exit 1
fi

# ── ¿Ya existe? Entonces no se crea otra: Always Free da para una. ────
EXISTENTE="$(oci compute instance list -c "${OCI_COMPARTIMENTO}" --all \
  --query "data[?\"display-name\"=='${NOMBRE}' && \"lifecycle-state\"!='TERMINATED' && \"lifecycle-state\"!='TERMINATING'] | [0].id" \
  --raw-output 2>&1)" || { echo "${EXISTENTE}" >&2; exit 1; }
if [ -n "${EXISTENTE}" ] && [ "${EXISTENTE}" != "null" ]; then
  echo "$(hora) La instancia «${NOMBRE}» ya existe: ${EXISTENTE}"
  INSTANCIA="${EXISTENTE}"
else
  # ── Lo que hace falta para crearla, buscado cada vez ───────────────
  # La imagen se busca y no se fija: Oracle publica una nueva cada pocas
  # semanas y retira las viejas, y un OCID fijo dejaría de valer.
  AD="$(oci iam availability-domain list -c "${OCI_COMPARTIMENTO}" --query 'data[0].name' --raw-output)" || exit 1
  SUBRED="$(oci network subnet list -c "${OCI_COMPARTIMENTO}" --all \
    --query 'data[?"prohibit-public-ip-on-vnic"==`false`] | [0].id' --raw-output)" || exit 1
  IMAGEN="$(oci compute image list -c "${OCI_COMPARTIMENTO}" --all \
    --operating-system "Canonical Ubuntu" --operating-system-version "24.04" \
    --shape "${FORMA}" --sort-by TIMECREATED --sort-order DESC \
    --query 'data[0].id' --raw-output)" || exit 1
  for v in AD SUBRED IMAGEN; do
    if [ -z "${!v}" ] || [ "${!v}" = "null" ]; then
      echo "No se encontró ${v}. ¿Existe una subred pública (la crea el asistente de VCN)?" >&2
      exit 1
    fi
  done

  CLAVE="$(mktemp)"
  printf '%s\n' "${CLAVE_SSH_PUBLICA}" > "${CLAVE}"
  # --no-retry: ante «sin capacidad» la CLI reintenta sola durante casi
  # dos minutos, que en Actions se pagan; la próxima vuelta ya reintenta.
  SALIDA="$(oci --no-retry compute instance launch \
    --availability-domain "${AD}" \
    --compartment-id "${OCI_COMPARTIMENTO}" \
    --display-name "${NOMBRE}" \
    --shape "${FORMA}" \
    --shape-config "{\"ocpus\": ${OCPUS}, \"memoryInGBs\": ${MEMORIA_GB}}" \
    --image-id "${IMAGEN}" \
    --boot-volume-size-in-gbs "${DISCO_GB}" \
    --subnet-id "${SUBRED}" \
    --assign-public-ip true \
    --ssh-authorized-keys-file "${CLAVE}" \
    --wait-for-state RUNNING --max-wait-seconds 900 \
    --query 'data.id' --raw-output 2>&1)"
  ESTADO=$?
  rm -f "${CLAVE}"

  if [ "${ESTADO}" -ne 0 ]; then
    if printf '%s' "${SALIDA}" | grep -qi "capacity"; then
      echo "$(hora) Sin capacidad en ${AD}. Se reintenta en la próxima vuelta."
      exit 0
    fi
    if printf '%s' "${SALIDA}" | grep -qi "TooManyRequests"; then
      echo "$(hora) Oracle pide esperar (TooManyRequests). Se reintenta en la próxima vuelta."
      exit 0
    fi
    if printf '%s' "${SALIDA}" | grep -qi "LimitExceeded"; then
      echo "Oracle dice que se superó el límite gratuito: ¿hay otra instancia A1 creada?" >&2
    fi
    echo "${SALIDA}" >&2
    exit 1
  fi
  INSTANCIA="$(printf '%s\n' "${SALIDA}" | grep -o 'ocid1\.instance[^" ]*' | tail -1)"
  echo "$(hora) ¡Instancia creada! ${INSTANCIA}"
fi

IP="$(oci compute instance list-vnics --instance-id "${INSTANCIA}" \
  --query 'data[0]."public-ip"' --raw-output 2>/dev/null)"
echo "IP pública: ${IP:-(todavía sin asignar)}"
printf '%s\n' "${IP}" > "${SALIDA_IP}"
