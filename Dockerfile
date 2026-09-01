# ColdLeads backend — FastAPI + Selenium (headless Chromium) for Railway.
FROM python:3.11-slim

# Chromium + matching driver + the libs headless Chrome needs.
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
        ca-certificates \
        fonts-liberation \
        libnss3 libxss1 libasound2 libatk-bridge2.0-0 libatk1.0-0 \
        libcups2 libdbus-1-3 libgbm1 libgtk-3-0 libxcomposite1 \
        libxdamage1 libxfixes3 libxrandr2 libxkbcommon0 libpango-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Selenium finds Chrome/driver via these; PRODUCTION enables the lean tuning.
ENV CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver \
    PYTHONUNBUFFERED=1 \
    PRODUCTION=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
WORKDIR /app/backend
RUN mkdir -p output

# Railway injects $PORT; bind to it.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
