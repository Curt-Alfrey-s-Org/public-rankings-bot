"""
Association scopes for ranking writes (imports, manual entry, copy-from-import, tournament merge).

- Maps ranking_system and user_associations.association rows to canonical scopes: WPBA, WPA, CP, LOCAL.
- Directors may only write systems whose scope is in their user_associations-derived scope set.
- admin and super_admin bypass scope checks.

Doc refs: docs/DIRECTOR_IMPORT.md; docs/ROLE_CAPABILITIES.md
"""

from __future__ import annotations

import re
from typing import FrozenSet, List, Optional, Set, Tuple

from sqlalchemy import text

# All systems accepted by POST /rankings/import and /import/manual (single source of truth).
IMPORTABLE_SYSTEMS_EXPLICIT: FrozenSet[str] = frozenset(
    {
        "WPBA",
        "WPA",
        "WPBA_Women",
        "WPA_Women",
        "WPA_Men",
        "WPA_Artistic",
        "WPA_Heyball_Men",
        "WPA_Heyball_Women",
        "Competitors_Pool_9Ball",
        "Competitors_Pool_10Ball",
        "Competitors_Pool_8Ball",
        "Competitors_Pool_Women_9Ball",
        "Competitors_Pool_Men_9Ball",
        "Competitors_Pool_Mixed_9Ball",
        "WPA_Women_9Ball",
        "WPA_Women_ChinaOpen",
        "WPA_Men_JPBA_JapanOpen",
        "WPA_Women_9B_WorldChamp",
        "WPA_Women_LittleMonster",
        "WPA_Women_AllJapan57",
        "WPA_Women_DRPoolTour",
        "WPA_Women_WPBA_Colorado",
        "WPA_Women_WPBA_IronCity",
        "WPA_Women_WPBA_RaxxMezz",
        "WPA_Women_WPBA_SEMasters",
        "WPBA_Women_IronCityVI",
        "WPBA_Women_Jacoby2025",
        "WPBA_Women_Colorado2025",
        "WPBA_Women_SoaringEagle2025",
        "WPBA_Women_RaxxMezz2025",
        "WPBA_Women_IronCityV",
        "WPBA_Women_Jacoby2024",
        "WPBA_Women_CapitalCity2024",
        "WPBA_Women_NAPA2024",
        "WPBA_Women_Colorado2024",
        "WPBA_Women_Palmetto",
        "LOCAL",
    }
)

# Align with DB dynamic CHECK patterns (e.g. alembic 044 WPBA_Women_*, 051 WPA_Women_*).
_DYNAMIC_RANKING_SYSTEM_PATTERNS: Tuple[Tuple[re.Pattern, str], ...] = (
    (re.compile(r"^WPBA_Women_[A-Za-z0-9_]+$"), "WPBA"),
    (re.compile(r"^WPA_Women_[A-Za-z0-9_]+$"), "WPA"),
    (re.compile(r"^WPA_Men_[A-Za-z0-9_]+$"), "WPA"),
)


def ranking_system_scope(ranking_system: str) -> Optional[str]:
    """Return canonical scope for a ranking_system, or None if not recognized."""
    if not ranking_system or not str(ranking_system).strip():
        return None
    s = str(ranking_system).strip()
    if s == "LOCAL":
        return "LOCAL"
    if s.startswith("Competitors_Pool_"):
        return "CP"
    if s.startswith("WPBA"):
        return "WPBA"
    if s.startswith("WPA"):
        return "WPA"
    return None


def association_membership_to_scope(membership: str) -> Optional[str]:
    """Map a user_associations.association value to a canonical scope."""
    if not membership or not str(membership).strip():
        return None
    m = str(membership).strip()
    if m.upper() == "LOCAL" or m.startswith("LOCAL"):
        return "LOCAL"
    if m.startswith("Competitors_Pool_") or m.upper() in ("CP", "COMPETITORS_POOL"):
        return "CP"
    if m.startswith("WPBA"):
        return "WPBA"
    if m.startswith("WPA"):
        return "WPA"
    return None


def is_valid_ranking_system_for_import(ranking_system: str) -> bool:
    """True if ranking_system is explicitly allowed or matches a dynamic DB-aligned pattern."""
    if not ranking_system or not str(ranking_system).strip():
        return False
    s = str(ranking_system).strip()
    if s in IMPORTABLE_SYSTEMS_EXPLICIT:
        return True
    for pat, _scope in _DYNAMIC_RANKING_SYSTEM_PATTERNS:
        if pat.match(s):
            return True
    return False


def explicit_importable_systems_for_scopes(scopes: Set[str]) -> List[str]:
    """Filter explicit system names to those whose scope is in scopes."""
    out = [sys for sys in sorted(IMPORTABLE_SYSTEMS_EXPLICIT) if ranking_system_scope(sys) in scopes]
    return out


