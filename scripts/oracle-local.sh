#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# Crea la máquina de Clinube en Oracle desde tu ordenador, mientras esté
# encendido. Es lo que hacía el flujo de GitHub Actions, sin gastar sus
# minutos: intenta cada ESPERA_S segundos hasta que Oracle tenga sitio y
# avisa con una notificación. Quien habla con Oracle es
# scripts/crear-instancia-oracle.sh; este guion lo prepara y lo repite.
#
#   bash scripts/oracle-local.sh --configurar    la clave de API en este ordenador
#   bash scripts/oracle-local.sh --comprobar     qué falta, sin crear nada
#   bash scripts/oracle-local.sh                 intenta en esta ventana
#   bash scripts/oracle-local.sh --al-encender   (macOS) en segundo plano, y
#                                                vuelve a empezar al encender
#   bash scripts/oracle-local.sh --estado        cómo va
#   bash scripts/oracle-local.sh --parar         lo para
#
# La clave privada de la API se queda en este ordenador (~/.oci): solo
# la usa la CLI de Oracle para firmar las peticiones. A Oracle se le da
# la pública.
#
# Mientras intenta, el Mac no se duerme solo (caffeinate). Cerrar la tapa
# de un portátil sí lo duerme: déjala abierta. Al despertar, sigue.
#
# Variables: ESPERA_S (120), NOMBRE (clinube), OCPUS / MEMORIA_GB /
# DISCO_GB (1 / 6 / 100), CLAVE_SSH (~/.ssh/clinube).
#
# Las variables van SIEMPRE entre llaves —${VAR}— porque en macOS una
# variable pegada a un carácter no ASCII se traga esos bytes dentro del
# identificador (ver comprobar-guiones.sh).
# ─────────────────────────────────────────────────────────────────────
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUION="${DIR}/crear-instancia-oracle.sh"
USO="bash scripts/oracle-local.sh"

CARPETA="${HOME}/.clinube-oracle"
REGISTRO="${CARPETA}/registro.txt"
CANDADO="${CARPETA}/en-marcha"
IP_ARCHIVO="${CARPETA}/ip.txt"
ETIQUETA="com.clinube.oracle"
PLIST="${HOME}/Library/LaunchAgents/${ETIQUETA}.plist"
CONFIG_OCI="${OCI_CLI_CONFIG_FILE:-${HOME}/.oci/config}"
CLAVE_API="${HOME}/.oci/clinube_api_key.pem"
CLAVE_SSH="${CLAVE_SSH:-${HOME}/.ssh/clinube}"
REGION_DE_INICIO="sa-santiago-1"
ESPERA_S="${ESPERA_S:-120}"
NOMBRE="${NOMBRE:-clinube}"
export NOMBRE

if [ -t 1 ]; then
  verde()  { printf '\033[0;32m✓\033[0m %s\n' "$1"; }
  rojo()   { printf '\033[0;31m✗\033[0m %s\n' "$1"; }
  aviso()  { printf '\033[0;33m!\033[0m %s\n' "$1"; }
  titulo() { printf '\n\033[1m%s\033[0m\n' "$1"; }
else
  verde()  { printf '✓ %s\n' "$1"; }
  rojo()   { printf '✗ %s\n' "$1"; }
  aviso()  { printf '! %s\n' "$1"; }
  titulo() { printf '\n%s\n' "$1"; }
fi
hora() { date '+%d/%m %H:%M'; }

