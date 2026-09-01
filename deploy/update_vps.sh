#!/bin/bash
# ── ColdLeads Update Script ───────────────────────────────
# Run on VPS jab bhi GitHub pe new code push karo
# Usage: bash /opt/coldleads/deploy/update_vps.sh

set -e
APP_DIR="/opt/coldleads"
SERVICE_NAME="coldleads"

echo "Updating ColdLeads..."

read -p "GitHub Username: " GH_USER
read -p "Personal Access Token: " GH_TOKEN
read -p "Repo name [scraper-stage-2]: " GH_REPO
GH_REPO=${GH_REPO:-"scraper-stage-2"}

cd "$APP_DIR"
git pull "https://${GH_USER}:${GH_TOKEN}@github.com/${GH_USER}/${GH_REPO}.git" main

# Update Python packages if requirements changed
cd "$APP_DIR/backend"
source venv/bin/activate
pip install -q -r ../requirements.txt

# Rebuild frontend
cd "$APP_DIR/frontend"
npm install -q
npm run build

# Restart service
systemctl restart "$SERVICE_NAME"
sleep 2

echo "✅ Updated! Status: $(systemctl is-active $SERVICE_NAME)"
echo "🌐 http://$(curl -s ifconfig.me):6002"
