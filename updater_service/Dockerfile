FROM python:3.11-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apk add --no-cache \
    docker-cli \
    docker-cli-compose \
    git

WORKDIR /service
COPY updater_service/app.py /service/app.py
COPY updater_service/memory_governor.py /service/memory_governor.py

EXPOSE 8090
CMD ["python", "/service/app.py"]
