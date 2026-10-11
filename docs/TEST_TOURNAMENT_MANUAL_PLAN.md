# Test Tournament Manual Plan (Classic Billiards)

## Goal
Validate full tournament flow using a test tournament that is excluded from live rankings.

## Pre-reqs
- Super admin account (to create and view test tournaments).
- PDF available at /home/ansible/2026+WPBA+Ranking+Post+Classic+Billiards+MASTER.pdf.
- Rankings API running with Postgres.

## Steps
1. Create a test tournament
   - Open the Tournament Wizard.
   - Toggle "Test tournament (hidden from live rankings)".
   - Set name: "2026 WPBA Classic's Players Championship (TEST)".
   - Set elimination type: double.
   - Set max players: 64.
   - Save and generate bracket.

2. Import External Pool data
   - Run:
     - python3 scripts/import_competitors_tournament.py \
         --slug 2026-wpba-classics-players-championship \
         --tournament-id <TXXXXXX> \
         --generate-bracket
   - Verify matches are populated and scores are set in bracket view.

3. Validate placements and points
   - Run:
     - python3 scripts/parse_classic_billiards_pdf.py \
         --tournament-id <TXXXXXX>
   - Confirm mismatches are zero or explainable (name variations, late entries).

4. Validate visibility
   - Log in as a non-super-admin user.
   - Confirm the test tournament does not show in tournament lists.
   - Confirm rankings do not change after test import.

5. Validate rankings exclusion
   - As super admin, confirm the tournament is marked as test.
   - Recalculate rankings if needed.
   - Verify no changes in live rankings totals.

## Expected Results
- Test tournament is visible only to super admins.
- Matches and scores match External Pool bracket.
- Points and placements match PDF for Classic Billiards.
- No changes appear in live rankings.
