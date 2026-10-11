"""
Parse uploaded files (PDF, DOCX, XLSX, XML, CSV, TXT) into ranking rows.
Output: list of dicts {rank, name, points, country, license_number?, stops_played?} for DB.
All columns present in the source are returned so imports persist to rankings table.
"""
import re
import io
import csv
import logging
from typing import List, Dict, Any, Optional, Tuple
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

def _normalize_header_key(text: str) -> str:
    """Normalize import headers the same way as WPA scraper header keys."""
    t = (text or "").strip().lower()
    t = re.sub(r"\s+", "_", t)
    t = re.sub(r"[^\w]", "", t)
    return t


# Explicit mappings avoid collapsing multiple 9-ball/10-ball columns into one system.
WPA_MEN_HEADER_TO_SYSTEM: Dict[str, str] = {
    # Current WPA table columns
    "jax_mens_international_open_2025": "WPA_Men_10B_Polish",
    "little_monster_international_open_2025": "WPA_Men_Maldives",
    "58th_all_japan_open_2025": "WPA_Men_HCM",
    "international_9ball_open_2025": "WPA_Men_9B_IntlOpen",
    "qatar_world_cup_10ball_2025": "WPA_Men_10B_Qatar",
    "yalin_wpa_8ball_world_championship_2025": "WPA_Men_Yalin_8Ball",
    "predator_wpa_10ball_world_championship_2025": "WPA_Men_Predator_10B",
    "38th_jpba_japan_open_2025": "WPA_Men_JPBA_JapanOpen",
    "pudong_tangcheng_wpa_9ball_china_open_2025": "WPA_Men_9B_ChinaOpen",
    "9ball_world_championship_2025": "WPA_Men_9B_WorldChamp",
    "indonesia_international_10ball_open_2025": "WPA_Men_10B_Indonesia",
    "kamui_las_vegas_open_2025": "WPA_Men_Kamui_LasVegas",
    # Legacy aliases
    "international_open_9ball_2024": "WPA_Men_9B_IntlOpen",
    "qatar_world_cup_10ball_2024": "WPA_Men_10B_Qatar",
    "polish_open_10ball_2024": "WPA_Men_10B_Polish",
    "maldives_open_2024": "WPA_Men_Maldives",
    "hcm_open_2024": "WPA_Men_HCM",
}

WPA_WOMEN_HEADER_TO_SYSTEM: Dict[str, str] = {
    # Current WPA table columns
    "wpa_9ball_world_championship_2025": "WPA_Women_9B_WorldChamp",
    "little_monster_international_open_2025": "WPA_Women_LittleMonster",
    "57th_all_japan_championship_2025": "WPA_Women_AllJapan57",
    "wpba_dr_pool_tour_championship_2025": "WPA_Women_DRPoolTour",
    "predator_wpa_10ball_world_championship_2025": "WPA_Women_10B_Predator",
    "poison_saigon_9ball_open_2025": "WPA_Women_9Ball",
    "japan_open_2025": "WPA_Women_JapanOpen",
    "china_open_2025": "WPA_Women_ChinaOpen",
    "wpba_olhausen_colorado_classic_2025": "WPA_Women_WPBA_Colorado",
    "indonesia_10ball_open_2025": "WPA_Women_10B_Indonesia",
    "wpa_8ball_world_championship_2025": "WPA_Women_8Ball",
    "wpba_se_masters_2025": "WPA_Women_WPBA_SEMasters",
    "wpba_raxx_mezz_2025": "WPA_Women_WPBA_RaxxMezz",
    "kamui_las_vegas_open_2025": "WPA_Women_Kamui_LasVegas",
    "wpba_olhausen_ironcity_2025": "WPA_Women_WPBA_IronCity",
}

