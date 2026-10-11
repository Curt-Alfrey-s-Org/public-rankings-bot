# Billiards Tournament Lifecycle — Full Process Analysis

**Purpose:** Describe the end-to-end lifecycle that tournament-management software (including **ProBilliardsSoftware** / probilliardssoftware.com) must model: creation, registration, brackets, live play, scoring, points, rankings, awards, and post-event reporting.

**Scope:** Cue sports pool tournaments as commonly run by associations (WPBA, WPA, BCA, leagues), informed by **Grokipedia** (grokipedia.com) articles on formats and rankings, governing-body rules, industry platforms (Digital Pool / Tournament Builder, IngenPool/BudTour, Bracketon/IBA, Scoreholio, RackEmApp), and FargoRate methodology.

### Canonical rules (WPBA / WPA) — source of truth

For **play rules** and association regulations, **official publications and this app’s Rules UI override** Grokipedia, Wikipedia, and any third-party summaries. If those secondary sources disagree with the PDFs or tour notices, follow the associations.

| Organization | Canonical rules (verify revision date on the PDF) |
|--------------|---------------------------------------------------|
| **WPBA** | [WPBA 9-Ball Rules (Rev 5.16.25)](https://static1.squarespace.com/static/5acf990e8ab7220efae54260/t/6827a9221dc42503382149e3/1747429667111/WPBA+9-Ball+Rules+-+%28Rev+5.16.25%29.pdf) |
| **WPA** | [WPA Rules of Play (2026.01.02)](https://wpapool.com/wp-content/uploads/2026/01/2026.01.02-WPA-Rules.pdf) |

Also use **Menu → Rules** in the web app: WPA lists bundled/serve endpoints under `/api/rules`; WPBA links tour PDFs and points materials.

**Production “New Tournament” vs Test Center:** Canonical director flow is the **4-step** wizard ([TOURNAMENT_WIZARD_VISUAL_OVERVIEW.md](TOURNAMENT_WIZARD_VISUAL_OVERVIEW.md) — `frontend/src/pages/TournamentWizard.tsx`). Test Center should align to that workflow; automation uses **APIs / shared code**, not UI clicks, and **restarts from step 1** after any error once fixed.

**Related code/docs:** For what this repo implements today, see [WPBA_TEST_CENTER_E2E.md](WPBA_TEST_CENTER_E2E.md), [TOURNAMENT_DIRECTOR_SCOREKEEPER_API.md](TOURNAMENT_DIRECTOR_SCOREKEEPER_API.md), and the roadmap [ROADMAP.md](ROADMAP.md). Test Center exercises an isolated subset of this lifecycle.

---

## 1. Pre-Tournament: Event Creation and Configuration

A tournament director (TD) creates the event with these core settings:

- **Identity**: Name, association (WPBA, WPA, BCA, local league), game type (9-Ball, 10-Ball, 8-Ball, Straight Pool, One-Pocket).
- **Format**: Single elimination, double elimination (true DE with bracket reset vs modified DE without), round-robin, hybrid (group stage into knockout), Swiss.
- **Field size**: 8 / 16 / 32 / 48 / 64 / 128 / 256. Clean brackets often use power-of-two sizing; **byes** fill gaps when the registered count is lower than draw size.
- **Race-to**: Per-stage (e.g., WPBA: race-to-7 Stage 1, race-to-8 Final Stage, race-to-10 Grand Final; WPA Nine-ball: race-to-11 main draw, race-to-15 final). Directors can override.
- **Break format**: Alternating break (WPBA standard), winner break, or player choice.
- **Handicap system (optional)**: BCA/Fargo, VNEA, TAP, APA — auto-calculates per-match race from rating differences.
- **Dates / location / venue**: Scheduling window, tables available, streaming table designation.
- **Prize pool**: Total prize, payout tiers per placement (winner, runner-up, semifinalists, etc.). Dynamic payouts that adjust as roster grows (commercial tools support this).
- **Points structure**: Tour points per placement. WPBA awards **150% points** for major events. WPA accumulates from world championships and regional opens.
- **Entry fee**: Stage 1 fee, Final Stage fee (WPBA-style multi-stage model), optional buy-back fee (re-entry in some bar/club formats).
- **Ranking system linkage**: Which ranking system(s) this event feeds (WPBA Women, WPA Men 9-Ball, Fargo-only events, etc.).

**Software expectation:** Allow saving tournament settings as **reusable templates** for recurring events.

---

## 2. Registration and Player Management

- **Player database**: Persistent roster with name, country, license number, Fargo rating (imported or manually entered), association membership, contact info.
- **Registration modes**: Online self-registration with payment (Stripe/PayPal), manual entry by TD, CSV/spreadsheet import, import from production ranking data (see Test Center WPBA import pattern in [WPBA_TEST_CENTER_E2E.md](WPBA_TEST_CENTER_E2E.md)).
- **Registration cap**: Max field size, waitlist when full, late-entry handling (late entries into specific bracket slots or preliminary rounds).
- **Seeding**: Automatic by ranking/rating, manual override by TD, random draw option. WPBA seeds top players into Final Stage; Stage 1 often uses random draw for qualifiers.
- **Player status**: Registered, confirmed (paid), checked-in (day-of QR code or manual), withdrawn, no-show.
- **Fargo integration**: Import current Fargo ratings for handicap calculations and seeding. FargoRate models win expectation from rating difference; a common published form is **`ratio = 2^(rating_difference / 100)`** (same rating ⇒ 1:1 expectation).

---

## 3. Bracket Generation

Core algorithmic and rules surface for the product.

### 3a. Double elimination (common in pool)

- **Winners bracket**: Single-elimination tree for undefeated players.
- **Losers bracket**: Parallel path for one-loss players; losers from the winners bracket drop into designated losers-bracket rounds.
- **Crossover points**: Losers bracket winners meet winners bracket survivors at defined junctions.
- **Grand final**: Winners bracket champion vs losers bracket champion.
  - **True DE (bracket reset)**: If the losers bracket champion wins the first grand final, a second **if-necessary** match may be required so both finalists have two losses except the champion — **WPBA-style implementations in this repo intentionally use a single grand final without bracket reset** (see Test Center / bracket engine docs).
  - **Modified DE (no bracket reset)**: One grand final match only.
- **Scale**: For *n* players, total matches is typically between **2(n−1)** and **2n−1** depending on finals rules.

### 3b. Single elimination

Simple knockout: **n−1** matches for *n* players. Often used for final stages after groups.

### 3c. Round-robin / group stage

Each player plays each other in the group: **n(n−1)/2** matches per group of size *n*. Used before knockout (e.g., large WPA-style events with multiple groups).

### 3d. Hybrid: groups into knockout

Groups play round-robin or mini-brackets; top finishers advance to single- or double-elimination playoffs.

### 3e. Swiss system

Pairings each round by current record; fixed rounds; no classical elimination until tie-break logic.

### Bracket mechanics

- **Bye allocation**: Typically winners-bracket byes for highest seeds to pad to draw size.
- **Seeding placement**: Snake seeding and similar patterns spread strong seeds across subtrees.
- **Draw size**: Bracket draw size can exceed registrants (e.g., 48 players in a 64 bracket with 16 byes).

---

## 4. Match Scheduling and Table Assignment

- **Table pool**: N tables, each identified for assignment and display URLs (commercial tools expose per-table scoring/TV URLs).
- **Match queue**: When a table frees, assign the next ready match from bracket dependency order.
- **Notifications**: SMS/push with opponent, table, estimated start time.
- **Streaming tables**: Featured tables with overlays for broadcast (OBS, Wirecast).
- **Projected match times**: Estimated from historical pace and race length.
- **Rest rules**: Minimum rest between matches per player where formats require it.

---

## 5. Live Scoring and Match Play

- **Score entry**: Per **rack** within a match (race-to-N). Tablet/mobile scoring at each table is an industry norm.
- **Roles**: Players and/or designated scorekeepers submit; TD approves to reduce disputes.
- **Score approval workflow**: Pending → TD approves → bracket advances winner → table released for next match (Digital Pool–style flow).
- **Winner advancement**: On approval, winner slots into next bracket match; loser drops or is eliminated per format.
- **Live updates**: Web/mobile bracket views and optionally SSE/WebSocket ([ROADMAP.md](ROADMAP.md) live odds / rack pipeline aligns here).
- **Match states**: Pending → Assigned → In progress → Completed (pending approval) → Approved.

---

## 6. Results, Rankings, and Points

### 6a. Placement determination

Winner, runner-up, tied semifinalists (3rd–4th), quarterfinalists (5th–8th), etc. In DE, losers-bracket depth determines lower placements.

### 6b. Points allocation

- Placement-based **tour points** from the event template (WPBA **R-points** bands; multipliers for majors).
- WPA-style **accumulated points** from sanctioned events (see Grokipedia / WPA rankings summaries).
- Other disciplines (e.g., English billiards WBL) use formulas combining group performance and knockout bonuses scaled by event level — pool software rarely implements WBL verbatim but illustrates configurable engines.

### 6c. Rankings update

- Points roll into season or rolling windows per governing body rules.
- **Seeding** for the next event reads the updated list.
- **FargoRate**: Match-result driven; global optimization-style updates (not the same as tour points tables).

### 6d. What this repo already handles

- WPBA/WPA ranking displays, Fargo sync, tournament history, leaderboard, hot streak.
- Test Center: isolated WPBA-style DE verification and mirrored read-only views ([WPBA_TEST_CENTER_E2E.md](WPBA_TEST_CENTER_E2E.md)).

---

## 7. Post-Tournament

- **Tournament history**: Bracket archive, match-by-match results, placements, points awarded.
- **Leaderboard / standings**: Tour standings after each event.
- **Awards / prizes**: Payout tiers tied to placement.
- **External rating submission**: Some directors submit results to FargoRate or league hubs (integration point for outbound APIs).
- **Reports**: Printable brackets, player stats (W/L, racks, win %).
- **Analytics**: Trends, rating trajectory, head-to-head — overlaps with roadmap “ExternalPool tournament intelligence” and live-estimated rating work ([ROADMAP.md](ROADMAP.md)).

---

## 8. Where Test Center Fits (This Repository)

| Lifecycle phase | Test Center (today) |
|-----------------|---------------------|
| Event creation (format, race, field, points) | Supported (setup flow) |
| Player registration (manual, demo seed, WPBA import) | Supported |
| Bracket generation (SE any power-of-2; DE 64-player only) | Supported |
| Match play | **Simulated**, not tablet/scorekeeper production flow |
| Score approval workflow | Not implemented |
| Table assignment / notifications | Not implemented |
| Placement + points calculation | Supported (WPBA-style bands) |
| Results persistence + mirrored rankings/history UI | Supported (test DB + `/api/test-center/*`) |
| Multi-tournament server library | Limited (`current` tournament API + history tables) |
| Template save/load | Partially (browser persistence; see Test Center components) |

---

## 9. Gap Analysis — Product vs Test Center

### Already built (production + Test Center)

- Ranking engine surfaces (WPBA, WPA, Fargo).
- Tournament history, leaderboard, hot streak.
- Single-elimination bracket engine (any power-of-2 draw size) + double-elimination (64-player, WPBA verification scope).
- Points structures and persistence paths for test mirrors.
- Fargo handicap calculator and race-from-Fargo (`api/services/fargo_handicap.py`, `apply-fargo-handicaps` / `calculate-handicap` routes).
- Round-robin / group-stage generation (`api/tournament_manager.py` `_generate_round_robin`).
- Outbound FargoRate submission scaffolding (`api/services/fargo_submit.py`, env-gated `POST .../submit-fargo`).
- Basic production match scoring (`PUT /matches/{id}/score`, winner advancement) and forfeit/DQ (`PATCH .../outcome`).

### Remaining build-outs for full tournament management

1. **Per-rack scoring + TD approval workflow**: Per-rack entry (not just final score), TD approval gate before bracket advancement.
2. **Table management**: Queue, assignment engine, status tracking, notifications (today only `table_number` field + manual updates).
3. **Swiss system**: Not implemented; round-robin and single/double elimination exist.
4. **Flexible DE draw sizes**: Beyond fixed 64-player double elimination — consistent bye and seeding rules for other field sizes.
5. **Online registration + payments**: Self-service tournament signup with fee collection (Stripe exists for app subscriptions, not tournament entry).
6. **Live display / streaming**: Public bracket TV mode, broadcast overlays (live-update hooks exist but no full streaming product).
7. **Series / multi-event**: Concurrent events under one organizer account.
8. **Mobile-first scoring**: Dedicated scorekeeper UX.
9. **Director operations**: Disputes, re-draws (forfeit/DQ partially implemented; see [TOURNAMENT_DIRECTOR_SCOREKEEPER_API.md](TOURNAMENT_DIRECTOR_SCOREKEEPER_API.md)).
10. **Prize payout tooling**: Placement-driven payout worksheets (`prize_pool` fields exist, no worksheet engine).

---

## Sources (external)

**Precedence:** Official WPBA/WPA PDFs (canonical rules table at top of this doc) and association sites trump Grokipedia and informal summaries.

- **WPBA (official):** [WPBA 9-Ball Rules PDF (Rev 5.16.25)](https://static1.squarespace.com/static/5acf990e8ab7220efae54260/t/6827a9221dc42503382149e3/1747429667111/WPBA+9-Ball+Rules+-+%28Rev+5.16.25%29.pdf); tour points and notices via [wpba.com/rules](https://wpba.com/rules).
- **WPA (official):** [WPA Rules of Play PDF (2026.01.02)](https://wpapool.com/wp-content/uploads/2026/01/2026.01.02-WPA-Rules.pdf); [wpapool.com/rules](https://wpapool.com/rules/).
- **Grokipedia (context only):** [Double-elimination tournament](https://grokipedia.com/page/Double-elimination_tournament), [Billiards world rankings](https://grokipedia.com/page/Billiards_world_rankings), [WPA World Nine-ball Championship](https://grokipedia.com/page/WPA_World_Nine-ball_Championship), [U.S. Open Pool Championship](https://grokipedia.com/page/U.S._Open_Pool_Championship), [World Pool Masters](https://grokipedia.com/page/World_Pool_Masters), [WPA World Eight-ball Championship](https://grokipedia.com/page/WPA_World_Eight-ball_Championship).
- **FargoRate**: [fargorate.com](https://fargorate.com/) — methodology and operator-facing FAQs.
- **Digital Pool**: [Tournament Builder quick start](https://docs.digitalpool.com/tournament-builder-quick-start-guide) — TD workflow, tablet scoring, overlays.
- **IngenPool / BudTour**: [budtour.com](https://budtour.com/) — formats, exports, Fargo-oriented workflows.
- **Bracketon / IBA**: [ibapool.com](https://www.ibapool.com/Bracketon) — notifications, live statistics patterns.
- **Scoreholio**: [scoreholio.com](https://scoreholio.com/billiards/tournaments/) — mobile-first tournament ops.
- **RackEmApp**: [rackemapp.com](https://www.rackemapp.com/) — leagues and competitions.

---

## Doc refs (AI / maintainers)

- When changing **tournament UX, bracket rules, or TD/scorekeeper APIs**, cross-check this doc against [TOURNAMENT_DIRECTOR_SCOREKEEPER_API.md](TOURNAMENT_DIRECTOR_SCOREKEEPER_API.md), [WPBA_TEST_CENTER_E2E.md](WPBA_TEST_CENTER_E2E.md), and [CHANGELOG_20260410_TOURNAMENT_OVERHAUL.md](CHANGELOG_20260410_TOURNAMENT_OVERHAUL.md).
- Governing-body PDFs and purse structures change seasonally — treat association PDFs and websites as **source of truth** over Grokipedia and other summaries.

**Last updated:** 2026-05-04 — Canonical WPBA/WPA rule PDF URLs and precedence; lifecycle synthesis (Grokipedia + industry context).
