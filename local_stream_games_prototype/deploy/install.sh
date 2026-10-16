#!/usr/bin/env bash
# Instalador para Kali Linux (ou qualquer Debian/Ubuntu com systemd).
# Uso:  bash deploy/install.sh [seu_usuario_tiktok]
#
# O que ele faz:
#   1. instala o python3-venv
#   2. cria o .venv e instala as dependencias
#   3. cria o .env com GAME_TOKEN aleatorio, se ainda nao existir
#   4. instala e habilita os dois servicos do systemd
#   5. mostra o estado final e o endereco para abrir no OBS
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TIKTOK_USER="${1:-}"
SERVICE_USER="${SUDO_USER:-$USER}"

echo "==> projeto em $APP_DIR"

# 1. dependencias do sistema
if ! dpkg -s python3-venv >/dev/null 2>&1; then
  echo "==> instalando python3-venv"
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3-venv
fi

# 2. venv + pip
echo "==> criando ambiente virtual"
[ -d "$APP_DIR/.venv" ] || python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

# 3. .env
if [ ! -f "$APP_DIR/.env" ]; then
  echo "==> criando .env"
  TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
  sed -e "s|^GAME_TOKEN=.*|GAME_TOKEN=$TOKEN|" \
      -e "s|^TIKTOK_USERNAME=.*|TIKTOK_USERNAME=$TIKTOK_USER|" \
      "$APP_DIR/.env.example" > "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
  echo "    GAME_TOKEN gerado. Este valor nao pode vazar (ele libera o envio de eventos)."
else
  echo "==> .env ja existe, mantido como esta"
fi

# 4. systemd
for unit in streamgames-server streamgames-bot; do
  echo "==> instalando $unit.service"
  sed -e "s|__USER__|$SERVICE_USER|g" -e "s|__HOME__|/home/$SERVICE_USER|g" \
      "$APP_DIR/deploy/$unit.service" > "/tmp/$unit.service"
  sudo install -m 644 "/tmp/$unit.service" "/etc/systemd/system/$unit.service"
  sudo systemctl daemon-reload
  sudo systemctl enable --now "$unit"
done

# 5. conferencia
PORT="$(grep -E '^PORT=' "$APP_DIR/.env" | cut -d= -f2 || echo 8080)"
echo
echo "==> status"
systemctl --no-pager --lines=0 status streamgames-server streamgames-bot | grep -E '●|Active' || true
echo
echo "Jogo em:    http://localhost:$PORT/"
echo "Ao vivo:    http://SEU_IP:$PORT/  (OBS: fonte de navegador)"
echo "Logs:       journalctl -u streamgames-server -f"
echo "Reiniciar:  sudo systemctl restart streamgames-server streamgames-bot"