def get_user_association_scopes(username: str) -> Set[str]:
    """
    Load canonical scopes for a user from user_associations (via users.username).
    Returns empty set if user not found or no rows.
    """
    if not username or not str(username).strip():
        return set()
    from database import get_engine

    engine = get_engine()
    scopes: Set[str] = set()
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT DISTINCT ua.association
                    FROM user_associations ua
                    INNER JOIN users u ON u.id = ua.user_id
                    WHERE LOWER(TRIM(u.username)) = LOWER(TRIM(:username))
                    """
                ),
                {"username": username.strip()},
            )
            for row in result.fetchall():
                if row and row[0]:
                    sc = association_membership_to_scope(str(row[0]))
                    if sc:
                        scopes.add(sc)
    except Exception:
        # Table missing or DB error: treat as no scopes (directors blocked until fixed)
        return set()
    return scopes


def director_may_write_ranking_systems(user: dict, ranking_systems: List[str]) -> Tuple[bool, str]:
    """
    Returns (allowed, error_message). admin/super_admin always allowed.
    director must have every system's scope in their association scopes.
    """
    role = (user or {}).get("role") or ""
    if role in ("admin", "super_admin"):
        return True, ""
    if role != "director":
        return True, ""

    username = (user or {}).get("sub") or ""
    scopes = get_user_association_scopes(username)
    if not scopes:
        return (
            False,
            "No association is assigned to your account. An administrator must assign your "
            "association (Data input / user settings) before you can import or update rankings.",
        )

    for sys in ranking_systems:
        if not sys:
            continue
        if not is_valid_ranking_system_for_import(sys):
            return False, f"Invalid or unsupported ranking system: {sys}"
        need = ranking_system_scope(sys)
        if need is None:
            return False, f"Unknown ranking system: {sys}"
        if need not in scopes:
            return (
                False,
                f"You may only update rankings for your assigned association(s): {', '.join(sorted(scopes))}. "
                f"This action targets a different scope ({need}).",
            )
    return True, ""


def tournament_merge_system_to_scope(system: str) -> Optional[str]:
    """WPBA / WPA query param for tournament merge -> scope."""
    u = (system or "").strip().upper()
    if u == "WPBA":
        return "WPBA"
    if u == "WPA":
        return "WPA"
    return None


def director_may_access_tournament_imports(user: dict, system: str) -> Tuple[bool, str]:
    """List/filter tournament imports by WPBA or WPA bucket (same scope rules as merge)."""
    return director_may_run_tournament_ranking_merge(user, system)


def director_may_modify_tournament_import_by_id(user: dict, import_ranking_system: Optional[str]) -> Tuple[bool, str]:
    """import_ranking_system from tournament_imports row (typically WPBA or WPA)."""
    if not import_ranking_system:
        return False, "Invalid tournament import"
    return director_may_run_tournament_ranking_merge(user, str(import_ranking_system))


def director_may_run_tournament_ranking_merge(user: dict, system: str) -> Tuple[bool, str]:
    """system is WPBA or WPA from query param."""
    role = (user or {}).get("role") or ""
    if role in ("admin", "super_admin"):
        return True, ""
    if role != "director":
        return True, ""
    need = tournament_merge_system_to_scope(system)
    if need is None:
        return False, "system must be WPBA or WPA"
    username = (user or {}).get("sub") or ""
    scopes = get_user_association_scopes(username)
    if not scopes:
        return (
            False,
            "No association is assigned to your account. An administrator must assign your association first.",
        )
    if need not in scopes:
        return (
            False,
            f"You may only run tournament ranking updates for your assigned association(s): {', '.join(sorted(scopes))}.",
        )
    return True, ""


def import_eligibility_payload(user: dict) -> dict:
    """Response body for GET /rankings/import/eligibility (Data input UI)."""
    role = (user or {}).get("role") or ""
    username = (user or {}).get("sub") or ""
    if role in ("admin", "super_admin"):
        systems = sorted(IMPORTABLE_SYSTEMS_EXPLICIT)
        return {
            "role": role,
            "scopes": ["WPBA", "WPA", "CP", "LOCAL"],
            "allowed_systems": systems,
            "full_access": True,
            "dynamic_patterns": [
                {"pattern": "WPBA_Women_*", "scope": "WPBA"},
                {"pattern": "WPA_Women_*", "scope": "WPA"},
                {"pattern": "WPA_Men_*", "scope": "WPA"},
            ],
            "needs_association_assignment": False,
        }

    if role != "director":
        return {
            "role": role,
            "scopes": [],
            "allowed_systems": [],
            "full_access": False,
            "dynamic_patterns": [],
            "needs_association_assignment": True,
        }

    scopes_set = get_user_association_scopes(username)
    systems = explicit_importable_systems_for_scopes(scopes_set)
    return {
        "role": role,
        "scopes": sorted(scopes_set),
        "allowed_systems": systems,
        "full_access": False,
        "dynamic_patterns": (
            [
                {"pattern": "WPBA_Women_*", "scope": "WPBA"},
                {"pattern": "WPA_Women_*", "scope": "WPA"},
                {"pattern": "WPA_Men_*", "scope": "WPA"},
            ]
            if scopes_set
            else []
        ),
        "needs_association_assignment": len(scopes_set) == 0,
    }
