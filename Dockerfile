FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# App listens on a fixed internal port; host port is mapped in compose
EXPOSE 8080

CMD ["python", "app.py"]
