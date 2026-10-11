# Live UI Freshness — Implementation Plan

**Goal.** Every successful write (scrape, score, upload, settings save, calibration apply, backup, etc.) is reflected in connected browsers **within ~1 second**, without polling, without page reload, and without manual cache busts in each route.

**Scope.** Closes the gap between the existing **scheduler → SSE** path (already live) and the **operator/user write** path (currently stale up to ~2 min because of HTTP cache + missing client invalidation).

---

## 1. Industry standards this plan follows

- **MDN — Server-Sent Events / `EventSource`.** One-way server-push over HTTP, auto-reconnect, works through Cloudflare Tunnel + nginx the same way our live log already does. Reference: <https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events>.
- **FastAPI — `StreamingResponse`.** Canonical pattern for SSE in FastAPI. Reference: <https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse>.
- **TanStack Query — Query Invalidation.** `invalidateQueries({ queryKey })` matches by **array prefix**; nested keys cascade. Reference: <https://tanstack.com/query/latest/docs/framework/react/guides/query-invalidation>.
- **RFC 9111 — HTTP Caching, §4.4 Invalidation.** State-changing methods invalidate cached representations of the affected resource. Our internal `cache_store` is the same model; busts must be tied to writes. Reference: <https://www.rfc-editor.org/rfc/rfc9111#name-invalidating-stored-responses>.
- **Twelve-Factor — Backing services / Concurrency / Stateless processes.** No per-process broadcaster; SSE stream is in-memory but cache invalidation must work for any worker. Reference: <https://12factor.net/>.

We do **not** introduce WebSockets — SSE already exists in this repo (`api/services/live_updates.py`, `api/routes/live_updates.py`) and matches the one-way push need. Adding WS is out of scope.

---

## 2. Current state

| Layer | Status | Evidence |
|---|---|---|
| SSE event bus | ✅ in production | `api/services/live_updates.py` (`publish_scraper_event`, `_client_queues`) |
| SSE HTTP stream | ✅ in production | `GET /api/live/updates`, `GET /api/live/status` |
| Scheduler jobs publish events | ✅ | `api/services/background_scheduler.py` (24 publish calls) |
| **Operator/admin writes publish events** | ⚠ Partial — tournament rack submit + match score now publish `scores`/`rankings` topics; photo upload, settings save, etc. still pending |
| **Server HTTP cache busted on writes** | ⚠ Partial — only `tournament_history.py` (`refresh-past`, after this plan) and `rankings.py` (4 sites). All other write endpoints leak stale data for `CACHE_TTL_SECONDS + CACHE_STALE_TTL_SECONDS` (default ~120s). |
| React Query key shape | ⚠ Inconsistent — some pages use `['tournament-history-details', id]` etc., which **do not** prefix-match `['tournament-history']`, so SSE-triggered invalidations miss them. |

---

## 3. Architecture (single best path)

Every successful write goes through **one helper** that does both halves of the freshness contract:

```
write endpoint
   └── DB commit + (optional) refresh_materialized_views()
         └── notify_data_changed(topic, **meta)
               ├── invalidate_cache(topic)            # RFC 9111 §4.4 invalidation
               └── publish_scraper_event(topic, ...)  # MDN SSE push to all clients
```

Browsers receive the SSE event, `useLiveUpdates` calls `queryClient.invalidateQueries({ queryKey: [topic] })`, TanStack Query refetches, fresh JSON comes from the API (cache was already busted), UI updates.

**Topic = the React Query key prefix.** One name, one cache prefix, one SSE event type. No translation tables.

---

## 4. Backend contract

### 4.1 New helper — `api/services/live_updates.py`

Add a single function (no removal, no rename):

```python
def notify_data_changed(
    topic: str,
    *,
    rows_updated: int = 0,
    duration_s: float = 0.0,
    message: str = "",
) -> None:
    """Bust server HTTP cache for `topic` and broadcast SSE to all clients.

    Call AFTER a successful DB commit (and after refresh_materialized_views()
    if the topic depends on a materialized view). Safe in sync routes.
    """
    from api.services.cache_store import invalidate_cache, make_cache_key
    try:
        invalidate_cache(make_cache_key(topic))
    except Exception as e:
        logger.warning("notify_data_changed: invalidate_cache(%s) failed: %s", topic, e)
    publish_scraper_event(
        scraper_type=topic,
        status="success",
        rows_updated=rows_updated,
        duration_s=duration_s,
        message=message,
    )
```

