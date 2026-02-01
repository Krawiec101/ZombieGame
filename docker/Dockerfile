FROM python:3.12-slim

# Nie tworzymy .pyc, logi lecą od razu
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Podstawowe narzędzia (git opcjonalnie, ale zwykle się przydaje)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Zależności Pythona
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Kod będzie montowany wolumenem, ale kopiowanie zostawiamy (bez szkody)
COPY . /app
