#!/bin/bash
# ── ColdLeads VPS Setup (FileZilla / manual-upload version) ──────────────
# Use this when you uploaded the project with FileZilla instead of git.
# Assumes the project is already at /opt/coldleads (so /opt/coldleads/backend
# and /opt/coldleads/frontend exist).
#
# Run as root on Ubuntu 22.04:
#     bash /opt/coldleads/deploy/setup_vps_filezilla.sh

set -e

PORT=6002
APP_DIR="/opt/coldleads"
SERVICE_NAME="coldleads"

echo "======================================"
echo "  ColdLeads VPS Setup (FileZilla) — Port $PORT"
echo "======================================"

# ── 0. Sanity: files uploaded? ─────────────────────────────
if [ ! -f "$APP_DIR/backend/main.py" ]; then
    echo "❌ $APP_DIR/backend/main.py not found."
    echo "   Upload the project to $APP_DIR with FileZilla first, then re-run."
    exit 1
fi

# ── 1. System packages (minimal — Chrome pulls its own libs below) ──
# Kept minimal so it works on both Ubuntu 22.04 and 24.04 (24.04 renamed some
# libs, e.g. libasound2 → libasound2t64). The Chrome .deb resolves its own
# runtime dependencies via apt, so we don't list them here.
echo "[1/6] Installing system packages..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv \
    curl wget unzip screen ca-certificates gnupg

# ── 2. Google Chrome (auto-installs all its runtime deps) ──
echo "[2/6] Installing Google Chrome..."
if ! command -v google-chrome &> /dev/null; then
    wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    apt-get install -y ./google-chrome-stable_current_amd64.deb
    rm -f google-chrome-stable_current_amd64.deb
fi
echo "  Chrome: $(google-chrome --version)"

# ── 3. Node.js 20 (to build the frontend) ──────────────────
echo "[3/6] Installing Node.js 20..."
if ! command -v node &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y -qq nodejs
fi
echo "  Node: $(node --version) | npm: $(npm --version)"

# ── 4. Python venv + dependencies ──────────────────────────
echo "[4/6] Installing Python dependencies..."
cd "$APP_DIR/backend"
python3 -m venv venv
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r ../requirements.txt

# ── 5. Tuned .env for KVM 4 (4 vCPU / 16 GB) ───────────────
echo "[5/6] Writing tuned .env..."
SERVER_IP=$(curl -s ifconfig.me || echo "YOUR_SERVER_IP")
if [ ! -f "$APP_DIR/backend/.env" ]; then
    read -p "  Admin email [admin@coldleads.com]: " ADMIN_EMAIL
    ADMIN_EMAIL=${ADMIN_EMAIL:-admin@coldleads.com}
    read -s -p "  Admin password (strong): " ADMIN_PASSWORD; echo ""
    JWT_SECRET=$(openssl rand -hex 32)

    cat > "$APP_DIR/backend/.env" <<ENVEOF
PRODUCTION=1
# Speed: parallel headless-Chrome scrapers (16 GB RAM holds 6; drop to 4 if CPU pegs)
NUM_DRIVERS=7
# More data per query
MAX_PLACES=500
SCROLL_ROUNDS=150
SCROLL_PAUSE=0.6
SCROLL_STALL_LIMIT=18
# More + faster emails
EMAIL_WORKERS=72
MAX_EMAIL_PAGES=10
EMAIL_DEEP=1
EMAIL_TIMEOUT=10
EMAIL_CRAWL_BUDGET=30
SQLITE_PATH=coldleads.db
JWT_SECRET=${JWT_SECRET}
ALLOWED_ORIGINS=http://${SERVER_IP}:${PORT}
ADMIN_EMAIL=${ADMIN_EMAIL}
ADMIN_PASSWORD=${ADMIN_PASSWORD}
ENVEOF
    echo "  .env created (tuned for KVM 4)."
else
    echo "  .env already exists — leaving it as-is."
fi

# ── 6. Build frontend + systemd service ────────────────────
echo "[6/6] Building frontend and starting service..."
cd "$APP_DIR/frontend"
npm install -q
npm run build

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

echo ""
echo "======================================"
if [ "$(systemctl is-active ${SERVICE_NAME})" = "active" ]; then
    echo "  ✅ ColdLeads is RUNNING!"
    echo "  🌐 Open: http://${SERVER_IP}:${PORT}"
    echo ""
    echo "  Logs:    journalctl -u ${SERVICE_NAME} -f"
    echo "  Restart: systemctl restart ${SERVICE_NAME}"
else
    echo "  ❌ Service failed to start"
    echo "  Run: journalctl -u ${SERVICE_NAME} -n 40"
fi
echo "======================================"
