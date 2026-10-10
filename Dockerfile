FROM node:22-bookworm-slim AS chatgpt-login-runtime
ARG CODEX_VERSION=0.162.1
RUN npm install --global @openai/codex@${CODEX_VERSION}

FROM python:3.11-slim

# Official OpenAI login runs inside FjordLens, never on the user's computer.
COPY --from=chatgpt-login-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=chatgpt-login-runtime /usr/local/lib/node_modules/@openai /opt/openai
RUN ln -s /opt/openai/codex/bin/codex.js /usr/local/bin/codex

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

ARG TUS_JS_VERSION=4.2.3

WORKDIR /app


# Installer systempakker (inkl. build deps til rawpy/LibRaw)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ffmpeg fonts-dejavu-core libimage-exiftool-perl \
    build-essential pkg-config cmake ninja-build python3-dev \
    libraw-dev libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Opdater pip/setuptools/wheel først for at få præbyggede hjul hvor muligt
RUN pip install --no-cache-dir -U pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# Bundle tus-js-client in the image (avoid runtime CDN dependency)
RUN mkdir -p /app/static/vendor \
    && curl -fsSL "https://cdn.jsdelivr.net/npm/tus-js-client@${TUS_JS_VERSION}/dist/tus.min.js" \
       -o /app/static/vendor/tus.min.js

# App listens on a fixed internal port; host port is mapped in compose
EXPOSE 8080

# Run with Gunicorn in containers for production-grade serving
CMD ["gunicorn", "--workers", "2", "--worker-class", "gthread", "--threads", "4", "--timeout", "120", "--bind", "0.0.0.0:8080", "wsgi:application"]