# Un valor del perfil DEFAULT de la configuración de OCI.
valor_config() {
  [ -f "${CONFIG_OCI}" ] || return 0
  awk -v clave="$1" '
    /^[ \t]*\[/ { seccion = $0; gsub(/[ \t]/, "", seccion); next }
    seccion == "[DEFAULT]" {
      linea = $0
      if (sub("^[ \t]*" clave "[ \t]*=", "", linea)) { gsub(/^[ \t]+|[ \t]+$/, "", linea); print linea; exit }
    }' "${CONFIG_OCI}"
}

# La huella de una clave privada, tal como la enseña Oracle (aa:bb:…).
huella_de() {
  openssl pkey -passin pass: -in "$1" -pubout -outform DER 2>/dev/null \
    | openssl md5 -c 2>/dev/null | awk '{print $NF}'
}

# Lo que deja la terminal al arrastrar un archivo: comillas, «\ » en los
# espacios y un espacio al final.
limpiar_ruta() {
  local r
  r="$(printf '%s' "$1" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' \
    -e "s/^'\(.*\)'\$/\1/" -e 's/^"\(.*\)"$/\1/' -e 's/\\\(.\)/\1/g')"
  case "${r}" in "~/"*) r="${HOME}/${r#\~/}" ;; esac
  printf '%s' "${r}"
}

# Los OCID tal como los da la vista previa de Oracle: con o sin «user=»
# delante y con espacios de más.
limpiar_valor() {
  printf '%s' "$1" | tr -d '\r' \
    | sed -E 's/^[[:space:]]*(user|tenancy|fingerprint|region)[[:space:]]*=//' | tr -d '[:space:]'
}

avisar() {
  local texto
  texto="$(printf '%s' "$1" | tr -d '"\\')"
  if command -v osascript >/dev/null 2>&1; then
    osascript -e "display notification \"${texto}\" with title \"Clinube · Oracle\" sound name \"Glass\"" >/dev/null 2>&1
  elif command -v notify-send >/dev/null 2>&1; then
    notify-send "Clinube · Oracle" "${texto}" >/dev/null 2>&1
  fi
}

# ── ¿Hay otro intento en marcha? ─────────────────────────────────────
# Dos a la vez gastan el cupo de peticiones de Oracle.
en_marcha() {
  local pid
  pid="$(cat "${CANDADO}/pid" 2>/dev/null)"
  if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
    printf '%s' "${pid}"
    return 0
  fi
  return 1
}

tomar_candado() {
  local pid
  if pid="$(en_marcha)"; then
    rojo "Ya hay un intento en marcha (proceso ${pid}). Para ver cómo va:"
    echo "${USO} --estado"
    return 1
  fi
  rm -rf "${CANDADO}"
  mkdir -p "${CANDADO}" && echo "$$" > "${CANDADO}/pid" && hora > "${CANDADO}/desde"
}

soltar_candado() {
  if [ "$(cat "${CANDADO}/pid" 2>/dev/null)" = "$$" ]; then rm -rf "${CANDADO}"; fi
}

# Para lo que cuelga de este proceso: el intento en curso, la CLI de
# Oracle que espera respuesta, el «sleep» y caffeinate.
matar_arbol() {
  local hijo
  for hijo in $(pgrep -P "$1" 2>/dev/null); do matar_arbol "${hijo}"; done
  kill -TERM "$1" 2>/dev/null
}
matar_hijos() {
  local hijo
  for hijo in $(pgrep -P "$$" 2>/dev/null); do matar_arbol "${hijo}"; done
}

mantener_despierto() {
  if command -v caffeinate >/dev/null 2>&1; then
    caffeinate -i -s -w "$$" >/dev/null 2>&1 &
  elif command -v systemd-inhibit >/dev/null 2>&1; then
    systemd-inhibit --what=idle:sleep --who=Clinube --why="Creando la máquina de Oracle" \
      bash -c "while kill -0 $$ 2>/dev/null; do sleep 60; done" >/dev/null 2>&1 &
  fi
}

# ── Comprobaciones ───────────────────────────────────────────────────

