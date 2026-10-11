# HTTP downloads (aria2)

This repo does not ship the fetch helper. For **large single-file HTTPS**
downloads (GGUF, installers, etc.), use the shared library and policy in
**alfa-ai**:

- [alfa-ai/docs/HTTP_DOWNLOADS.md](../../alfa-ai/docs/HTTP_DOWNLOADS.md)
- `alfa-ai/scripts/lib/http_fetch.sh` — source it, then call `http_fetch_to URL DEST`

Set `ARIA2_RPC_URL` (and related env vars from that doc) when you want hub
aria2 JSON-RPC instead of a single `curl` stream.
