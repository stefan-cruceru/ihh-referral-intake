# CareBridge web app in one container. Build from the repo root (see compose.yaml):
# the image mirrors the repo layout so app/carebridge/paths.py finds the criteria files.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Settings and the outcome log (SQLite) live in the /data volume, never in the image.
    LOCALAPPDATA=/data \
    CAREBRIDGE_HOST=0.0.0.0 \
    CAREBRIDGE_PACKETS=/packets \
    CAREBRIDGE_INBOX=/inbox

WORKDIR /srv/ihh
COPY app/requirements.txt app/requirements.txt
RUN pip install --no-cache-dir -r app/requirements.txt

# Only the public data the app reads. Packets are never copied in: they are mounted read-only.
COPY challenges/1-referral-intake/criteria/admission-criteria.json challenges/1-referral-intake/criteria/
COPY challenges/2-finding-the-right-resource/data/oc-resources.seed.json challenges/2-finding-the-right-resource/data/
COPY challenges/2-finding-the-right-resource/scenarios/client-scenarios.json challenges/2-finding-the-right-resource/scenarios/
COPY app/carebridge app/carebridge
COPY app/demo app/demo
COPY app/tests app/tests

RUN useradd --create-home --uid 1000 carebridge \
    && mkdir -p /data /packets /inbox \
    && chown carebridge /data /inbox
USER carebridge

WORKDIR /srv/ihh/app
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8765/', timeout=4)"

CMD ["python", "-m", "carebridge", "serve", "8765", "--no-browser"]