comprobar_cli() {
  if command -v oci >/dev/null 2>&1; then
    verde "CLI de Oracle: $(oci --version 2>/dev/null | head -1)"
    return 0
  fi
  rojo "No está instalada la CLI de Oracle (oci)."
  if command -v brew >/dev/null 2>&1; then
    echo "    Instálala con:"
    echo "    brew install oci-cli"
  elif [ "$(uname)" = "Darwin" ]; then
    echo "    Instala Homebrew (https://brew.sh) y después:"
    echo "    brew install oci-cli"
  else
    echo "    Instrucciones: https://docs.oracle.com/iaas/Content/API/SDKDocs/cliinstall.htm"
  fi
  return 1
}

# Lo justo para empezar a intentar; el resto lo dice Oracle al primer
# intento, con su mensaje.
lo_minimo() {
  local fallos=0
  comprobar_cli >/dev/null || { comprobar_cli; fallos=1; }
  if [ ! -f "${CONFIG_OCI}" ]; then
    rojo "Este ordenador no tiene la configuración de Oracle (${CONFIG_OCI}). Créala con:"
    echo "${USO} --configurar"
    fallos=1
  fi
  if [ ! -f "${CLAVE_SSH}.pub" ]; then
    rojo "No encuentro la clave SSH ${CLAVE_SSH}.pub, con la que entrarás en la máquina. Créala con:"
    echo "ssh-keygen -t ed25519 -f ${CLAVE_SSH} -C clinube"
    fallos=1
  fi
  return "${fallos}"
}

