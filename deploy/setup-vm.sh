#!/usr/bin/env bash
# One-time setup of an Ubuntu 24.04 VM for Parable: Node 22 (Arkiv helper + building the website),
# uv (Python engine) and Caddy (HTTPS in front of the engine). Safe to run again.
set -euo pipefail
sudo apt-get update -y
sudo apt-get install -y curl git debian-keyring debian-archive-keyring apt-transport-https rsync
if ! command -v node >/dev/null || ! node -v | grep -q '^v22'; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  sudo apt-get update -y && sudo apt-get install -y caddy
fi
if ! command -v uv >/dev/null && [ ! -x "$HOME/.local/bin/uv" ]; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
echo "setup done: node $(node -v), caddy $(caddy version | cut -d' ' -f1), uv $($HOME/.local/bin/uv --version 2>/dev/null || uv --version)"
