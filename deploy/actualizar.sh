#!/usr/bin/env bash
# Actualiza el panel de Xenomorfo-Q ya instalado con deploy/instalar.sh (D18).
#
# Uso, en el servidor: sudo bash /opt/xenomorfo-q/deploy/actualizar.sh
#
# Trae la rama main, reinstala las dependencias y reinicia el servicio. No toca
# /etc/xenomorfo-q.env ni el acceso de Caddy.
set -euo pipefail

RAMA="main"
DIR_APP="/opt/xenomorfo-q"

fallar() { printf 'Error: %s\n' "$1" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || fallar "ejecuta el script con sudo: sudo bash $DIR_APP/deploy/actualizar.sh"
[ -d "$DIR_APP/.git" ] || fallar "no está instalado en $DIR_APP; usa primero deploy/instalar.sh."

git -C "$DIR_APP" fetch -q origin "$RAMA"
git -C "$DIR_APP" checkout -q "$RAMA"
git -C "$DIR_APP" merge -q --ff-only "origin/$RAMA"
git -C "$DIR_APP" log -1 --format='Versión: %h %s'

"$DIR_APP/.venv/bin/pip" install -q -r "$DIR_APP/requirements.txt"

install -m 644 "$DIR_APP/deploy/xenomorfo-q.service" /etc/systemd/system/xenomorfo-q.service
systemctl daemon-reload
systemctl restart xenomorfo-q

for _ in 1 2 3 4 5 6 7 8 9 10; do
    if curl -sf -m 2 http://127.0.0.1:8000/salud >/dev/null; then
        printf 'Actualizado: el panel responde en 127.0.0.1:8000.\n'
        exit 0
    fi
    sleep 1
done
fallar "el panel no responde; revisa: sudo journalctl -u xenomorfo-q -n 50"
