#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# Deja lista una VM Ubuntu recién creada para correr Clinube.
#
#   sudo bash scripts/preparar-servidor.sh               prepara
#   sudo bash scripts/preparar-servidor.sh --comprobar   solo revisa
#
# Qué hace, y por qué cada cosa:
#
#   1. Instala los parches pendientes y deja activadas las ACTUALIZACIONES
#      DE SEGURIDAD AUTOMÁTICAS (unattended-upgrades). En Oracle la
#      seguridad del sistema operativo es del cliente, no de Oracle, y
#      una VM sin parchear acaba siendo un problema de los dos.
#      Si un parche lo pide, la máquina se reinicia sola a las 08:00 UTC
#      (03:00 en Ecuador); Docker y el túnel arrancan solos al volver.
#   2. Instala Docker y rclone (este, para la copia fuera del servidor).
#   3. Comprueba que no quede NADA escuchando hacia internet salvo SSH.
#      El tráfico de la clínica entra por Cloudflare Tunnel, que sale
#      desde dentro; no hace falta abrir puertos ni en Oracle ni aquí.
#
# Qué NO hace, a propósito: tocar el cortafuegos. La imagen de Ubuntu de
# Oracle trae reglas de iptables que solo dejan pasar SSH, y así deben
# quedarse.
#
# Se puede volver a ejecutar: lo que ya está hecho se deja como está.
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

verde() { printf '\033[0;32m✓\033[0m %s\n' "$1"; }
rojo()  { printf '\033[0;31m✗\033[0m %s\n' "$1"; }
paso()  { printf '\n\033[1m▶ %s\033[0m\n' "$1"; }

# Lo que escucha en una dirección que no es la propia máquina, salvo SSH.
puertos_abiertos() {
    ss -tlnH 2>/dev/null \
        | awk '{print $4}' \
        | grep -vE '^(127\.[0-9.]+|\[::1\]|::1|\[::ffff:127\.[0-9.]+\])(%[a-z0-9]+)?:' \
        | grep -vE ':22$' \
        | sort -u || true
}

comprobar() {
    local fallos=0 abiertos

    paso "Actualizaciones automáticas"
    if dpkg -s unattended-upgrades >/dev/null 2>&1 \
        && apt-config dump 2>/dev/null | grep -q 'APT::Periodic::Unattended-Upgrade "1"'; then
        verde "unattended-upgrades instalado y activado"
    else
        rojo "unattended-upgrades no está activado"
        fallos=$((fallos + 1))
    fi

    paso "Programas"
    for p in docker rclone; do
        if command -v "${p}" >/dev/null 2>&1; then
            verde "${p}"
        else
            rojo "falta ${p}"
            fallos=$((fallos + 1))
        fi
    done

    paso "Puertos abiertos hacia fuera (aparte de SSH)"
    abiertos=$(puertos_abiertos)
    if [ -z "${abiertos}" ]; then
        verde "ninguno"
    else
        rojo "hay servicios escuchando hacia fuera:"
        printf '      %s\n' ${abiertos}
        echo "    Si es Nginx: NGINX_PUERTO en el .env debe ser 127.0.0.1:80."
        fallos=$((fallos + 1))
    fi

    echo ""
    if [ "${fallos}" -eq 0 ]; then
        verde "Servidor en orden."
    else
        rojo "${fallos} cosa(s) por corregir."
    fi
    return "${fallos}"
}

if [ "${1:-}" = "--comprobar" ]; then
    comprobar
    exit $?
fi

if [ "$(id -u)" -ne 0 ]; then
    echo "Hay que ejecutarlo con sudo: sudo bash $0" >&2
    exit 1
fi

export DEBIAN_FRONTEND=noninteractive

paso "Parches pendientes"
apt-get update -q
apt-get -y -q full-upgrade
apt-get -y -q install unattended-upgrades ca-certificates curl git rclone

paso "Actualizaciones de seguridad automáticas"
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'CONF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
CONF
cat > /etc/apt/apt.conf.d/52clinube <<'CONF'
// Clinube: reiniciar solo si un parche lo exige, de madrugada en Ecuador.
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "08:00";
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
CONF
systemctl enable --now unattended-upgrades >/dev/null
verde "activadas (registro en /var/log/unattended-upgrades/)"

paso "Docker"
if command -v docker >/dev/null 2>&1; then
    verde "ya estaba instalado"
else
    curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker >/dev/null
if [ -n "${SUDO_USER:-}" ] && [ "${SUDO_USER}" != "root" ]; then
    usermod -aG docker "${SUDO_USER}"
    verde "${SUDO_USER} puede usar docker (vuelve a entrar por SSH para que surta efecto)"
fi

if comprobar; then
    echo ""
    echo "Siguiente paso: los «Pasos comunes» de DEPLOY.md."
else
    exit 1
fi