# Generic column mapping for non-WPA-specific import contexts.
GENERIC_COLUMN_HEADER_TO_RANKING: List[Tuple[str, Optional[str]]] = [
    ("mixed_9", "Competitors_Pool_Mixed_9Ball"),
    ("mixed_9ball", "Competitors_Pool_Mixed_9Ball"),
    ("8ball", "Competitors_Pool_8Ball"),
    ("10ball", "Competitors_Pool_10Ball"),
    ("9ball", "Competitors_Pool_9Ball"),
    ("artistic", "WPA_Artistic"),
    ("heyball", None),  # resolved by import_context -> WPA_Heyball_Men or WPA_Heyball_Women
]

# Allowed extensions
ALLOWED_EXTENSIONS = {"pdf", "docx", "xlsx", "xml", "csv", "txt"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/xml",
    "text/xml",
    "text/csv",
    "text/plain",
}


def _header_to_ranking_system(header: str, import_context: str) -> Optional[str]:
    """Map a column header (e.g. 'Yalin 8-ball world championship 2025') to ranking_system, or None for main/unknown."""
    h = _normalize_header_key(header)
    if not h:
        return None

    ctx = (import_context or "").strip()
    if ctx == "WPA_Men" and h in WPA_MEN_HEADER_TO_SYSTEM:
        return WPA_MEN_HEADER_TO_SYSTEM[h]
    if ctx == "WPA_Women" and h in WPA_WOMEN_HEADER_TO_SYSTEM:
        return WPA_WOMEN_HEADER_TO_SYSTEM[h]

    for keyword, system in GENERIC_COLUMN_HEADER_TO_RANKING:
        if keyword in h:
            if system is None:
                return "WPA_Heyball_Men" if "men" in import_context.lower() else "WPA_Heyball_Women"
            return system
    return None


def _normalize_row(
    rank: int,
    name: str,
    points: float = 0.0,
    country: str = None,
    license_number: Optional[str] = None,
    stops_played: Optional[int] = None,
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "rank": rank,
        "name": (name or "").strip(),
        "points": float(points or 0),
        "country": (country or "").strip() or None,
    }
    if license_number is not None and str(license_number).strip():
        row["license_number"] = str(license_number).strip()
    if stops_played is not None:
        try:
            row["stops_played"] = int(stops_played)
        except (TypeError, ValueError) as e:
            logger.debug("Could not parse stops_played '%s': %s", stops_played, e)
    return row


def parse_text_to_rows(text: str) -> List[Dict[str, Any]]:
    """Parse plain text (tab or comma separated) into ranking rows. Tolerates WPA-style header. Optional license, stops columns."""
    rows = []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    start = 0
    header_parts: Optional[List[str]] = None
    col_license: Optional[int] = None
    col_stops: Optional[int] = None
    for i, line in enumerate(lines):
        if re.match(r"^Position\s|^Rank\s|^#\s", line, re.I) or line.lower().startswith("rank,"):
            start = i + 1
            # Detect header for optional columns
            parts = re.split(r"\t+", line) if "\t" in line else next(csv.reader(io.StringIO(line), skipinitialspace=True), [line])
            parts = [p.strip().lower() for p in parts if p is not None]
            if any("rank" in (p or "") or "position" in (p or "") for p in parts):
                header_parts = parts
                col_license = _header_col_index(parts, "license", "wpa license", "license number")
                col_stops = _header_col_index(parts, "stops", "stops played", "tournaments")
            break
    for line in lines[start:]:
        parts = re.split(r"\t+", line) if "\t" in line else next(csv.reader(io.StringIO(line), skipinitialspace=True), [line])
        parts = [p.strip() for p in parts if p is not None]
        if len(parts) < 2:
            continue
        try:
            rank = int(re.sub(r"[^\d]", "", parts[0]) or 0)
        except (ValueError, TypeError):
            continue
        name = parts[1] if len(parts) > 1 else ""
        if len(parts) >= 4 and not re.match(r"^[\d.,$]+$", parts[2]):
            name = f"{parts[1]} {parts[2]}".strip()
        points = 0.0
        country = None
        for j in range(2, min(len(parts), 6)):
            raw = (parts[j] or "").replace(",", "").replace("$", "")
            try:
                points = float(raw)
                break
            except ValueError:
                if len(parts[j]) <= 4 and parts[j].isalpha():
                    country = parts[j]
        license_number = None
        if col_license is not None and col_license < len(parts) and parts[col_license]:
            license_number = parts[col_license].strip()
        stops_played = None
        if col_stops is not None and col_stops < len(parts) and parts[col_stops]:
            try:
                stops_played = int(float(parts[col_stops].replace(",", "")))
            except (ValueError, TypeError) as e:
                logger.debug("Could not parse text stops column '%s': %s", parts[col_stops], e)
        if not name:
            continue
        rows.append(_normalize_row(rank, name, points, country, license_number=license_number, stops_played=stops_played))
    return rows


