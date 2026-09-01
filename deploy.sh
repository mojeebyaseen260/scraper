#!/bin/bash
# ============================================================
#  ColdLeads — VPS Auto Deploy Script
#  Usage: bash deploy.sh
# ============================================================

set -e  # Exit on any error

# ── CONFIG ──────────────────────────────────────────────────
# Secrets are NEVER hardcoded here. Provide them via environment variables, e.g.
#   GITHUB_TOKEN=ghp_xxx GITHUB_USERNAME=you GITHUB_REPO=repo bash deploy.sh
# Anything not provided is prompted for (token) or generated/defaulted safely.
GITHUB_USERNAME="${GITHUB_USERNAME:-}"
GITHUB_REPO="${GITHUB_REPO:-}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
APP_PORT="${APP_PORT:-6002}"
INSTALL_DIR="${INSTALL_DIR:-/opt/coldleads}"

# Admin account (password auto-generated if not supplied — shown once at the end)
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@coldleads.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"

# JWT secret — generated fresh if not supplied
JWT_SECRET="${JWT_SECRET:-}"

# PostgreSQL connection string (REQUIRED — the app won't boot without it).
# Use a managed Postgres (Railway/Neon/Supabase) or one installed on this VPS.
DATABASE_URL="${DATABASE_URL:-}"
# ────────────────────────────────────────────────────────────

# ── Collect / generate secrets ───────────────────────────────
if [[ -z "$GITHUB_USERNAME" ]]; then read -p "  GitHub Username: " GITHUB_USERNAME; fi
if [[ -z "$GITHUB_REPO" ]];     then read -p "  Repo name: " GITHUB_REPO; fi
if [[ -z "$GITHUB_TOKEN" ]]; then
  echo "  GitHub Personal Access Token (input hidden):"
  read -s GITHUB_TOKEN; echo ""
fi
if [[ -z "$GITHUB_USERNAME" || -z "$GITHUB_REPO" || -z "$GITHUB_TOKEN" ]]; then
  echo "❌  ERROR: GitHub username, repo and token are all required."
  exit 1
fi

# Generate a strong JWT secret if none supplied
if [[ -z "$JWT_SECRET" ]]; then
  JWT_SECRET="$(openssl rand -hex 32)"
  echo "  ✓ Generated a random JWT_SECRET"
fi

# Postgres connection string is required
if [[ -z "$DATABASE_URL" ]]; then
  echo "  Enter the PostgreSQL connection string (postgresql://user:pass@host:5432/db):"
  read -r DATABASE_URL
fi
if [[ -z "$DATABASE_URL" ]]; then
  echo "❌  ERROR: DATABASE_URL is required — the backend won't start without it."
  exit 1
fi

# Generate a strong admin password if none supplied
ADMIN_PW_GENERATED=0
if [[ -z "$ADMIN_PASSWORD" ]]; then
  ADMIN_PASSWORD="$(openssl rand -base64 12 | tr -d '/+=' | cut -c1-14)"
  ADMIN_PW_GENERATED=1
fi

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║     ColdLeads VPS Deploy — Starting...       ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── Step 1: System Update ────────────────────────────────────
echo "▶ [1/8] System update ho raha hai..."
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq curl wget git ufw

# ── Step 2: Python ───────────────────────────────────────────
echo "▶ [2/8] Python install ho raha hai..."
apt-get install -y -qq python3 python3-pip python3-venv

# ── Step 3: Node.js ──────────────────────────────────────────
echo "▶ [3/8] Node.js install ho raha hai..."
if ! command -v node &> /dev/null; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash - > /dev/null 2>&1
  apt-get install -y -qq nodejs
fi
echo "   Node: $(node -v) | npm: $(npm -v)"

# ── Step 4: Google Chrome ────────────────────────────────────
echo "▶ [4/8] Google Chrome install ho raha hai (Selenium ke liye)..."
if ! command -v google-chrome-stable &> /dev/null && ! command -v google-chrome &> /dev/null; then
  wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
  apt-get install -y -qq /tmp/chrome.deb || apt-get install -f -y -qq
  rm -f /tmp/chrome.deb
fi
CHROME_VER=$(google-chrome --version 2>/dev/null || google-chrome-stable --version 2>/dev/null || echo "installed")
echo "   Chrome: $CHROME_VER"

