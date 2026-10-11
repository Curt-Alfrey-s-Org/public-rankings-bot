"""
Canonical WPBA Women PDF rotating-window column keys and display labels.

Roles:
- **Known-event dictionary** for the word-position parser's dynamic header
  discovery (``WPBAScraper._extract_column_headers``). Recurring events are
  matched to these canonical (key, label) pairs by token overlap so they keep
  stable keys/labels even when the rolling window shifts.
- **Static fallback** for the per-event column order when the PDF header cannot
  be read confidently (and for the older table / text-line parsers).
- DB tournament_history names (via ``wpba_column_labels`` in rankings source_data).

IMPORTANT: as of the dynamic-column-discovery change, ``WPBA_ROTATING_TEN_COLUMNS``
is NO LONGER the primary source of column *order* — the primary source is the
``<year> WPBA`` markers read live from the PDF header. When WPBA publishes a new
event it is discovered automatically (no edit here required). Keep this list in
sync only so recurring events keep their canonical keys/labels; keys must stay
aligned with ``PostgresManager.WPBA_WOMEN_COLUMN_MAPPING`` for the same events.
See ``docs/WPBA_TOURNAMENT_SSOT.md`` §5.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

# Known-event dictionary + static fallback order (newest → older slots).
# Labels match the official PDF / site naming used in the app.
WPBA_ROTATING_TEN_COLUMNS: List[Tuple[str, str]] = [
    ("2026_wpba_classic_billiards_championship", "2026 Classic Billiards Championship"),
    ("2026_wpba_olhausen_iron_city_invitational_vi", "2026 Iron City Invitational VI"),
    ("2025_wpba_dr_pool_jacoby_tour_championship", "2025 Jacoby Tour Championship"),
    ("2025_wpba_olhausen_colorado_classic", "2025 Colorado Classic"),
    ("2025_wpba_soaring_eagle_masters", "2025 Soaring Eagle Masters"),
    ("2025_wpba_olhausen_raxx_mezz_invitational", "2025 Raxx Mezz Invitational"),
    ("2025_wpba_olhausen_iron_city_invitational_v", "2025 Iron City Invitational V"),
    ("2024_wpba_dr_pool_jacoby_tour_championship", "2024 Jacoby Tour Championship"),
    ("2024_wpba_capital_city_billiards_invitational", "2024 Capital City Invitational"),
    ("2024_wpba_cuespeed_napa_invitational", "2024 Cuespeed NAPA Invitational"),
]

# When the PDF lists an 11th numeric column (event rotating out of the window), it must not
# overwrite another tournament column.
WPBA_ROTATING_11TH_KEY = "wpba_rotating_11th_slot"
WPBA_ROTATING_11TH_LABEL = "Rotating (11th / out of window)"


def wpba_default_column_labels() -> Dict[str, str]:
    """Map column_key -> display label for PDF-derived tournaments."""
    out = {k: v for k, v in WPBA_ROTATING_TEN_COLUMNS}
    out[WPBA_ROTATING_11TH_KEY] = WPBA_ROTATING_11TH_LABEL
    return out
