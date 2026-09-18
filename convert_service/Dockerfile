FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libimage-exiftool-perl \
    build-essential pkg-config libraw-dev libjpeg-dev zlib1g-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -U pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8010
HEALTHCHECK --interval=10s --timeout=5s --retries=10 --start-period=20s \
    CMD curl -fsS http://127.0.0.1:8010/health || exit 1

CMD ["gunicorn", "--workers", "1", "--worker-class", "gthread", "--threads", "4", "--timeout", "21600", "--bind", "0.0.0.0:8010", "app:app"]
