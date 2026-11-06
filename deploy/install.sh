#!/usr/bin/env bash
# Builds Parable on the VM and installs two always-on services (Arkiv helper + engine) behind Caddy HTTPS.
# Run from ~/parable:  bash deploy/install.sh <dns-name>
# The services start only once ~/parable/.env exists (copy it from your laptop; it is never in git).
set -euo pipefail
DNS="${1:-parable-demo.centralindia.cloudapp.azure.com}"
APP="$HOME/parable"
UV="$HOME/.local/bin/uv"
cd "$APP/engine" && "$UV" sync --frozen 2>/dev/null || "$UV" sync
cd "$APP/arkiv-bridge" && npm ci --silent
cd "$APP/frontend" && npm ci --silent && npm run build --silent

sudo tee /etc/systemd/system/parable-bridge.service >/dev/null <<UNIT
[Unit]
Description=Parable Arkiv helper (Node, 127.0.0.1:8787)
After=network-online.target
ConditionPathExists=$APP/.env
[Service]
User=$USER
WorkingDirectory=$APP/arkiv-bridge
ExecStart=/usr/bin/node index.mjs
Restart=always
RestartSec=3
[Install]
WantedBy=multi-user.target
UNIT

# ONE engine process only: running bots live in its memory.
sudo tee /etc/systemd/system/parable-engine.service >/dev/null <<UNIT
[Unit]
Description=Parable engine (FastAPI, 127.0.0.1:8000)
After=parable-bridge.service
Requires=parable-bridge.service
ConditionPathExists=$APP/.env
[Service]
User=$USER
WorkingDirectory=$APP/engine
Environment=WORLD_REDIRECT_URI=https://$DNS/world/callback
ExecStart=$UV run uvicorn parable.api:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3
[Install]
WantedBy=multi-user.target
UNIT

echo "$DNS {
  reverse_proxy 127.0.0.1:8000
}" | sudo tee /etc/caddy/Caddyfile >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable parable-bridge parable-engine >/dev/null
sudo systemctl restart caddy
if [ -f "$APP/.env" ]; then sudo systemctl restart parable-bridge parable-engine; echo "services started"; else echo "add ~/parable/.env, then: sudo systemctl start parable-bridge parable-engine"; fi
