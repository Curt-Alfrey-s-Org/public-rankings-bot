"""
Fargo name variation helpers.

Keeps name normalization logic in one place for reuse across scrapers and scripts.
"""

from typing import List, Tuple


def generate_name_variations(name: str) -> List[str]:
    """
    Generate intelligent name variations for complex names.

    Handles:
    - Hyphens: "Al-Awadhi" -> ["Al-Awadhi", "Al Awadhi", "AlAwadhi"]
    - 3-part names: "Ropero Garcia, Maria" -> ["Maria Ropero Garcia", "Maria Ropero-Garcia"]
    - Compound surnames: "Nguyen Bich, Tram" -> ["Tram Nguyen Bich", "Tram Nguyen-Bich"]
    - Reversed formats: All variations tried in reverse order too
    - Single names: For Asian/Filipino players sometimes registered under one name
    - First initial combinations: "Jon Brown" might be registered as "J Brown"
    - Common spelling variants: "Ammit" vs "Amit", "Loree Jon" vs "LoreeJon"

    Returns list of unique variations to try.
    """
    variations = set()

    # Original name
    variations.add(name)

    # Parse "Last, First" format
    if "," in name:
        parts = name.split(",", 1)
        if len(parts) == 2:
            last_name = parts[0].strip()
            first_name = parts[1].strip()

            # Basic: "First Last"
            variations.add(f"{first_name} {last_name}")

            # Handle hyphens in BOTH parts
            if "-" in last_name or "-" in first_name:
                # Version with hyphens
                variations.add(f"{first_name} {last_name}")
                # Version with spaces instead of hyphens
                first_no_hyphen = first_name.replace("-", " ")
                last_no_hyphen = last_name.replace("-", " ")
                variations.add(f"{first_no_hyphen} {last_no_hyphen}")
                # Version with no separator (merge)
                first_merged = first_name.replace("-", "")
                last_merged = last_name.replace("-", "")
                variations.add(f"{first_merged} {last_merged}")
                # Hyphenate compound last name
                variations.add(f"{first_name} {last_name.replace(' ', '-')}")

            # Handle multi-part last names (e.g., "Ropero Garcia")
            if " " in last_name:
                last_parts = last_name.split()
                # Try: "First LastPart1 LastPart2"
                variations.add(f"{first_name} {' '.join(last_parts)}")
                # Try: "First LastPart1-LastPart2"
                variations.add(f"{first_name} {'-'.join(last_parts)}")
                # Try: just first part of last name
                variations.add(f"{first_name} {last_parts[0]}")
                # Try: just last part of last name
                variations.add(f"{first_name} {last_parts[-1]}")

            # Handle multi-part first names (e.g., "Loree Jon")
            if " " in first_name:
                first_parts = first_name.split()
                # Just first word of first name
                variations.add(f"{first_parts[0]} {last_name}")
                # Just last word of first name (sometimes registered as "Jon Brown" not "Loree Jon Brown")
                variations.add(f"{first_parts[-1]} {last_name}")
                # All first name parts with hyphen (CamelCase or hyphenated)
                variations.add(f"{'-'.join(first_parts)} {last_name}")
                # CamelCase: "LoreoJon"
                variations.add(f"{''.join(first_parts)} {last_name}")

            # Single name variation: try just first name or just last name
            # (Some Asian/Filipino players registered under single name)
            variations.add(first_name)
            variations.add(last_name)

            # First initial variations: "R Amit" or "Rubilen A"
            if first_name:
                variations.add(f"{first_name[0]} {last_name}")
            if last_name:
                variations.add(f"{first_name} {last_name[0]}")

    # For non-comma names, try reversals
    else:
        parts = name.split()
        if len(parts) >= 2:
            # Reverse: "First Last" -> "Last First"
            variations.add(" ".join(reversed(parts)))
            # With comma: "Last, First"
            variations.add(", ".join(reversed(parts)))
            # Single words
            for part in parts:
                variations.add(part)
            # First initial: "R Amit" or "Amit R"
            variations.add(f"{parts[0][0]} {' '.join(parts[1:])}")
            variations.add(f"{' '.join(parts[:-1])} {parts[-1][0]}")

            # Handle hyphens
            if any("-" in p for p in parts):
                # Remove hyphens
                no_hyphen_parts = [p.replace("-", " ") for p in parts]
                variations.add(" ".join(no_hyphen_parts))
                variations.add(" ".join(reversed(no_hyphen_parts)))

    # Remove duplicates and return sorted by simplicity (prefer simpler names first)
    unique_variations = sorted(variations, key=lambda x: (len(x.split()), len(x)))
    return unique_variations


def generate_high_confidence_name_variations(name: str) -> List[Tuple[str, str]]:
    """
    Generate conservative variation candidates for auto-fill.

    Returns:
    - List[(query, match_kind)] where match_kind indicates confidence class.

    Confidence policy:
    - exact_input / exact_reordered: high confidence
    - reordered_space / reordered_comma: medium-high (safe for 2-part names)
    - hyphen_*: medium-high normalization only
    - reduced_first_last: low confidence (3+ names reduced to 2 names; never auto-only)
    """
    raw = " ".join((name or "").split()).strip()
    if not raw:
        return []

    candidates: List[Tuple[str, str]] = []

    if "," in raw:
        parts = raw.split(",", 1)
        if len(parts) == 2:
            last_name = parts[0].strip()
            first_name = parts[1].strip()
            canonical = f"{first_name} {last_name}".strip()

            if raw:
                candidates.append((raw, "exact_input"))
            if canonical:
                candidates.append((canonical, "exact_reordered"))

            # Hyphen normalization on full forms.
            for base in (raw, canonical):
                if "-" in base:
                    candidates.append((" ".join(base.replace("-", " ").split()), "hyphen_to_space"))
                    candidates.append((base.replace("-", ""), "hyphen_removed"))

            # Low-confidence variation for 3+ token names.
            first_tokens = first_name.split()
            if len(first_tokens) >= 2 and last_name:
                candidates.append((f"{first_tokens[0]} {last_name}", "reduced_first_last"))
    else:
        parts = raw.split()
        candidates.append((raw, "exact_input"))

        if len(parts) >= 2:
            reordered_space = " ".join(reversed(parts))
            reordered_comma = f"{parts[-1]}, {' '.join(parts[:-1])}"
            candidates.append((reordered_space, "reordered_space"))
            candidates.append((reordered_comma, "reordered_comma"))

        if any("-" in p for p in parts):
            candidates.append((" ".join(p.replace("-", " ") for p in parts), "hyphen_to_space"))
            candidates.append((" ".join(p.replace("-", "") for p in parts), "hyphen_removed"))

        # Low-confidence variation for 3+ token names.
        if len(parts) >= 3:
            candidates.append((f"{parts[0]} {parts[-1]}", "reduced_first_last"))

    # Preserve insertion order; de-duplicate by normalized query.
    seen = set()
    out: List[Tuple[str, str]] = []
    for query, kind in candidates:
        normalized = " ".join((query or "").split()).strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append((normalized, kind))

    return out
