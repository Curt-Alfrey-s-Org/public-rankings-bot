# Legacy: Missing Data Backfill Summary

This document was archived because it reflects an older enrichment model that primarily wrote Fargo-related metadata into `rankings` rows.

Current authoritative docs:

- `docs/RANKINGS_DATA_CONSOLIDATION.md`
- `docs/FARGO_QUICK_REFERENCE.md`
- `docs/HOW_DATA_IS_UPDATED.md`

Reason for archival:

- The current model treats `players` as the source of truth for live rating/identity fields and overlays those values into leaderboard views at read time.