comprobar() {
  local fallos=0 usuario huella arrendamiento region clave calculada salida pid
  titulo "1. La CLI de Oracle"
  comprobar_cli || return 1

  titulo "2. La configuración (${CONFIG_OCI})"
  if [ ! -f "${CONFIG_OCI}" ]; then
    rojo "No existe. Créala con:"
    echo "${USO} --configurar"
    return 1
  fi
  usuario="$(valor_config user)"
  huella="$(valor_config fingerprint)"
  arrendamiento="$(valor_config tenancy)"
  region="$(valor_config region)"
  clave="$(limpiar_ruta "$(valor_config key_file)")"
  case "${usuario}" in ocid1.user.*) verde "Usuario" ;; *) rojo "Falta user= (ocid1.user…)"; fallos=$((fallos + 1)) ;; esac
  case "${arrendamiento}" in ocid1.tenancy.*) verde "Arrendamiento" ;; *) rojo "Falta tenancy= (ocid1.tenancy…)"; fallos=$((fallos + 1)) ;; esac
  if [ -z "${region}" ]; then
    aviso "Sin región: se usará ${REGION_DE_INICIO} (Santiago)."
  elif [ "${region}" != "${REGION_DE_INICIO}" ]; then
    aviso "Región ${region}. La máquina gratuita se crea en la región de inicio de la cuenta (en DEPLOY.md, Santiago: ${REGION_DE_INICIO})."
  else
    verde "Región ${region}"
  fi
  if [ -z "${clave}" ] || [ ! -f "${clave}" ]; then
    rojo "No encuentro la clave privada (key_file=${clave:-vacío})."
    fallos=$((fallos + 1))
  else
    calculada="$(huella_de "${clave}")"
    if [ -z "${calculada}" ]; then
      rojo "${clave} no se puede leer como clave privada (¿es la pública, o tiene contraseña?)."
      fallos=$((fallos + 1))
    elif [ "${calculada}" != "${huella}" ]; then
      rojo "La huella de la configuración (${huella:-vacía}) no es la de la clave (${calculada})."
      fallos=$((fallos + 1))
    else
      verde "Clave de API ${calculada}"
    fi
  fi

  titulo "3. Oracle acepta la clave"
  if [ "${fallos}" -gt 0 ]; then
    aviso "Antes hay que arreglar lo de arriba:"
    echo "${USO} --configurar"
    return 1
  fi
  if salida="$(OCI_CLI_REGION="${OCI_CLI_REGION:-${region:-${REGION_DE_INICIO}}}" \
      oci iam availability-domain list -c "${arrendamiento}" --query 'data[0].name' --raw-output 2>&1)"; then
    verde "Sí: dominio de disponibilidad $(printf '%s\n' "${salida}" | tail -1)"
  else
    case "${salida}" in
      *NotAuthenticated*)
        rojo "Oracle no la acepta (NotAuthenticated). En la consola, Mi perfil → Claves de API: tiene que aparecer la huella ${huella}. Si no está, agrega la clave pública:"
        echo "${USO} --configurar" ;;
      *) rojo "No se pudo preguntar a Oracle:"; printf '%s\n' "${salida}" | head -8 | sed 's/^/    /' ;;
    esac
    return 1
  fi
  export OCI_CLI_REGION="${OCI_CLI_REGION:-${region:-${REGION_DE_INICIO}}}"

  titulo "4. La red"
  salida="$(oci network subnet list -c "${arrendamiento}" --all \
    --query 'data[?"prohibit-public-ip-on-vnic"==`false`] | [0]."display-name"' --raw-output 2>/dev/null)"
  if [ -n "${salida}" ] && [ "${salida}" != "null" ]; then
    verde "Subred pública: ${salida}"
  else
    rojo "No hay una subred pública. Créala con el asistente de VCN (DEPLOY.md, «Pasos»)."
    fallos=$((fallos + 1))
  fi

  titulo "5. La clave SSH para entrar en la máquina"
  if [ -f "${CLAVE_SSH}.pub" ]; then
    verde "${CLAVE_SSH}.pub"
    [ -f "${CLAVE_SSH}" ] || aviso "Está la pública pero no la privada (${CLAVE_SSH}): sin ella no podrás entrar."
  else
    rojo "No encuentro ${CLAVE_SSH}.pub. Créala con:"
    echo "ssh-keygen -t ed25519 -f ${CLAVE_SSH} -C clinube"
    fallos=$((fallos + 1))
  fi

  titulo "6. La máquina"
  salida="$(oci compute instance list -c "${arrendamiento}" --all \
    --query "data[?\"display-name\"=='${NOMBRE}' && \"lifecycle-state\"!='TERMINATED' && \"lifecycle-state\"!='TERMINATING'] | [0].\"lifecycle-state\"" \
    --raw-output 2>/dev/null)"
  if [ -n "${salida}" ] && [ "${salida}" != "null" ]; then
    verde "«${NOMBRE}» ya existe (${salida}): no hace falta intentar nada."
  else
    echo "  Todavía no existe «${NOMBRE}»."
  fi
  if pid="$(en_marcha)"; then
    aviso "Hay un intento en marcha desde $(cat "${CANDADO}/desde" 2>/dev/null) (proceso ${pid})."
  fi

  echo ""
  if [ "${fallos}" -gt 0 ]; then
    rojo "${fallos} cosa(s) por arreglar."
    return 1
  fi
  verde "Todo listo. Para empezar a intentar:"
  echo "${USO}"
}

# ── Configurar la clave de API ───────────────────────────────────────

