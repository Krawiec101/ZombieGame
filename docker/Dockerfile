FROM python:3.12-slim

# Do not generate .pyc files; stream logs directly.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Basic tooling used by local workflows and CI helpers.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# The repo is mounted as a volume, but keeping a copy here is harmless.
COPY . /app
