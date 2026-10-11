# Architecture diagrams (Mermaid)

Use these to **see what talks to what** and to **diagnose** when the site or bot isn’t updating.

## View in browser (no install)

Open **`architecture.html`** in a browser (double‑click or `file:///path/to/docs/diagrams/architecture.html`).  
It loads Mermaid from a CDN and renders:

- **Current flow (Feb 2026):** Tunnel → probilliards-nginx → rankings-bot-api (Docker); data/scrape flow; UI flow; “Why you don’t see updates”
- **Setup B:** Reverse proxy → frontend container + API container
- **Diagnose flow:** Where to check when something’s wrong, plus “website change” actions

No server or `npm install` needed.

## Export PNG/SVG (optional)

If you want static images (e.g. for docs or n8n):

```bash
cd docs/diagrams
npx @mermaid-js/mermaid-cli@latest -i setup-b-docker.mmd -o setup-b-docker.png
npx @mermaid-js/mermaid-cli@latest -i diagnose-flow.mmd -o diagnose-flow.png
```

Or use the npm script (after `npm install` in this folder):

```bash
cd docs/diagrams
npm install
npm run build
```

That writes `*.png` (and optionally `*.svg`) into this folder.  
`mermaid-cli` uses Puppeteer; first run may download Chromium.

## Files

| File | Purpose |
|------|--------|
| **architecture.html** | Open in browser to view all diagrams (including current flow Feb 2026) and the diagnose checklist |
| **current-flow-feb2026.mmd** | Mermaid source: Tunnel → Nginx → API (Docker) — main request flow |
| **setup-b-docker.mmd** | Mermaid source: Reverse proxy → frontend + API containers |
| **diagnose-flow.mmd** | Mermaid source: diagnose flow and “what to run” for website changes |

Full narrative: **docs/REQUEST_FLOW_AND_ARCHITECTURE.md**.
