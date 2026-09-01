#!/bin/bash
# ── ColdLeads VPS Setup Script ────────────────────────────
# Run as root on Ubuntu 20.04/22.04
# Usage: bash setup_vps.sh

set -e

PORT=6002
APP_DIR="/opt/coldleads"
SERVICE_NAME="coldleads"

echo "======================================"
echo "  ColdLeads VPS Setup — Port $PORT"
echo "======================================"

# ── 1. System packages ─────────────────────────────────────
echo "[1/7] Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
    python3 python3-pip python3-venv \
    curl wget unzip git screen \
    fonts-liberation libappindicator3-1 \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 \
    libcups2 libdbus-1-3 libgdk-pixbuf2.0-0 \
    libnspr4 libnss3 libx11-xcb1 libxcomposite1 \
    libxcursor1 libxdamage1 libxfixes3 libxi6 \
    libxrandr2 libxss1 libxtst6 xdg-utils \
    libgbm1 libxkbcommon0 libpango-1.0-0 \
    ca-certificates gnupg lsb-release

# ── 2. Google Chrome ───────────────────────────────────────
echo "[2/7] Installing Google Chrome..."
if ! command -v google-chrome &> /dev/null; then
    wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    apt-get install -y -qq ./google-chrome-stable_current_amd64.deb
    rm google-chrome-stable_current_amd64.deb
    echo "Chrome installed: $(google-chrome --version)"
else
    echo "Chrome already installed: $(google-chrome --version)"
fi

# ── 3. Node.js 20 ─────────────────────────────────────────
echo "[3/7] Installing Node.js 20..."
if ! command -v node &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y -qq nodejs
fi
echo "Node: $(node --version) | npm: $(npm --version)"

# ── 4. Clone / update repo ────────────────────────────────
echo "[4/7] Setting up application..."
echo ""
echo "  GitHub repo clone karne ke liye Personal Access Token chahiye."
echo "  GitHub → Settings → Developer Settings → Personal Access Tokens → Tokens (classic)"
echo "  'repo' permission de kar token banao."
echo ""
read -p "  GitHub Username: " GH_USER
read -p "  Personal Access Token: " GH_TOKEN
read -p "  Repo name (e.g. scraper-stage-2): " GH_REPO

REPO_URL="https://${GH_USER}:${GH_TOKEN}@github.com/${GH_USER}/${GH_REPO}.git"

if [ -d "$APP_DIR" ]; then
    echo "  Updating existing installation..."
    cd "$APP_DIR"
    git pull "$REPO_URL" main
else
    echo "  Cloning repo..."
    git clone "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
fi

# ── 5. Python virtualenv + dependencies ───────────────────
echo "[5/7] Installing Python dependencies..."
cd "$APP_DIR/backend"
python3 -m venv venv
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r ../requirements.txt

# ── 6. Create .env file ───────────────────────────────────
echo "[6/7] Setting up .env config..."
SERVER_IP=$(curl -s ifconfig.me)
if [ ! -f "$APP_DIR/backend/.env" ]; then
    echo ""
    echo "  .env file bana rahe hain — apni values enter karo:"
    read -p "  JWT Secret (blank = auto-generate): " JWT_SECRET
    JWT_SECRET=${JWT_SECRET:-$(openssl rand -hex 32)}
    read -p "  Admin Email [$GH_USER@coldleads.com]: " ADMIN_EMAIL
    ADMIN_EMAIL=${ADMIN_EMAIL:-"$GH_USER@coldleads.com"}
    read -s -p "  Admin Password (strong): " ADMIN_PASSWORD
    echo ""

    cat > "$APP_DIR/backend/.env" <<ENVEOF
JWT_SECRET=${JWT_SECRET}
PRODUCTION=1
ALLOWED_ORIGINS=http://${SERVER_IP}:${PORT}
ADMIN_EMAIL=${ADMIN_EMAIL}
ADMIN_PASSWORD=${ADMIN_PASSWORD}
ENVEOF
    echo "  .env created."
else
    echo "  .env already exists — skipping."
fi

# ── 7. Build React frontend ────────────────────────────────
echo "[7/7] Building React frontend..."
cd "$APP_DIR/frontend"
npm install -q
npm run build
echo "  Frontend built → frontend/dist/"

# ── Systemd service ───────────────────────────────────────
echo "Setting up systemd service..."
cat > /etc/systemd/system/${SERVICE_NAME}.service <<SERVICEEOF
[Unit]
Description=ColdLeads Scraper SaaS
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${APP_DIR}/backend
Environment="PATH=${APP_DIR}/backend/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=${APP_DIR}/backend/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF

systemctl daemon-reload
systemctl enable ${SERVICE_NAME}
systemctl restart ${SERVICE_NAME}

sleep 3
STATUS=$(systemctl is-active ${SERVICE_NAME})

echo ""
echo "======================================"
if [ "$STATUS" = "active" ]; then
    echo "  ✅ ColdLeads is RUNNING!"
    echo "  🌐 URL: http://${SERVER_IP}:${PORT}"
    echo ""
    echo "  Useful commands:"
    echo "  systemctl status ${SERVICE_NAME}    # status dekho"
    echo "  systemctl restart ${SERVICE_NAME}   # restart karo"
    echo "  journalctl -u ${SERVICE_NAME} -f    # live logs"
else
    echo "  ❌ Service start nahi hua"
    echo "  journalctl -u ${SERVICE_NAME} -n 30 chala ke error dekho"
fi
echo "======================================"
