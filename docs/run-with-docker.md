# Run Care Bridge with Docker

One command starts the app on your own computer. Nothing else on the network can reach it.

## Start

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/).
2. From the repo folder:
   - Windows: `.\start.ps1`
   - Mac or Linux: `./start.sh`
3. The app opens at http://localhost:8780. Click **Try a busy Monday** for the demo. It needs no key.

The first run makes a `.env` file from `.env.example`. Put `ANTHROPIC_API_KEY` in `.env` to read
packets, then run the start script again. In Docker the key comes from `.env`, not from Settings
(there is no Windows Credential Manager inside the container). For Claude in IHH's Azure, set
`CAREBRIDGE_PROVIDER=foundry`, `ANTHROPIC_FOUNDRY_RESOURCE` and `ANTHROPIC_FOUNDRY_API_KEY` there.

## Stop

`.\start.ps1 -Stop` or `./start.sh stop`. Settings and the outcome log are kept for next time.

## What goes where

| What | Where | Notes |
| --- | --- | --- |
| The app | `http://localhost:8780` | Published on 127.0.0.1 only. Change with `CAREBRIDGE_PORT`. |
| Settings and outcome log | Docker volume `ihh-care-bridge_carebridge-data` | No packet pages or chart text (`app/carebridge/store.py`). |
| De-identified packets | `challenges/1-referral-intake/packets/` | Mounted read-only. Never copied into the image. |
| Watched inbox | `inbox/` | A PDF saved here becomes a card. Gitignored. |
| API key | `.env` | Gitignored. Never in the image. |

Port 8780 lets the container run next to a native `python -m carebridge serve 8765`.

To erase the outcome log and settings: `docker compose down -v`.

## By hand

```bash
cp .env.example .env          # once
docker compose up --build -d  # start or rebuild
docker compose logs -f        # watch the app
docker compose down           # stop
```

---

## En español

Instale Docker Desktop. En la carpeta del repo, corra `.\start.ps1` (Windows) o `./start.sh`
(Mac o Linux). La app se abre en http://localhost:8780. Solo esta computadora la puede abrir. La
demo funciona sin clave. Para leer referidos, ponga `ANTHROPIC_API_KEY` en el archivo `.env` y
corra el script otra vez. Para pararla: `.\start.ps1 -Stop` o `./start.sh stop`.
