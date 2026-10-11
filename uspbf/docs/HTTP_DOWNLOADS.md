# HTTP downloads (aria2)

Canonical implementation and operator notes live in **alfa-ai**:

- [alfa-ai/docs/HTTP_DOWNLOADS.md](../../alfa-ai/docs/HTTP_DOWNLOADS.md)
- `alfa-ai/scripts/lib/http_fetch.sh`

**This repo:** `scripts/download-rules-pdfs.sh` sources the sibling
`../alfa-ai/scripts/lib/http_fetch.sh` when present (override with
`HTTP_FETCH_SH`), so multi-connection aria2 is used when it helps; otherwise
it falls back to `curl`.