# ── Step 5: Clone / Update Repo ──────────────────────────────
echo "▶ [5/8] Repo clone/update ho raha hai..."
REPO_URL="https://${GITHUB_TOKEN}@github.com/${GITHUB_USERNAME}/${GITHUB_REPO}.git"

if [ -d "$INSTALL_DIR/.git" ]; then
  echo "   Repo already exists — pulling latest changes..."
  cd "$INSTALL_DIR"
  git remote set-url origin "$REPO_URL"
  git pull origin main 2>/dev/null || git pull origin master 2>/dev/null
else
  echo "   Fresh clone ho raha hai..."
  rm -rf "$INSTALL_DIR"
  git clone "$REPO_URL" "$INSTALL_DIR"
  cd "$INSTALL_DIR"
fi

# Token URL se hata do (security)
git remote set-url origin "https://github.com/${GITHUB_USERNAME}/${GITHUB_REPO}.git"
echo "   ✓ Repo ready: $INSTALL_DIR"

# ── Step 6: Backend Setup ────────────────────────────────────
echo "▶ [6/8] Backend setup ho raha hai..."
cd "$INSTALL_DIR/backend"

# Virtual environment
python3 -m venv venv
source venv/bin/activate

# Dependencies
pip install -q --upgrade pip
pip install -q -r ../requirements.txt

# .env file banao (agar pehle se nahi hai)
if [ ! -f ".env" ]; then
  cat > .env << EOF
DATABASE_URL=${DATABASE_URL}
JWT_SECRET=${JWT_SECRET}
PRODUCTION=1
ALLOWED_ORIGINS=http://$(curl -s ifconfig.me):${APP_PORT}
ADMIN_EMAIL=${ADMIN_EMAIL}
ADMIN_PASSWORD=${ADMIN_PASSWORD}
EOF
  echo "   ✓ .env file bana di"
else
  echo "   ✓ .env already exists — skip (existing settings preserve ho gaye)"
  # Don't mislead the final summary with a freshly-generated password we didn't use
  ADMIN_PW_GENERATED=0
fi

# Output folder
mkdir -p output

deactivate

# ── Step 7: Frontend Build ───────────────────────────────────
echo "▶ [7/8] Frontend build ho raha hai..."
cd "$INSTALL_DIR/frontend"
npm install --silent
npm run build
echo "   ✓ Frontend dist/ folder ready"

# ── Step 8: Systemd Service ──────────────────────────────────
echo "▶ [8/8] Systemd service setup ho raha hai..."

cat > /etc/systemd/system/coldleads.service << EOF
[Unit]
Description=ColdLeads FastAPI Backend
After=network.target

[Service]
User=root
WorkingDirectory=${INSTALL_DIR}/backend
Environment="PATH=${INSTALL_DIR}/backend/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=${INSTALL_DIR}/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port ${APP_PORT} --workers 1
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable coldleads
systemctl restart coldleads

# Firewall
ufw allow "${APP_PORT}/tcp" > /dev/null 2>&1 || true

# ── Done ─────────────────────────────────────────────────────
sleep 3
STATUS=$(systemctl is-active coldleads)
SERVER_IP=$(curl -s ifconfig.me)

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║           ✅  DEPLOY COMPLETE!               ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "  🌐  App URL   : http://${SERVER_IP}:${APP_PORT}"
echo "  📊  Status    : $STATUS"
echo "  📧  Admin     : ${ADMIN_EMAIL}"
if [ "$ADMIN_PW_GENERATED" = "1" ]; then
  echo "  🔑  Password  : ${ADMIN_PASSWORD}   (auto-generated — save it now, shown only once!)"
else
  echo "  🔑  Password  : (the one you provided)"
fi
echo ""
echo "  Logs dekhne ke liye:"
echo "    journalctl -u coldleads -f"
echo ""
echo "  Restart karne ke liye:"
echo "    systemctl restart coldleads"
echo ""
echo "  Future updates ke liye:"
echo "    bash ${INSTALL_DIR}/deploy.sh"
echo ""

if [ "$STATUS" != "active" ]; then
  echo "⚠️  Service active nahi hai! Logs check karo:"
  echo "   journalctl -u coldleads -n 50 --no-pager"
fi