configurar() {
  local pem nueva=1 huella linea usuario="" arrendamiento="" region="" huella_oracle="" visto_clave=0 leidas=0 copia salida i
  if [ ! -t 0 ]; then rojo "Hace falta una terminal: se preguntan cosas."; exit 1; fi
  comprobar_cli || exit 1
  command -v openssl >/dev/null 2>&1 || { rojo "Falta openssl."; exit 1; }
  mkdir -p "${HOME}/.oci" && chmod 700 "${HOME}/.oci"

  titulo "1. La clave de API"
  echo "Oracle firma cada petición con una clave de API. Lo más seguro es crear una"
  echo "nueva aquí: la privada no sale de este ordenador y a Oracle solo se le da la pública."
  echo ""
  echo "Si prefieres usar el .pem que descargaste de Oracle, arrástralo a esta ventana."
  echo "Si no, pulsa Enter y se crea una nueva."
  read -r -p "> " pem
  pem="$(limpiar_ruta "${pem}")"
  if [ -n "${pem}" ]; then
    if [ ! -f "${pem}" ]; then rojo "No encuentro ${pem}."; exit 1; fi
    if [ -z "$(huella_de "${pem}")" ]; then
      rojo "Ese archivo no es una clave privada (¿es la pública?)."
      exit 1
    fi
    if [ "${pem}" != "${CLAVE_API}" ]; then
      [ -f "${CLAVE_API}" ] && mv "${CLAVE_API}" "${CLAVE_API}.antes-$(date +%Y%m%d-%H%M%S)"
      cp "${pem}" "${CLAVE_API}"
    fi
    chmod 600 "${CLAVE_API}"
    nueva=0
    verde "Se usa una copia en ${CLAVE_API}. La de ${pem} ya se puede borrar."
  elif [ -f "${CLAVE_API}" ]; then
    verde "Ya había una clave en ${CLAVE_API}: se usa esa."
  else
    ( umask 077; openssl genrsa -out "${CLAVE_API}" 2048 >/dev/null 2>&1 ) || { rojo "No se pudo crear la clave."; exit 1; }
    chmod 600 "${CLAVE_API}"
    verde "Clave creada en ${CLAVE_API}."
  fi
  huella="$(huella_de "${CLAVE_API}")"

  if [ "${nueva}" -eq 1 ]; then
    openssl pkey -in "${CLAVE_API}" -pubout -out "${CLAVE_API%.pem}_public.pem" 2>/dev/null
    echo ""
    echo "Ahora dale a Oracle la clave PÚBLICA (esta sí se puede compartir):"
    echo ""
    cat "${CLAVE_API%.pem}_public.pem"
    echo ""
    if command -v pbcopy >/dev/null 2>&1; then
      pbcopy < "${CLAVE_API%.pem}_public.pem"
      verde "Ya está copiada: en Oracle pégala con ⌘V."
    fi
    echo "En la consola de Oracle: icono de perfil (arriba a la derecha) → Mi perfil →"
    echo "Claves de API → Agregar clave de API → «Pegar una clave pública» → pegar → Agregar."
    echo "La huella que enseñe Oracle tiene que ser: ${huella}"
    echo "Si ya la habías agregado antes, no hace falta repetirlo."
    read -r -p "Pulsa Enter cuando esté agregada. " _
  fi

  titulo "2. Tu usuario y tu arrendamiento"
  echo "Al agregar la clave, Oracle enseña una «vista previa del archivo de configuración»"
  echo "(si ya la cerraste: Claves de API → ⋮ junto a la clave → Ver archivo de configuración)."
  echo "Cópiala entera, pégala aquí y pulsa Enter en una línea vacía:"
  while IFS= read -r linea; do
    linea="$(printf '%s' "${linea}" | tr -d '\r')"
    # Las líneas vacías antes de lo pegado no cuentan.
    if [ -z "${linea}" ] && [ "${leidas}" -eq 0 ]; then continue; fi
    leidas=$((leidas + 1))
    case "${linea}" in
      *user*=*) usuario="$(limpiar_valor "${linea}")" ;;
      *tenancy*=*) arrendamiento="$(limpiar_valor "${linea}")" ;;
      *region*=*) region="$(limpiar_valor "${linea}")" ;;
      *fingerprint*=*) huella_oracle="$(limpiar_valor "${linea}")" ;;
      *key_file*) visto_clave=1 ;;
    esac
    # key_file es la última línea de la vista previa: no hace falta más.
    if [ -z "${linea}" ] || [ "${visto_clave}" -eq 1 ]; then break; fi
  done
  case "${usuario}" in ocid1.user.*) ;; *)
    read -r -p "OCID de tu usuario (ocid1.user…): " usuario
    usuario="$(limpiar_valor "${usuario}")" ;;
  esac
  case "${arrendamiento}" in ocid1.tenancy.*) ;; *)
    read -r -p "OCID del arrendamiento (ocid1.tenancy…): " arrendamiento
    arrendamiento="$(limpiar_valor "${arrendamiento}")" ;;
  esac
  case "${usuario}" in ocid1.user.*) ;; *) rojo "Eso no es un OCID de usuario (empieza por ocid1.user.)."; exit 1 ;; esac
  case "${arrendamiento}" in ocid1.tenancy.*) ;; *) rojo "Eso no es un OCID de arrendamiento (empieza por ocid1.tenancy.)."; exit 1 ;; esac
  region="${region:-${REGION_DE_INICIO}}"
  if [ -n "${huella_oracle}" ] && [ "${huella_oracle}" != "${huella}" ]; then
    rojo "Esa vista previa es de otra clave (huella ${huella_oracle}); la de este ordenador es ${huella}."
    echo "    Pega la vista previa de la clave con la huella ${huella}, o agrégala si no está."
    exit 1
  fi

  titulo "3. Guardar"
  if [ -f "${CONFIG_OCI}" ]; then
    copia="${CONFIG_OCI}.antes-$(date +%Y%m%d-%H%M%S)"
    cp "${CONFIG_OCI}" "${copia}"
    aviso "La configuración que había queda en ${copia}."
  fi
  mkdir -p "$(dirname "${CONFIG_OCI}")"
  ( umask 077
    {
      echo "[DEFAULT]"
      echo "user=${usuario}"
      echo "fingerprint=${huella}"
      echo "tenancy=${arrendamiento}"
      echo "region=${region}"
      echo "key_file=${CLAVE_API}"
    } > "${CONFIG_OCI}" )
  chmod 600 "${CONFIG_OCI}"
  verde "Guardada en ${CONFIG_OCI}."

  titulo "4. Probar"
  # Una clave recién agregada puede tardar un poco en valer.
  for i in 1 2 3 4 5 6; do
    if salida="$(OCI_CLI_REGION="${region}" oci iam availability-domain list -c "${arrendamiento}" \
        --query 'data[0].name' --raw-output 2>&1)"; then
      verde "Oracle acepta la clave (dominio $(printf '%s\n' "${salida}" | tail -1))."
      echo ""
      echo "Siguiente, comprobar el resto:"
      echo "${USO} --comprobar"
      return 0
    fi
    case "${salida}" in
      *NotAuthenticated*) [ "${i}" -lt 6 ] && { echo "  Oracle aún no la reconoce; a veces tarda un minuto…"; sleep 15; } ;;
      *) break ;;
    esac
  done
  rojo "Oracle no acepta la clave todavía:"
  printf '%s\n' "${salida}" | head -8 | sed 's/^/    /'
  echo "    ¿Está agregada la pública con la huella ${huella}? Cuando lo esté:"
  echo "${USO} --comprobar"
  exit 1
}

