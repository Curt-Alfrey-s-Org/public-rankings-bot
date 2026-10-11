# Quick Script Reference

**Start everything from scratch:**
```bash
./scripts/full_deploy.sh
```

**Code changed? Quick restart:**
```bash
./scripts/stop.sh --app-only && ./scripts/start.sh --app-only
```

**Stop everything:**
```bash
./scripts/stop.sh
```

**Dependencies only (for maintenance):**
```bash
# Stop just postgres + redis (app stopped too)
./scripts/stop.sh --app-only
./scripts/stop.sh --deps-only

# ... maintenance work ...

./scripts/start.sh --deps-only && ./scripts/start.sh --app-only
```

**Watch logs:**
```bash
docker compose logs -f rankings-bot-api
```

---

**Dependencies** (Postgres, Redis): ~30 seconds startup, rarely restart
**App** (API, Celery, Frontend): ~1-2 minutes rebuild, restart as needed

Typical workflow: Edit code → `stop.sh --app-only` + `start.sh --app-only` (2 min) vs. full_deploy (10 min)