**Why one helper.** Removes the chance to forget either half. RFC 9111 §4.4 requires invalidation tied to the write; SSE without a cache bust ships an event that returns stale JSON.

### 4.2 Topic registry (single source of truth)

`api/services/live_topics.py` (shipped):

```python
class Topic(str, Enum):
    TOURNAMENT_HISTORY = "tournament-history"
    UPCOMING_EVENTS    = "upcoming-events"
    RANKINGS           = "rankings"
    LEADERBOARD        = "leaderboard"
    PLAYERS            = "players"
    SETTINGS           = "settings"
    BACKUPS            = "backups"
    CALIBRATION        = "calibration"
    FARGO              = "fargo"
    SCORES             = "scores"
    UPLOADS            = "uploads"
```

The frontend currently uses string literals matching these values inside
`frontend/src/hooks/useLiveUpdates.ts`. A typed mirror at `frontend/src/lib/topics.ts`
is a non-blocking follow-up to eliminate the chance of future string drift.

### 4.3 Endpoint audit (concrete rollout)

For each row: add **one line** at the success path of the route, after the DB commit / MV refresh.

| File | Route | Topic to publish | Status |
|---|---|---|---|
| `api/routes/tournament_history.py` | `POST /refresh-past` | `tournament-history` | ✅ done (cache only — switch to `notify_data_changed`) |
| `api/routes/tournament_history.py` | `POST /refresh-upcoming` | `upcoming-events` | ❌ to do |
| `api/routes/tournament_history.py` | `POST /fill-from-cp-archives` | `tournament-history` | ❌ |
| `api/routes/tournament_history.py` | `POST /fill-from-rankings` | `tournament-history` | ❌ |
| `api/routes/rankings.py` | `POST /refresh-wpba` (and 3 sibling refresh routes) | `rankings` + `tournament-history` | ⚠ has `invalidate_cache` only — add SSE |
| `api/routes/admin.py` | `POST /rebuild-all-images` | `uploads` | ❌ |
| `api/routes/admin.py` | photo / image uploads | `uploads` + relevant entity topic | ❌ |
| `api/routes/self_calibration.py` | `POST /run-calibration-cycle`, `/apply-recommendations/*` | `calibration` + `rankings` | ❌ |
| `api/routes/backups.py` | `POST /create` | `backups` | ❌ |
| `api/routes/scores.py` (or equivalent) | score entry / edit / delete | `scores` + `tournament-history` | ❌ |
| `api/routes/settings*.py` | settings save / role change / password | `settings` | ❌ |
| `api/routes/players*.py` | player CRUD, fargo sync | `players` + (`fargo` or `rankings`) | ❌ |

**Definition of done per row:** route returns success → `notify_data_changed("topic", ...)` was called exactly once → manual `curl` of the corresponding GET returns updated JSON on the **next** request → connected browser receives SSE within 1s.

---

## 5. Frontend contract

### 5.1 Query key convention (recommended for new code; legacy tolerated)

The hook tolerates **both** of these key shapes — no rename of existing code is required:

```ts
// Recommended new shape (nested arrays):
useQuery({ queryKey: ['tournament-history', year, association], ... })
useQuery({ queryKey: ['tournament-history', 'details', id], ... })
useQuery({ queryKey: ['tournament-history', 'coverage'], ... })

// Legacy hyphenated shape (still works — predicate matches the prefix):
useQuery({ queryKey: ['tournament-history-details', id], ... })
useQuery({ queryKey: ['tournament-history-performance', id], ... })
```

The shipped `useLiveUpdates` predicate matches a query iff its first key element
either equals the topic OR starts with `${topic}-`. This covers both shapes from a
single SSE event, so no migration is required at PR-2..5 time. Renaming legacy
hyphenated keys to nested arrays is a future cleanup, not a prerequisite.

### 5.2 `useLiveUpdates` (no-arg, app-global hook)

The shipped hook is parameterless and mounts once at the app root. It reads the
SSE `scraper_type` from `/api/live/updates` and routes invalidations to the
correct query-key family using the predicate above. No per-page wiring is
required for any topic listed in §4.2.

```ts
// In App.tsx (already in place):
useLiveUpdates()
```

### 5.3 Per-page wiring

