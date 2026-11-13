#!/usr/bin/env bash
# Instala el panel de Xenomorfo-Q en una instancia Ubuntu 24.04, detrás de Caddy (D18).
#
# Uso, en el servidor:
#   curl -fsSLO https://raw.githubusercontent.com/jalvarez01/Xenomorfo-Q/main/deploy/instalar.sh
#   sudo bash instalar.sh
#
# Se puede correr varias veces: actualiza lo que ya existe y no toca /etc/xenomorfo-q.env
# si ya está creado. Pide el dominio, el usuario y la contraseña del acceso; de la
# contraseña solo guarda el hash bcrypt que produce `caddy hash-password`.
# Nunca muestra el contenido de /etc/xenomorfo-q.env ni la contraseña.
set -euo pipefail

REPO_URL="${XQ_REPO_URL:-https://github.com/jalvarez01/Xenomorfo-Q.git}"
RAMA="main"
DIR_APP="/opt/xenomorfo-q"
USUARIO_SERVICIO="xq"
ARCHIVO_ENV="/etc/xenomorfo-q.env"
ARCHIVO_ACCESO="/etc/caddy/xenomorfo-q-acceso"
CADDYFILE="/etc/caddy/Caddyfile"
LLAVERO_CADDY="/usr/share/keyrings/caddy-stable-archive-keyring.gpg"
LISTA_CADDY="/etc/apt/sources.list.d/caddy-stable.list"
LARGO_MIN_CLAVE=10

