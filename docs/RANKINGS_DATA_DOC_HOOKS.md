# Rankings data pipeline — doc hooks for AI and maintainers

**Purpose:** WPA/WPBA (and related) data moves through **scrapers → Postgres (`postgres_manager`) → API (`rankings` routes) → UI**. Read the linked docs before adding columns, splits, or endpoints so UI, API, and DB stay aligned.

**Process pattern:** [AI_INLINE_DOC_REF_PROCESS.md](AI_INLINE_DOC_REF_PROCESS.md)

---

## Rules (summary)

1. **WPA men/women** — Dynamic tournament columns, `wpa_column_labels`, API-driven menus, zero-data column skip: see **docs/WPA_RANKINGS_DATA_FLOW.md**.
2. **WPBA PDF** — Rotating columns and which tables/pages consume data: **docs/WPBA_DATA_FLOW.md**.
3. **Schema / JSONB** — First-class columns vs `source_data`: **docs/RANKINGS_TABLE_DESIGN.md**.
4. **Consolidation / rebuilds** — Player vs ranking sources: **docs/RANKINGS_DATA_CONSOLIDATION.md**.

---

## File → documentation

| Repository path | Read these docs |
|-----------------|-----------------|
| `database/postgres_manager.py` | **docs/RANKINGS_TABLE_DESIGN.md**, **docs/WPA_RANKINGS_DATA_FLOW.md**, **docs/WPBA_DATA_FLOW.md**, **docs/RANKINGS_DATA_CONSOLIDATION.md** |
| `api/routes/rankings.py` | **docs/WPA_RANKINGS_DATA_FLOW.md**, **docs/WPBA_DATA_FLOW.md**, **docs/RANKINGS_TABLE_DESIGN.md**, **docs/HOW_DATA_IS_UPDATED.md** (refresh triggers) |
| `scrapers/wpa_scraper.py` | **docs/WPA_RANKINGS_DATA_FLOW.md** |
| `scrapers/wpba_scraper.py` | **docs/WPBA_DATA_FLOW.md**, **docs/RANKINGS_TABLE_DESIGN.md** |
| `frontend/src/pages/Rankings.tsx` | **docs/WPA_RANKINGS_DATA_FLOW.md**, **docs/WPBA_DATA_FLOW.md** |
| `frontend/src/api/rankings.ts` | **docs/WPA_RANKINGS_DATA_FLOW.md** (tournament-systems endpoints), **docs/RANKINGS_TABLE_DESIGN.md** |
| `api/services/background_scheduler.py` | **docs/HOW_DATA_IS_UPDATED.md**, **docs/ROADMAP.md** (scheduler vs doc claims) |
