# Design Tokens — WPBA & WPA Theme Reference

This document captures theme and layout cues from the official **WPBA** and **WPA** websites so the Rankings Bot UI can align with their look and feel. Sources were inspected from live sites (wpba.com, wpapool.com/rankings/).

---

## Source URLs

| Site | URL | Notes |
|------|-----|--------|
| WPBA | https://wpba.com | Squarespace; women's professional billiards; events, news, players |
| WPA  | https://wpapool.com/rankings/ | Rankings table; WORLD RANKINGS; men's/women's |

---

## WPA (wpapool.com)

### Colors (from rankings page)
- **Table header:** background `#000000`, text `#ffffff` (strong contrast for rankings table).
- **Nav / footer:** Dark header area; white/light text on dark.
- **Logo:** WPA Primary Logo (wpapool.com) — use only with permission; link to official site.

### Layout
- **Headings:** "WORLD RANKINGS", "MEN'S PLAYER RANKING – [date]" — clear hierarchy, date in subtitle.
- **Table:** Rank, Player, WPA License Number, Country, Total Points, then tournament columns.
- **Nav:** Horizontal top nav — About, Our Members, Calendar, Rules, Rankings, News, Contact Us, LOG IN.
- **Footer:** Follow Us (YouTube, Instagram, Facebook, LinkedIn); logo repeated.

### Typography
- Sans-serif for UI; readable sizes for table and nav. Prefer clean, professional sans (e.g. system UI or Inter).

---

## WPBA (wpba.com)

### Brand
- **Name:** "Women's Professional Billiard Association".
- **Tagline / CTA:** "Meet the Best Players in the World" (with link to Players).
- **Logo:** Full-color WPBA logo with ® (Squarespace CDN); use only with permission.

### Layout
- **Hero:** Large event imagery; "Latest News"; YouTube subscribe CTA.
- **Events:** Card grid — image, date badge (e.g. Jan29, May1), title, location, date range.
- **Footer / bottom:** "Meet the Best Players in the World" + Players → link; full-width imagery (e.g. HomePage-Bottom.jpg).

### Colors & tone
- Clean, modern (Squarespace). White/light backgrounds with strong imagery; dark text on light for body.
- Accent for CTAs and links; professional, sport-focused.

### Typography
- Clear headings; event titles and dates prominent. Sans-serif for UI and cards.

---

## Suggested design tokens for Rankings Bot

Use these as a **respectful derivative** — we do not copy WPBA/WPA branding; we echo structure and tone.

| Token | Suggested value | Source / note |
|-------|-----------------|---------------|
| **Table header bg** | `#0a0a0a` or `hsl(0 0% 4%)` | WPA black header; slightly off-black for our app |
| **Table header text** | `#ffffff` | WPA white on black |
| **Primary (buttons, links)** | Keep existing `primary` or align to deep blue/green if desired | WPBA/WPA use accent for CTAs |
| **Content max-width** | `80rem` (1280px) or similar | Wide content for rankings tables |
| **Rankings title** | "Rankings" or "WORLD RANKINGS" style — large, clear | Both sites use strong page titles |
| **Card style** | Border, rounded, subtle bg | WPBA event cards; our stats/panels |
| **Nav** | Sidebar or top bar; clear labels (Rankings, Settings, Logs, System) | Matches “clear nav” from both |

### Optional CSS variables (Tailwind / index.css)

```css
/* Optional: WPA-style table header */
--rankings-table-header-bg: #000000;
--rankings-table-header-text: #ffffff;

/* Optional: WPBA-style “Meet the best” accent */
--wpba-tagline: "Meet the Best Players in the World";
```

---

## Layout patterns to reuse

1. **Rankings page:** Strong title + last-updated line; then stats cards; then association toggle (WPBA / WPA); then search + table; table header with clear contrast (WPA-style).
2. **Splash / hero:** Full-width imagery or gradient; short tagline (e.g. “WPBA & WPA Rankings”); CTA to enter or view rankings (see Roadmap Phase 2.2 splash).
3. **Footer:** Creator attribution (Example Example, alfaqd.com) + optional “Built for the sport” line; do not use WPBA/WPA logos without permission.
4. **Logo usage:** We do not embed WPBA or WPA logos without license; we can link to wpba.com and wpapool.com and use text (“WPBA”, “WPA”) or our own branding.

---

## Applying the theme in the app

- **Applied:** The app uses WPBA and WPA design tokens in `frontend/src/index.css` and `frontend/tailwind.config.js`:
  - **WPBA:** `--wpba-accent` (teal/green), `--wpba-card`; hero tagline “Meet the best players in the world”; WPBA button and Data Source card use WPBA accent when selected.
  - **WPA:** `--wpa-accent` (near-black), `--wpa-card`; hero tagline “Welcome to the world of pool”; WPA button and Data Source card use WPA accent when selected.
  - **Table:** `--rankings-table-header-bg` / `--rankings-table-header-text` (black/white, WPA-style) in `RankingsTable.tsx`.
  - **Splash:** “Meet the best players in the world” + “WPBA & WPA · World of Pool”. **Footer:** “WPBA & WPA rankings · self-hosted by alfaqd.com. Built for the sport by …”.
- **Legal:** Any use of official logos or imagery must be licensed; until then use placeholders, text, and links to the official sites.