Not needed — the hook is mounted once globally and dispatches to the right
queries via the predicate. New pages get live updates "for free" as long as
their first query-key element matches a `Topic` value (or starts with `${topic}-`).

### 5.4 Mutation `onSuccess` policy

For the **submitter's own browser**, `onSuccess` of every mutation also invalidates the same topic prefix locally — covers the (rare) case where the SSE event arrives slower than the mutation response:

```ts
onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tournament-history'] })
```

This is belt-and-suspenders, not a workaround: TanStack Query docs recommend invalidating from the mutation that caused the change.

---

## 6. Multi-worker note

`_client_queues` in `live_updates.py` is **per-process**. With multiple uvicorn workers, an SSE-connected client only sees events published by the same worker that handled `GET /api/live/updates`. Today this works because the API runs as a single uvicorn worker behind nginx. If we ever scale workers > 1, the broadcast bus must move to Redis Pub/Sub (`redis-py` `pubsub`, FastAPI documented pattern). Track as a separate change; do not block this plan.

---

## 7. Acceptance criteria

A change is "done" only when **all four** are true for the affected topic:

1. `curl` of the GET endpoint after the write returns updated JSON on the **next** request (no 60–120s wait). RFC 9111 §4.4.
2. `useLiveUpdates`-subscribed page refetches without manual reload (TanStack Query `invalidateQueries`).
3. `LiveUpdatesBanner` shows the event (existing infra, zero new code).
4. Logs show: `notify_data_changed(topic=...) invalidated cache + broadcast to N clients`.

Smoke procedure (run in this order, one terminal each):

```bash
curl -N http://127.0.0.1:8003/api/live/updates                      # client A: stream
curl -s http://127.0.0.1:8003/api/tournament-history/tournaments    # baseline
# trigger any write that calls notify_data_changed(...)
curl -s http://127.0.0.1:8003/api/tournament-history/tournaments    # must show new data
```

---

## 8. Rollout order (ship in small PRs)

1. **PR-1 (infra):** add `notify_data_changed` + `Topic` enum + frontend `topics` prop. No behavior change yet. (~50 LOC.)
2. **PR-2 (tournament-history):** convert the 4 routes in `tournament_history.py`; rename frontend `tournament-history-*` keys to nested arrays.
3. **PR-3 (rankings + calibration):** convert `rankings.py` (4 sites already have `invalidate_cache` — wrap in `notify_data_changed`); convert `self_calibration.py`.
4. **PR-4 (admin + backups):** `rebuild-all-images`, uploads, `backups.py`.
5. **PR-5 (writes from end users):** scores, settings, players. Highest user-visible impact, ship last because of test surface.
6. **PR-6 (docs):** mark `LIVE_UPDATES_DOCUMENTATION.md` as covering scheduler events; this doc covers writes; keep both cross-linked.

Each PR ships independently; each is reversible by removing the helper call (cache TTL takes over within 120s, SSE simply goes silent for that topic).

---

## 9. Out of scope (explicit, to prevent scope creep)

- **WebSockets.** Not needed; SSE covers one-way push per MDN.
- **Multi-worker Redis Pub/Sub bus.** Only required if uvicorn workers > 1.
- **Optimistic UI.** Separate concern; TanStack Query supports it but it is not required for "live freshness."
- **Push notifications / mobile.** Out of scope.

---

## 10. Standards references

- MDN, *Using server-sent events*: <https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events>
- WHATWG HTML Living Standard, *Server-sent events*: <https://html.spec.whatwg.org/multipage/server-sent-events.html>
- FastAPI, *Custom Response — StreamingResponse*: <https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse>
- TanStack Query, *Query Invalidation*: <https://tanstack.com/query/latest/docs/framework/react/guides/query-invalidation>
- TanStack Query, *Mutations — Invalidating queries from a mutation*: <https://tanstack.com/query/latest/docs/framework/react/guides/mutations#invalidating-queries-from-a-mutation>
- IETF RFC 9111, *HTTP Caching*, §4.4 Invalidation: <https://www.rfc-editor.org/rfc/rfc9111#name-invalidating-stored-responses>
- Twelve-Factor App: <https://12factor.net/>
- Project: `.github/CODING_STANDARDS.md`, `docs/LIVE_UPDATES_DOCUMENTATION.md`, `docs/BUTTON_REFRESH_ARCHITECTURE.md`