# ── Intentar ─────────────────────────────────────────────────────────

intentar_hasta_crearla() {
  local clave_publica estado ip region
  lo_minimo || exit 1
  mkdir -p "${CARPETA}"
  tomar_candado || exit 1
  trap 'soltar_candado' EXIT
  trap 'echo ""; echo "$(hora) Parado."; matar_hijos; exit 130' INT TERM HUP

  region="$(valor_config region)"
  export OCI_CLI_REGION="${OCI_CLI_REGION:-${region:-${REGION_DE_INICIO}}}"
  if [ -z "${OCI_COMPARTIMENTO:-}" ]; then
    OCI_COMPARTIMENTO="$(valor_config tenancy)"
    export OCI_COMPARTIMENTO
  fi
  clave_publica="$(cat "${CLAVE_SSH}.pub")"
  rm -f "${IP_ARCHIVO}"
  mantener_despierto

  echo "$(hora) Intentando crear «${NOMBRE}» (${OCPUS:-1} OCPU, ${MEMORIA_GB:-6} GB, ${DISCO_GB:-100} GB de disco) en ${OCI_CLI_REGION}: un intento cada ${ESPERA_S} s."
  if [ -t 1 ]; then
    echo "Deja esta ventana abierta; Ctrl+C lo para. Para que siga sin la ventana y al encender el Mac:"
    echo "${USO} --al-encender"
  fi
  while :; do
    rm -f "${IP_ARCHIVO}.nueva"
    # En segundo plano y con «wait», para que Ctrl+C o --parar lo corten
    # al momento y no al acabar el intento en curso.
    CLAVE_SSH_PUBLICA="${clave_publica}" SALIDA_IP="${IP_ARCHIVO}.nueva" \
      DURACION_MIN=60 ESPERA_S="${ESPERA_S}" bash "${GUION}" &
    wait "$!"
    estado=$?
    case "${estado}" in
      0)
        if [ -f "${IP_ARCHIVO}.nueva" ]; then
          ip="$(tr -d '[:space:]' < "${IP_ARCHIVO}.nueva")"
          mv "${IP_ARCHIVO}.nueva" "${IP_ARCHIVO}"
          creada "${ip}"
          return 0
        fi
        # Una hora sin sitio: otra vuelta, que vuelve a buscar la imagen.
        ;;
      4)
        echo "$(hora) Sin conexión con Oracle; se reintenta en ${ESPERA_S} s."
        sleep "${ESPERA_S}" &
        wait "$!"
        ;;
      *)
        echo ""
        rojo "$(hora) Oracle respondió con un error que no se arregla esperando (su mensaje está arriba)."
        echo "Para ver qué falta:"
        echo "${USO} --comprobar"
        avisar "No se pudo seguir intentando crear la máquina. Mira el registro: ${USO} --estado"
        return 1
        ;;
    esac
  done
}

