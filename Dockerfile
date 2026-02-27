FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app


# Installer curl
RUN apt-get update && apt-get install -y curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# App listens on a fixed internal port; host port is mapped in compose
EXPOSE 8080

# Run with Gunicorn in containers for production-grade serving
CMD ["gunicorn", "--workers", "2", "--worker-class", "gthread", "--threads", "4", "--timeout", "120", "--bind", "0.0.0.0:8080", "wsgi:application"]
