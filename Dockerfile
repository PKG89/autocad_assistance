FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (kept minimal; manylinux wheels cover heavy libs)
RUN apt-get update \
    && apt-get -y upgrade \
    && apt-get install -y --no-install-recommends \
       ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY autocad_assistance/requirements.txt /app/requirements.txt
# Upgrade pip to address known CVEs, then install deps
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r /app/requirements.txt

COPY autocad_assistance /app/autocad_assistance

# Default DB path inside container; override via env if needed
RUN mkdir -p /data
ENV DATA_DIR=/data
ENV DB_PATH=/data/usage_stats.db

CMD ["python", "autocad_assistance/main.py"]
