# USPBF WordPress — recommended pages (post-deploy)

For colors and CSS aligned with Pro Billiards + USPBF, see [WORDPRESS_THEME.md](WORDPRESS_THEME.md).

After completing the WordPress installation at `https://www.example.com` or `https://example.com`, create or structure content as follows.

## Core pages

| Page slug (suggested) | Purpose |
|----------------------|---------|
| **Home** | Mission hero, link to **app.example.com** for rankings/tournaments, sponsor strip, featured news |
| **About** | Non-profit mission, board, history, bylaws link |
| **Rules** | Tabbed or child pages by game (9-ball, 8-ball, 10-ball, one-pocket, 14.1, banks, scotch doubles, artistic, heyball, pyramid). Link to PDFs in **Media** from `docs/rules/` |
| **Rankings** | Call-to-action + link/embed to **https://app.example.com** (rankings, ALFA, tournaments) |
| **Tournaments** | Calendar narrative, registration → **app.example.com**, director info |
| **Players** | Registration, amateur vs pro, Fargo/ALFA overview, link to app |
| **Membership** | Dues, benefits, contact (details TBD by board) |
| **Sponsors** | Tiers, logos, partnership inquiry form |
| **News** | Use **Posts** for announcements and recaps |
| **Contact** | Form or email for board, media, partnerships |

## Rules content notes

- **WPA** PDFs: `docs/rules/wpa/` (from `download-rules-pdfs.sh`)
- **WPBA** PDF + points image: `docs/rules/wpba/`
- **Texas Express**: add when an official PDF/source is chosen; see `docs/rules/reference/README.md`

## Theme

- Block theme (e.g. Spectra One or Twenty Twenty-Five) with USPBF branding (colors, logo).
- Set **Settings → General** site title and tagline for United States Pro Billiards Federation.

## Deep links

- **Pro Billiards app:** `https://app.example.com`
- **Rules in app (reference):** e.g. `https://app.example.com/rules` (if enabled in rankings-bot deployment)
