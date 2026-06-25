#!/bin/bash
set -e
REPO="git@github.com:rudybo/careeros.git"
DIR=~/CareerOS

echo "======================================"
echo "  CareerOS Server Setup / Update"
echo "======================================"

# ── 1. Clone o pull ───────────────────────
if [ ! -d "$DIR/.git" ]; then
  echo "[1/6] Clone repository..."
  git clone "$REPO" "$DIR"
else
  echo "[1/6] Pull aggiornamenti..."
  cd "$DIR" && git pull
fi

# ── 2. Backend venv + dipendenze ──────────
echo "[2/6] Backend Python..."
cd "$DIR/backend"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q

# ── 3. Frontend build ─────────────────────
echo "[3/6] Build frontend..."
cd "$DIR/frontend"
npm install --silent
npm run build

# ── 4. Nginx ──────────────────────────────
echo "[4/6] Nginx..."
if ! command -v nginx &>/dev/null; then
  sudo apt-get install -y nginx -q
fi

sudo tee /etc/nginx/sites-available/careeros > /dev/null << 'NGINX'
server {
    listen 80;
    server_name _;

    root /home/rudy/CareerOS/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300;
        proxy_send_timeout 300;
    }
}
NGINX

sudo ln -sf /etc/nginx/sites-available/careeros /etc/nginx/sites-enabled/careeros
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl reload nginx

# ── 5. Systemd backend service ────────────
echo "[5/6] Servizio backend (systemd)..."
sudo tee /etc/systemd/system/careeros-backend.service > /dev/null << 'SERVICE'
[Unit]
Description=CareerOS Backend
After=network.target docker.service
Wants=docker.service

[Service]
User=rudy
WorkingDirectory=/home/rudy/CareerOS/backend
ExecStart=/home/rudy/CareerOS/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable careeros-backend
sudo systemctl restart careeros-backend

# ── 6. LLM ────────────────────────────────
# Si usa Groq (cloud) → niente Ollama sul server (VM da 4GB). Vedi LLM_PROVIDER nel .env.
echo "[6/6] LLM: provider Groq (cloud) — nessun Ollama da installare."

echo ""
echo "======================================"
echo "  ✓ CareerOS pronto!"
echo "  → http://srvsviluppo"
echo "======================================"
