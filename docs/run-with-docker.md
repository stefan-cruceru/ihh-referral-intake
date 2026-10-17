# Run Lamplight with Docker

One command starts the app on your own computer. Nothing else on the network can reach it.

## Start

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/).
2. From the repo folder:
   - Windows: `.\start.ps1`
   - Mac or Linux: `./start.sh`
3. The app opens at http://localhost:8780. For the demo, click **Practice** at the top right, then **Practice with made-up referrals**. It needs no key.

To read packets, an admin adds the Claude API key in **Settings** (the gear at the top right). In
Docker it is kept in a file only the app can read, inside the `ihh-care-bridge_carebridge-data`
volume. Or put `ANTHROPIC_API_KEY` in `.env` (the first run makes it from `.env.example`) and run
the start script again; `.env` wins when both are set. For Claude in IHH's Azure, set
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
| API key | Settings, or `.env` | Settings: a private file in the data volume. `.env`: gitignored. Never in the image. |

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
(Mac o Linux). La app se abre en http://localhost:8780. Solo esta computadora la puede abrir. Para la
demo, haga clic en **Práctica** arriba a la derecha y luego en **Practique con referidos inventados**. Funciona sin clave. Para leer referidos, un administrador agrega la clave en Ajustes (el
engranaje arriba a la derecha). Para pararla: `.\start.ps1 -Stop` o `./start.sh stop`.
