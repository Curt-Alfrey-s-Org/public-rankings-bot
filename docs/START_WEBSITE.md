# Start the rankings-bot website (Docker + Nginx)

Use this when you want the site live (e.g. **https://www.probilliardssoftware.com**).

---

## Standard: Docker

Production runs under **Docker**. Start the full stack:

```bash
cd ~/rankings-bot
./scripts/full_deploy.sh --force-docker
```

Or, if the stack is already built and you only need to bring it up:

```bash
cd ~/rankings-bot
docker compose -f production/docker-compose.prod.yml up -d
# (Or use the main compose + nginx as documented in PRODUCTION_DEPLOYMENT.md)
```

---

## If you're on another machine

1. Sync code: `./scripts/deploy.sh ansible@<server>`
2. SSH to the server and run the Docker commands above.

---

## Check

- **Health:** https://www.probilliardssoftware.com/api/health → `{"status":"healthy",...}`
- **Site:** https://www.probilliardssoftware.com/ → Rankings Bot app

---

## References

- **docs/PRODUCTION_DEPLOYMENT.md** — Nginx container + API container (locked)
- **docs/DEPLOY_WEBSITE.md** — full deploy steps
