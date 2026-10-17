#!/usr/bin/env sh
# Start IHH Care Bridge in Docker and open it in the browser.
# Inicia IHH Care Bridge en Docker y lo abre en el navegador.
#   ./start.sh          start (or rebuild after code changes)
#   ./start.sh stop     stop the app (settings and the outcome log are kept)
set -e
cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed. Install Docker Desktop, then run this again."
  echo "Docker no esta instalado. Instale Docker Desktop y vuelva a correr esto."
  exit 1
fi
if [ "$1" = "stop" ]; then exec docker compose down; fi
if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running. Start Docker Desktop and try again."
  echo "Docker no esta corriendo. Abra Docker Desktop y vuelva a intentar."
  exit 1
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Made .env. Add ANTHROPIC_API_KEY there to read packets (the demo works without it)."
  echo "Se creo .env. Agregue ANTHROPIC_API_KEY para leer referidos (la demo funciona sin ella)."
fi
mkdir -p inbox

docker compose up --build -d

url="http://localhost:${CAREBRIDGE_PORT:-8780}/"
i=0
while [ $i -lt 30 ] && ! curl -fs -o /dev/null "$url"; do i=$((i + 1)); sleep 1; done
echo "IHH Care Bridge: $url"
(command -v open >/dev/null && open "$url") || (command -v xdg-open >/dev/null && xdg-open "$url") || true