creada() {
  local ip="$1"
  echo ""
  verde "$(hora) La máquina «${NOMBRE}» está creada. IP pública: ${ip:-(todavía sin asignar; mírala en la consola)}"
  if [ -n "${ip}" ]; then
    echo "Para entrar:"
    echo "ssh -i ${CLAVE_SSH} ubuntu@${ip}"
  fi
  echo "Siguiente paso: DEPLOY.md, «Preparar el servidor»."
  avisar "La máquina de Clinube está creada. IP: ${ip:-sin asignar}"
  # Hecho: que no vuelva a arrancar al encender el Mac.
  rm -f "${PLIST}"
}

# ── En segundo plano (macOS) ─────────────────────────────────────────

xml() { printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'; }

al_encender() {
  local pid bin ruta_oci uid variable
  if [ "$(uname)" != "Darwin" ]; then
    rojo "Esto es para macOS. Aquí, déjalo en una terminal abierta:"
    echo "${USO}"
    exit 1
  fi
  lo_minimo || exit 1
  if pid="$(en_marcha)"; then
    rojo "Ya hay un intento en marcha (proceso ${pid}). Páralo antes (Ctrl+C en su ventana) o:"
    echo "${USO} --parar"
    exit 1
  fi
  # Una copia fuera de Documentos, Escritorio y Descargas: macOS no deja
  # que un proceso en segundo plano lea esas carpetas sin pedir permiso.
  bin="${CARPETA}/bin"
  mkdir -p "${bin}" "${HOME}/Library/LaunchAgents"
  cp "${DIR}/oracle-local.sh" "${GUION}" "${bin}/"
  ruta_oci="$(dirname "$(command -v oci)")"
  uid="$(id -u)"
  {
    echo '<?xml version="1.0" encoding="UTF-8"?>'
    echo '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">'
    echo '<plist version="1.0"><dict>'
    echo "  <key>Label</key><string>${ETIQUETA}</string>"
    echo '  <key>ProgramArguments</key><array>'
    echo "    <string>/bin/bash</string><string>$(xml "${bin}/oracle-local.sh")</string><string>--intentar</string>"
    echo '  </array>'
    echo '  <key>RunAtLoad</key><true/>'
    echo '  <key>ProcessType</key><string>Background</string>'
    echo "  <key>StandardOutPath</key><string>$(xml "${REGISTRO}")</string>"
    echo "  <key>StandardErrorPath</key><string>$(xml "${REGISTRO}")</string>"
    echo '  <key>EnvironmentVariables</key><dict>'
    echo "    <key>PATH</key><string>$(xml "${ruta_oci}"):/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>"
    for variable in ESPERA_S NOMBRE OCPUS MEMORIA_GB DISCO_GB CLAVE_SSH OCI_CLI_CONFIG_FILE OCI_CLI_REGION OCI_COMPARTIMENTO; do
      if [ -n "${!variable:-}" ]; then
        echo "    <key>${variable}</key><string>$(xml "${!variable}")</string>"
      fi
    done
    echo '  </dict>'
    echo '</dict></plist>'
  } > "${PLIST}"
  launchctl bootout "gui/${uid}/${ETIQUETA}" >/dev/null 2>&1
  if ! launchctl bootstrap "gui/${uid}" "${PLIST}" 2>/dev/null; then
    launchctl load -w "${PLIST}" || { rojo "macOS no aceptó el servicio (${PLIST})."; exit 1; }
  fi
  sleep 3
  if ! en_marcha >/dev/null; then
    rojo "No arrancó. Lo último del registro:"
    tail -n 8 "${REGISTRO}" 2>/dev/null | sed 's/^/    /'
    exit 1
  fi
  verde "En marcha en segundo plano. Sigue aunque cierres la Terminal y vuelve a empezar"
  echo "  cada vez que enciendas el Mac e inicies sesión, hasta crear la máquina."
  echo "  Al crearla llega una notificación y deja de arrancar solo."
  echo ""
  echo "Para ver cómo va:"
  echo "${USO} --estado"
  echo "Para pararlo:"
  echo "${USO} --parar"
}

estado() {
  local pid intentos
  if [ -s "${IP_ARCHIVO}" ]; then
    verde "La máquina está creada. IP: $(cat "${IP_ARCHIVO}")"
  fi
  if pid="$(en_marcha)"; then
    verde "Intentando desde $(cat "${CANDADO}/desde" 2>/dev/null) (proceso ${pid})."
  else
    aviso "Ahora no hay ningún intento en marcha."
  fi
  [ -f "${PLIST}" ] && echo "  Arranca solo al encender el Mac (--al-encender)."
  if [ -f "${REGISTRO}" ]; then
    intentos="$(grep -c 'Intento [0-9]' "${REGISTRO}" 2>/dev/null)"
    titulo "Lo último del registro (${intentos:-0} intento(s) en total)"
    tail -n 12 "${REGISTRO}"
  fi
}

parar() {
  local pid agente=0 algo=0
  if [ -f "${PLIST}" ]; then
    launchctl bootout "gui/$(id -u)/${ETIQUETA}" >/dev/null 2>&1 || launchctl unload "${PLIST}" >/dev/null 2>&1
    rm -f "${PLIST}"
    agente=1
  fi
  if pid="$(en_marcha)"; then
    kill -TERM "${pid}" 2>/dev/null
    algo=1
  fi
  if [ "${agente}" -eq 1 ]; then
    verde "Parado. Ya no arranca al encender el Mac."
  elif [ "${algo}" -eq 1 ]; then
    verde "Parado."
  else
    aviso "No había nada en marcha."
  fi
}

case "${1:-}" in
  ""|--intentar) intentar_hasta_crearla ;;
  --comprobar) comprobar ;;
  --configurar) configurar ;;
  --al-encender) al_encender ;;
  --estado) estado ;;
  --parar) parar ;;
  -h|--ayuda|--help) sed -n '3,22p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' ;;
  *) rojo "Opción desconocida: $1 (mira ${USO} --ayuda)"; exit 2 ;;
esac