paso() { printf '\n==> %s\n' "$1"; }
fallar() { printf 'Error: %s\n' "$1" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || fallar "ejecuta el script con sudo: sudo bash instalar.sh"
if ! grep -q 'VERSION_ID="24.04"' /etc/os-release 2>/dev/null; then
    printf 'Aviso: el script está probado para Ubuntu 24.04.\n'
fi

paso "Paquetes del sistema (python3-venv, git, curl)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-venv git curl gpg debian-keyring debian-archive-keyring apt-transport-https >/dev/null

paso "Caddy desde su repositorio oficial"
if [ ! -f "$LLAVERO_CADDY" ]; then
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o "$LLAVERO_CADDY"
    chmod o+r "$LLAVERO_CADDY"
fi
if [ ! -f "$LISTA_CADDY" ]; then
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > "$LISTA_CADDY"
    chmod o+r "$LISTA_CADDY"
    apt-get update -qq
fi
apt-get install -y -qq caddy >/dev/null

paso "Usuario del servicio ($USUARIO_SERVICIO)"
if ! id -u "$USUARIO_SERVICIO" >/dev/null 2>&1; then
    useradd --system --no-create-home --home-dir "$DIR_APP" --shell /usr/sbin/nologin "$USUARIO_SERVICIO"
fi

paso "Código en $DIR_APP (rama $RAMA)"
if [ -d "$DIR_APP/.git" ]; then
    git -C "$DIR_APP" fetch -q origin "$RAMA"
    git -C "$DIR_APP" checkout -q "$RAMA"
    git -C "$DIR_APP" merge -q --ff-only "origin/$RAMA"
elif [ -e "$DIR_APP" ]; then
    fallar "$DIR_APP existe pero no es un repositorio git; muévelo y vuelve a correr el script."
else
    git clone -q --branch "$RAMA" "$REPO_URL" "$DIR_APP"
fi
git -C "$DIR_APP" log -1 --format='Versión: %h %s'

paso "Entorno virtual y dependencias"
if [ ! -x "$DIR_APP/.venv/bin/python" ]; then
    python3 -m venv "$DIR_APP/.venv"
fi
"$DIR_APP/.venv/bin/pip" install -q --upgrade pip
"$DIR_APP/.venv/bin/pip" install -q -r "$DIR_APP/requirements.txt"

paso "Variables del servicio ($ARCHIVO_ENV)"
if [ ! -f "$ARCHIVO_ENV" ]; then
    install -m 600 -o root -g "$USUARIO_SERVICIO" "$DIR_APP/deploy/xenomorfo-q.env.plantilla" "$ARCHIVO_ENV"
    printf 'Creado vacío; hay que completarlo (ver los pasos siguientes).\n'
else
    chown root:"$USUARIO_SERVICIO" "$ARCHIVO_ENV"
    chmod 600 "$ARCHIVO_ENV"
    printf 'Ya existe; no se modifica.\n'
fi

paso "Servicio systemd"
install -m 644 "$DIR_APP/deploy/xenomorfo-q.service" /etc/systemd/system/xenomorfo-q.service
systemctl daemon-reload
systemctl enable -q xenomorfo-q
systemctl restart xenomorfo-q

paso "Acceso al panel (dominio, usuario y contraseña)"
leer_valor() { sed -n "s/^$1=//p" "$ARCHIVO_ACCESO" 2>/dev/null | head -n 1; }
pedir_acceso="s"
if [ -f "$ARCHIVO_ACCESO" ]; then
    printf 'Ya hay un acceso configurado para %s con el usuario %s.\n' "$(leer_valor XQ_DOMINIO)" "$(leer_valor XQ_USUARIO)"
    read -r -p "¿Cambiar el dominio, el usuario o la contraseña? [s/N] " pedir_acceso
fi
if [ "${pedir_acceso,,}" = "s" ]; then
    sugerido=""
    token_imds="$(curl -sf -m 2 -X PUT http://169.254.169.254/latest/api/token \
        -H 'X-aws-ec2-metadata-token-ttl-seconds: 60' || true)"
    if [ -n "$token_imds" ]; then
        ip_publica="$(curl -sf -m 2 -H "X-aws-ec2-metadata-token: $token_imds" \
            http://169.254.169.254/latest/meta-data/public-ipv4 || true)"
        [ -n "$ip_publica" ] && sugerido="${ip_publica//./-}.sslip.io"
    fi
    read -r -p "Dominio [${sugerido:-sin sugerencia}]: " dominio
    dominio="${dominio:-$sugerido}"
    [[ "$dominio" =~ ^[A-Za-z0-9.-]+$ ]] || fallar "dominio inválido."
    read -r -p "Usuario del acceso [equipo]: " usuario
    usuario="${usuario:-equipo}"
    [[ "$usuario" =~ ^[A-Za-z0-9_.-]+$ ]] || fallar "usuario inválido: usa letras, números, punto, guion o guion bajo."
    read -r -s -p "Contraseña (mínimo $LARGO_MIN_CLAVE caracteres, no se muestra): " clave; printf '\n'
    read -r -s -p "Repite la contraseña: " clave2; printf '\n'
    [ "$clave" = "$clave2" ] || fallar "las contraseñas no coinciden."
    [ "${#clave}" -ge "$LARGO_MIN_CLAVE" ] || fallar "la contraseña debe tener al menos $LARGO_MIN_CLAVE caracteres."
    # Por la entrada estándar: así la contraseña no aparece en la lista de procesos.
    hash_clave="$(printf '%s\n' "$clave" | caddy hash-password | tail -n 1)"
    unset clave clave2
    [[ "$hash_clave" =~ ^[^[:space:]]+$ ]] || fallar "caddy hash-password no devolvió un hash."
    umask 077
    printf 'XQ_DOMINIO=%s\nXQ_USUARIO=%s\nXQ_HASH=%s\n' "$dominio" "$usuario" "$hash_clave" > "$ARCHIVO_ACCESO"
    umask 022
    chmod 600 "$ARCHIVO_ACCESO"
fi
[ -f "$ARCHIVO_ACCESO" ] || fallar "falta el acceso; vuelve a correr el script y responde s."

paso "Caddyfile"
XQ_DOMINIO="$(leer_valor XQ_DOMINIO)" XQ_USUARIO="$(leer_valor XQ_USUARIO)" XQ_HASH="$(leer_valor XQ_HASH)" \
    python3 - "$DIR_APP/deploy/Caddyfile.plantilla" "$CADDYFILE" <<'PY'
import os, sys
lineas = []
for linea in open(sys.argv[1], encoding="utf-8"):
    # Los comentarios quedan como están: el hash solo va en la línea de basic_auth.
    if not linea.lstrip().startswith("#"):
        for nombre in ("XQ_DOMINIO", "XQ_USUARIO", "XQ_HASH"):
            linea = linea.replace("{$" + nombre + "}", os.environ[nombre])
    lineas.append(linea)
with open(sys.argv[2], "w", encoding="utf-8") as archivo:
    archivo.writelines(lineas)
PY
chown root:caddy "$CADDYFILE"
chmod 640 "$CADDYFILE"
caddy validate --config "$CADDYFILE" --adapter caddyfile >/dev/null 2>&1 || fallar "el Caddyfile no es válido: revisa con sudo caddy validate --config $CADDYFILE"
systemctl enable -q caddy
systemctl reload caddy 2>/dev/null || systemctl restart caddy

paso "Comprobación"
for _ in 1 2 3 4 5 6 7 8 9 10; do
    if curl -sf -m 2 http://127.0.0.1:8000/salud >/dev/null; then
        printf 'El panel responde en 127.0.0.1:8000.\n'
        break
    fi
    sleep 1
done
curl -sf -m 2 http://127.0.0.1:8000/salud >/dev/null || fallar "el panel no responde; revisa: sudo journalctl -u xenomorfo-q -n 50"

dominio_final="$(leer_valor XQ_DOMINIO)"
cat <<FIN

Listo. Pasos siguientes:
  1. Completa las variables (proveedor y clave del modelo):
       sudo nano $ARCHIVO_ENV
     Pon XQ_PROVEEDOR=openai y OPENAI_API_KEY con la clave. No copies ese archivo a ningún lado.
  2. Reinicia el panel para que las lea:
       sudo systemctl restart xenomorfo-q
  3. Abre https://$dominio_final/ en el navegador y entra con el usuario y la contraseña.
     Comprobación sin contraseña: curl https://$dominio_final/salud
  4. Para actualizar más adelante: sudo bash $DIR_APP/deploy/actualizar.sh
FIN