def parse_pdf(content: bytes) -> List[Dict[str, Any]]:
    """Extract text from PDF and parse into ranking rows."""
    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber not available for PDF import")
        return []
    text_parts = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return parse_text_to_rows("\n".join(text_parts))


def parse_docx(content: bytes) -> List[Dict[str, Any]]:
    """Extract text or tables from DOCX and parse into ranking rows."""
    try:
        from docx import Document
    except ImportError:
        logger.warning("python-docx not available for DOCX import")
        return []
    doc = Document(io.BytesIO(content))
    # Prefer tables
    for table in doc.tables:
        rows = []
        for i, row in enumerate(table.rows):
            cells = [c.text.strip() for c in row.cells]
            if not any(cells):
                continue
            if i == 0 and any("position" in c.lower() or "rank" in c.lower() for c in cells):
                continue
            try:
                rank = int(re.sub(r"[^\d]", "", cells[0]) or 0)
            except (ValueError, TypeError, IndexError):
                continue
            name = (cells[1] if len(cells) > 1 else "") or (cells[2] if len(cells) > 2 else "")
            if len(cells) > 3 and cells[2] and not re.match(r"^[\d.,$]+$", cells[2]):
                name = f"{cells[1]} {cells[2]}".strip()
            points = 0.0
            country = None
            for c in cells[2:6]:
                raw = (c or "").replace(",", "").replace("$", "")
                try:
                    points = float(raw)
                    break
                except ValueError:
                    if c and len(c) <= 4 and c.isalpha():
                        country = c
            if name:
                rows.append(_normalize_row(rank, name, points, country))
        if rows:
            return rows
    # Alternative: parse paragraphs as text
    text = "\n".join(p.text for p in doc.paragraphs if p.text)
    return parse_text_to_rows(text)


def _header_col_index(header: List[str], *names: str) -> Optional[int]:
    """Return 0-based column index if any of names appears in header (substring match, case-insensitive)."""
    for i, h in enumerate(header):
        h_lower = (h or "").lower()
        for n in names:
            if n in h_lower or h_lower in n:
                return i
    return None


def parse_xlsx(content: bytes) -> List[Dict[str, Any]]:
    """Read first sheet of XLSX; columns Rank/Position, Name, Points, Country; optional License, Stops."""
    try:
        import openpyxl
    except ImportError:
        logger.warning("openpyxl not available for XLSX import")
        return []
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    if not ws:
        return []
    rows = []
    header_row: Optional[List[str]] = None
    col_license: Optional[int] = None
    col_stops: Optional[int] = None
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        row = [str(c).strip() if c is not None else "" for c in row]
        if not any(row):
            continue
        if i == 0 and any("rank" in (c or "").lower() or "position" in (c or "").lower() for c in row):
            header_row = [(c or "").strip().lower() for c in row]
            col_license = _header_col_index(header_row, "license", "wpa license", "license number")
            col_stops = _header_col_index(header_row, "stops", "stops played", "tournaments")
            continue
        try:
            rank = int(float(row[0])) if row[0] is not None and str(row[0]).replace(".", "").isdigit() else i + 1
        except (ValueError, TypeError):
            rank = i + 1
        name = (row[1] if len(row) > 1 else "") or (row[2] if len(row) > 2 else "")
        if len(row) > 3 and row[2] and not str(row[2]).replace(".", "").replace(",", "").isdigit():
            name = f"{row[1]} {row[2]}".strip()
        points = 0.0
        country = None
        for j in range(2, min(len(row), 6)):
            try:
                points = float(str(row[j]).replace(",", "").replace("$", ""))
                break
            except (ValueError, TypeError):
                if row[j] and len(str(row[j])) <= 4:
                    country = str(row[j])
        license_number = None
        if col_license is not None and col_license < len(row) and row[col_license]:
            license_number = str(row[col_license]).strip()
        stops_played = None
        if col_stops is not None and col_stops < len(row) and row[col_stops] is not None:
            try:
                stops_played = int(float(str(row[col_stops]).replace(",", "")))
            except (ValueError, TypeError) as e:
                logger.debug("Could not parse XLSX stops column '%s': %s", row[col_stops], e)
        if name:
            rows.append(_normalize_row(rank, name, points, country, license_number=license_number, stops_played=stops_played))
    wb.close()
    return rows


