# USPBF — rules documents

Official PDFs used as the starting rule set (WPA + WPBA). Re-run the download script periodically to pick up published updates.

## Layout

| Directory | Content |
|-----------|---------|
| `wpa/` | World Pool Association rule PDFs |
| `wpba/` | WPBA 9-ball rules PDF and point-system image |
| `reference/` | Notes and placeholders (e.g. Texas Express) |

### WPA files (`wpa/`)

| File | Description |
|------|-------------|
| `2026.01.02-WPA-Rules.pdf` | Rules of play |
| `2025.09.15-WPA-Regs-NP.pdf` | Rule regulations |
| `2022-WPA-Sports-Regulations-v2-1.pdf` | Sports regulations |
| `2025.02.12-WPA-Sanctioning-Regulations.pdf` | Sanctioning regulations |
| `RECOMMENDED-EQUIPMENT-SPECIFICATIONS.pdf` | Equipment |
| `2025.07.19-Pyramid-Rules.pdf` | Pyramid |
| `250816-Rules-of-Heyball.pdf` | Heyball |
| `APD-Guidelines-FINAL-WPA-Update-Notes.pdf` | Artistic pool guidelines |
| `International_8_Ball_Rules_Feb2021.pdf` | International 8-ball |

### WPBA files (`wpba/`)

| File | Description |
|------|-------------|
| `WPBA-9-Ball-Rules-Rev-51625.pdf` | 9-ball rules |
| `WPBA-Point-System-rev-12326.png` | Point system graphic |

## Download

From the USPBF repo root:

```bash
./scripts/download-rules-pdfs.sh
```

Requires `curl`. Sources are documented in the script; if a URL returns 404, update the script with the current link from [wpapool.com/rules](https://wpapool.com/rules/) or [wpba.com/rules](https://wpba.com/rules/).

## WordPress

Upload PDFs via **Media → Add New**, then link from your **Rules** pages. Prefer **USPBF Official** vs **Reference** labels per ruleset as the federation adopts variants.
