# ColdLeads — VPS Deploy via FileZilla (KVM 4)

Tuned for a **KVM 4 VPS = 4 vCPU / 16 GB RAM**, Ubuntu 22.04.
Already configured for: more cities (top-40/state), more data, more+faster emails,
6 parallel scrapers, auto-resume on crash/network drop.

---

## A. VPS lein
1. KVM 4 VPS banao — **OS: Ubuntu 22.04 (64-bit)**.
2. Panel se note karo: **Server IP**, **root password**.

## B. FileZilla se files upload
1. FileZilla kholo → **File → Site Manager → New Site**.
   - Protocol: **SFTP - SSH File Transfer Protocol**
   - Host: **<SERVER_IP>**   Port: **22**
   - Logon Type: **Normal**   User: **root**   Password: **<root password>**
   - **Connect**.
2. Right panel (server) me jao, `/opt/` me ek folder banao: **`coldleads`** → path `/opt/coldleads`.
3. Left panel (local) me apna project folder kholo:
   `C:\Users\PC\Desktop\scrape final\new scraper\scrape`
4. Andar ki **saari cheezein** `/opt/coldleads` me drag karo — LEKIN yeh **EXCLUDE** karo
   (warna upload ghanton lagega / galat data jayega):
   - `frontend/node_modules`   ← bahut bara, skip
   - `backend/venv`            ← skip
   - `backend/__pycache__`, `backend/.pytest_cache`
   - `backend/.env`            ← skip (script naya tuned banayega)
   - `backend/coldleads.db`, `*.db-wal`, `*.db-shm`  ← skip (fresh DB)
   - `.git`
   > Tip: bas `backend/` (in exclusions ke bina), `frontend/` (src/index.html/package.json,
   > bina node_modules), `deploy/`, `requirements.txt`, `Dockerfile`, `README.md` upload karo.

   (Optional: agar apna purana data chahiye to `backend/coldleads.db` bhi upload karo —
   phir naya admin seed nahi hoga, purane accounts chalenge.)

## C. SSH se setup chalao
1. Windows pe terminal kholo (PowerShell ya PuTTY) aur connect:
   ```
   ssh root@<SERVER_IP>
   ```
   (PuTTY me Host=<SERVER_IP>, Port=22, root se login.)
2. Setup script chalao (ek hi command — sab install + build + start karega):
   ```
   bash /opt/coldleads/deploy/setup_vps_filezilla.sh
   ```
3. Yeh poochega: **Admin email** aur **Admin password** — daal do.
   (JWT secret auto-generate hoga, .env tuned values ke saath ban jayega.)
4. ~3-5 min me yeh install karega: Chrome, Node, Python deps, frontend build,
   systemd service, aur app START kar dega.

## D. Firewall — port 6002 kholo
1. VPS pe:
   ```
   ufw allow 6002/tcp
   ufw allow OpenSSH
   ufw --force enable
   ```
2. **Hostinger/provider panel** me bhi firewall ho to wahan bhi **port 6002 (TCP)** allow karo.

## E. Open karo
Browser me: **http://<SERVER_IP>:6002**
Login: jo admin email/password setup me diya tha.

---

## Rozmarra commands (VPS pe)
```
journalctl -u coldleads -f       # live logs
systemctl restart coldleads      # restart
systemctl status coldleads       # status
```

## Baad me code update karna ho (FileZilla)
1. Badli hui files FileZilla se `/opt/coldleads/...` pe overwrite karo.
2. Agar frontend badla: `cd /opt/coldleads/frontend && npm run build`
3. `systemctl restart coldleads`

## Speed/Data tuning (file: `backend/.env`)
- CPU 100% reh raha hai → `NUM_DRIVERS=6` ko **4** karo.
- Aur zyada data chahiye → cities badhane ke liye local pe `backend/fetch_cities.py`
  me `TOP_N` badhao, regenerate karke `locations.py` upload karo.
- Aur zyada email → `MAX_EMAIL_PAGES=8`, `EMAIL_WORKERS=48`.
Har change ke baad: `systemctl restart coldleads`.