def _xlsx_grid(content: bytes) -> Tuple[Optional[List[str]], List[List[Any]]]:
    """Read first sheet of XLSX into header row (or None) and data rows. Cells as strings/numbers."""
    try:
        import openpyxl
    except ImportError:
        return None, []
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    if not ws:
        wb.close()
        return None, []
    header_row: Optional[List[str]] = None
    data_rows: List[List[Any]] = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        row = [c if c is not None else "" for c in row]
        if not any(str(c).strip() for c in row):
            continue
        if i == 0 and any(
            "rank" in str(c or "").lower() or "position" in str(c or "").lower() or "name" in str(c or "").lower()
            for c in row
        ):
            header_row = [str(c).strip() if c is not None else "" for c in row]
            continue
        data_rows.append([c for c in row])
    wb.close()
    return header_row, data_rows


def parse_xlsx_multi_columns(content: bytes, import_context: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Parse XLSX with multiple tournament columns. Each column header (e.g. 'Yalin 8-ball world championship 2025')
    is mapped to a ranking_system; that column's points are combined with Name/Country from fixed columns.
    import_context is 'WPA_Men' or 'WPA_Women' (for main list and Heyball Men/Women).
    Returns dict: ranking_system -> list of {rank, name, points, country, ...}.
    """
    header_row, data_rows = _xlsx_grid(content)
    if not header_row or not data_rows:
        return {}
    # Fixed column indices
    col_rank = _header_col_index(header_row, "rank", "position", "pos")
    col_name = _header_col_index(header_row, "name", "player", "playername")
    col_country = _header_col_index(header_row, "country", "nation")
    col_license = _header_col_index(header_row, "license", "wpa license", "license number")
    col_stops = _header_col_index(header_row, "stops", "stops played", "tournaments")
    if col_name is None:
        col_name = 1 if col_rank == 0 else 0
    # Data columns: indices that are not rank/name/country/license/stops
    fixed = {col_rank, col_name, col_country, col_license, col_stops}
    fixed.discard(None)
    data_cols: List[Tuple[int, str]] = []
    for j, raw_h in enumerate(header_row):
        if j in fixed:
            continue
        h = (raw_h or "").strip()
        if not h or h.lower() in ("", "rank", "position", "name", "player", "country", "license", "stops"):
            continue
        data_cols.append((j, raw_h or ""))
    if not data_cols:
        return {}
    main_system = import_context if import_context in ("WPA_Men", "WPA_Women") else "WPA_Men"
    assigned: Dict[str, Optional[int]] = {}  # ranking_system -> column index (first column that maps)
    for j, raw_h in data_cols:
        system = _header_to_ranking_system(raw_h, import_context)
        if system and system not in assigned:
            assigned[system] = j
        elif system is None and main_system not in assigned:
            assigned[main_system] = j
    result: Dict[str, List[Dict[str, Any]]] = {}
    for system, col_idx in assigned.items():
        if col_idx is None:
            continue
        rows_for_system = []
        for r, data_row in enumerate(data_rows):
            name = ""
            if col_name is not None and col_name < len(data_row):
                name = str(data_row[col_name] or "").strip()
            if not name:
                continue
            try:
                points = float(str(data_row[col_idx] or "0").replace(",", "").replace("$", ""))
            except (ValueError, TypeError):
                points = 0.0
            rank_val = r + 1
            if col_rank is not None and col_rank < len(data_row):
                try:
                    rank_val = int(float(str(data_row[col_rank] or "0").replace(",", "")))
                except (ValueError, TypeError) as e:
                    logger.debug("Could not parse XLSX rank value '%s': %s", data_row[col_rank], e)
            country = None
            if col_country is not None and col_country < len(data_row) and data_row[col_country]:
                country = str(data_row[col_country]).strip()
            license_number = None
            if col_license is not None and col_license < len(data_row) and data_row[col_license]:
                license_number = str(data_row[col_license]).strip()
            stops_played = None
            if col_stops is not None and col_stops < len(data_row) and data_row[col_stops] is not None:
                try:
                    stops_played = int(float(str(data_row[col_stops]).replace(",", "")))
                except (ValueError, TypeError) as e:
                    logger.debug("Could not parse XLSX multi-column stops '%s': %s", data_row[col_stops], e)
            rows_for_system.append(
                _normalize_row(rank_val, name, points, country, license_number=license_number, stops_played=stops_played)
            )
        if rows_for_system:
            # Re-rank by points descending so rank reflects order
            rows_for_system.sort(key=lambda x: (-float(x["points"]), x["name"]))
            for i, row in enumerate(rows_for_system):
                row["rank"] = i + 1
            result[system] = rows_for_system
    return result


def parse_file_multi_columns(
    content: bytes, filename: str, import_context: str
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Parse file (XLSX or CSV) with multiple tournament columns; map each column to a ranking_system.
    import_context: 'WPA_Men' or 'WPA_Women'. Returns {} if format not supported or single-table.
    """
    ext = (filename or "").split(".")[-1].lower() if "." in (filename or "") else ""
    if ext == "xlsx":
        return parse_xlsx_multi_columns(content, import_context)
    if ext in ("csv", "txt"):
        # CSV: same idea - first row headers, then data; reuse logic via a small grid builder
        try:
            text = content.decode("utf-8", errors="replace")
        except Exception:
            text = content.decode("latin-1", errors="replace")
        reader = csv.reader(io.StringIO(text))
        lines = list(reader)
        if len(lines) < 2:
            return {}
        header_row = [str(c).strip() for c in lines[0]]
        data_rows = [[c for c in line] for line in lines[1:] if any(c.strip() for c in line)]
        if not any("rank" in (c or "").lower() or "position" in (c or "").lower() or "name" in (c or "").lower() for c in header_row):
            return {}
        # Build same structures and run column detection + assignment
        col_name = _header_col_index(header_row, "name", "player", "playername")
        col_rank = _header_col_index(header_row, "rank", "position", "pos")
        col_country = _header_col_index(header_row, "country", "nation")
        col_license = _header_col_index(header_row, "license", "wpa license", "license number")
        col_stops = _header_col_index(header_row, "stops", "stops played", "tournaments")
        if col_name is None:
            col_name = 1 if col_rank == 0 else 0
        fixed = {col_rank, col_name, col_country, col_license, col_stops}
        fixed.discard(None)
        data_cols = []
        for j, raw_h in enumerate(header_row):
            if j in fixed or not (raw_h or "").strip():
                continue
            h = (raw_h or "").strip().lower()
            if h in ("", "rank", "position", "name", "player", "country", "license", "stops"):
                continue
            data_cols.append((j, (raw_h or "").strip()))
        if not data_cols:
            return {}
        main_system = import_context if import_context in ("WPA_Men", "WPA_Women") else "WPA_Men"
        assigned = {}
        for j, raw_h in data_cols:
            system = _header_to_ranking_system(raw_h, import_context)
            if system and system not in assigned:
                assigned[system] = j
            elif system is None and main_system not in assigned:
                assigned[main_system] = j
        result = {}
        for system, col_idx in assigned.items():
            if col_idx is None:
                continue
            rows_for_system = []
            for r, data_row in enumerate(data_rows):
                name = (data_row[col_name] or "").strip() if col_name is not None and col_name < len(data_row) else ""
                if not name:
                    continue
                try:
                    points = float(str(data_row[col_idx] or "0").replace(",", "").replace("$", ""))
                except (ValueError, TypeError):
                    points = 0.0
                rank_val = r + 1
                if col_rank is not None and col_rank < len(data_row):
                    try:
                        rank_val = int(float(str(data_row[col_rank] or "0").replace(",", "")))
                    except (ValueError, TypeError) as e:
                        logger.debug("Could not parse CSV rank value '%s': %s", data_row[col_rank], e)
                country = None
                if col_country is not None and col_country < len(data_row) and data_row[col_country]:
                    country = str(data_row[col_country]).strip()
                license_number = None
                if col_license is not None and col_license < len(data_row) and data_row[col_license]:
                    license_number = str(data_row[col_license]).strip()
                stops_played = None
                if col_stops is not None and col_stops < len(data_row) and data_row[col_stops] is not None:
                    try:
                        stops_played = int(float(str(data_row[col_stops]).replace(",", "")))
                    except (ValueError, TypeError) as e:
                        logger.debug("Could not parse CSV multi-column stops '%s': %s", data_row[col_stops], e)
                rows_for_system.append(
                    _normalize_row(rank_val, name, points, country, license_number=license_number, stops_played=stops_played)
                )
            if rows_for_system:
                rows_for_system.sort(key=lambda x: (-float(x["points"]), x["name"]))
                for i, row in enumerate(rows_for_system):
                    row["rank"] = i + 1
                result[system] = rows_for_system
        return result
    return {}


def parse_xml(content: bytes) -> List[Dict[str, Any]]:
    """Parse XML: look for elements with rank/position, name, points, country (any nesting)."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []
    rows = []
    # Find row-like elements (item, row, player, result, etc.)
    for elem in root.iter():
        tag = (elem.tag or "").split("}")[-1].lower()
        if tag in ("row", "item", "player", "result", "ranking", "record"):
            row = {}
            for child in elem.iter():
                ctag = (child.tag or "").split("}")[-1].lower()
                text = (child.text or "").strip()
                if ctag in ("rank", "position", "pos"):
                    try:
                        row["rank"] = int(float(text))
                    except (ValueError, TypeError) as e:
                        logger.debug("Could not parse XML rank '%s': %s", text, e)
                elif ctag in ("name", "playername", "player"):
                    row["name"] = text
                elif ctag in ("points", "pts", "rpoints", "award"):
                    try:
                        row["points"] = float(text.replace(",", "").replace("$", ""))
                    except (ValueError, TypeError) as e:
                        logger.debug("Could not parse XML points '%s': %s", text, e)
                elif ctag in ("country", "nation", "countrycode"):
                    row["country"] = text
            if row.get("name") and "rank" in row:
                rows.append(_normalize_row(row.get("rank", len(rows) + 1), row.get("name", ""), row.get("points", 0), row.get("country")))
    # If no row elements, try flat list of name/rank/points
    if not rows and len(root) > 0:
        return parse_text_to_rows(ET.tostring(root, method="text", encoding="unicode"))
    return rows


def parse_file(content: bytes, filename: str) -> List[Dict[str, Any]]:
    """
    Parse uploaded file by extension. Returns list of {rank, name, points, country}.
    """
    ext = (filename or "").split(".")[-1].lower() if "." in (filename or "") else ""
    if ext == "pdf":
        return parse_pdf(content)
    if ext == "docx":
        return parse_docx(content)
    if ext == "xlsx":
        return parse_xlsx(content)
    if ext == "xml":
        return parse_xml(content)
    if ext in ("csv", "txt"):
        try:
            text = content.decode("utf-8", errors="replace")
        except Exception:
            text = content.decode("latin-1", errors="replace")
        return parse_text_to_rows(text)
    # Default: try as text
    try:
        text = content.decode("utf-8", errors="replace")
    except Exception:
        text = content.decode("latin-1", errors="replace")
    return parse_text_to_rows(text)
