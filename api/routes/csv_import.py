"""
CSV Import Routes for WPBA & WPA Rankings

Allows importing official CSV files instead of web scraping.
"""
import csv
import io
import logging
from datetime import date
from typing import Dict, List, Optional
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import JSONResponse

from api.auth import require_director_or_admin
from api.ranking_scope import director_may_write_ranking_systems
from database import get_database_manager

router = APIRouter(prefix="/api/csv-import", tags=["csv-import"])
logger = logging.getLogger(__name__)


def _ensure_csv_import_allowed(user: dict, ranking_systems: list) -> None:
    ok, msg = director_may_write_ranking_systems(user, ranking_systems)
    if not ok:
        raise HTTPException(status_code=403, detail=msg)


class CSVImportResult:
    def __init__(self):
        self.total_rows = 0
        self.valid_rows = 0
        self.imported_rows = 0
        self.errors = []
        self.duplicates = 0


def validate_csv_headers(headers: List[str], expected_headers: List[str]) -> bool:
    """Validate that CSV has required headers"""
    required = set(h.strip().lower() for h in expected_headers)
    actual = set(h.strip().lower() for h in headers)
    return required.issubset(actual)


def normalize_player_name(name: str) -> str:
    """Normalize player name for consistency"""
    if not name:
        return ""
    return name.strip()


def _parse_points(points_raw: str) -> float:
    """Parse points safely; blank values are treated as 0."""
    if points_raw is None:
        return 0.0
    raw = str(points_raw).strip()
    if raw == "":
        return 0.0
    return float(raw.replace(",", ""))


def _parse_rankings_rows(content: str, expected_headers: List[str], result: CSVImportResult) -> List[Dict]:
    """Validate CSV and convert rows into normalized ranking dicts."""
    reader = csv.DictReader(io.StringIO(content))
    result.total_rows = sum(1 for _ in reader)  # Count rows
    reader = csv.DictReader(io.StringIO(content))  # Reset reader

    if not validate_csv_headers(list(reader.fieldnames or []), expected_headers):
        result.errors.append(f"Missing required headers. Expected: {expected_headers}")
        return []

    parsed_rows: List[Dict] = []
    for row in reader:
        result.valid_rows += 1
        player_name = normalize_player_name(row.get("Player Name", ""))
        rank_raw = str(row.get("Rank", "")).strip()

        if not player_name or not rank_raw:
            result.errors.append(f"Missing player name or rank in row: {row}")
            continue

        try:
            parsed_rows.append({
                "name": player_name,
                "rank": int(rank_raw),
                "points": _parse_points(row.get("Points", "")),
                "country": str(row.get("Country", "")).strip() or None,
                "license_number": str(row.get("License Number", "")).strip() or None,
            })
        except (TypeError, ValueError):
            result.errors.append(f"Invalid numeric value in row: {row}")
            continue
    return parsed_rows


def process_wpba_csv(content: str) -> CSVImportResult:
    """Process WPBA women's rankings CSV"""
    result = CSVImportResult()

    expected_headers = ["Player Name", "Rank", "Points", "Country", "License Number"]
    rankings = _parse_rankings_rows(content, expected_headers, result)
    if not rankings:
        return result

    try:
        result.imported_rows = get_database_manager().save_rankings(
            rankings=rankings,
            system="WPBA_Women",
            snapshot_date=date.today(),
        )
    except Exception as e:
        result.errors.append(f"Database error: {str(e)}")

    return result


def process_wpa_csv(content: str, system_type: str) -> CSVImportResult:
    """Process WPA rankings CSV (Men, Women, Heyball)"""
    result = CSVImportResult()

    expected_headers = ["Player Name", "Rank", "Points", "Country", "License Number"]
    rankings = _parse_rankings_rows(content, expected_headers, result)
    if not rankings:
        return result

    # Map system type to internal ranking_system code
    system_map = {
        "men": "WPA_Men",
        "women": "WPA_Women",
        "heyball_men": "WPA_Heyball_Men",
        "heyball_women": "WPA_Heyball_Women"
    }

    db_system = system_map.get(system_type.lower())
    if not db_system:
        result.errors.append(f"Invalid system type: {system_type}")
        return result

    try:
        result.imported_rows = get_database_manager().save_rankings(
            rankings=rankings,
            system=db_system,
            snapshot_date=date.today(),
        )
    except Exception as e:
        result.errors.append(f"Database error: {str(e)}")

    return result


@router.post("/wpba")
async def import_wpba_csv(
    file: UploadFile = File(...),
    user: dict = Depends(require_director_or_admin),
):
    """
    Import WPBA women's rankings from CSV file.

    Expected CSV format:
    Player Name,Rank,Points,Country,License Number
    Kristina Tkach,1,132750,AIN,EPBF - 046
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV file")

    _ensure_csv_import_allowed(user, ["WPBA_Women"])

    content = await file.read()
    content_str = content.decode('utf-8')

    result = process_wpba_csv(content_str)

    response = {
        "message": f"WPBA CSV import completed",
        "statistics": {
            "total_rows": result.total_rows,
            "valid_rows": result.valid_rows,
            "imported_rows": result.imported_rows,
            "errors_count": len(result.errors)
        },
        "errors": result.errors[:10]  # Show first 10 errors
    }

    if result.errors:
        response["warnings"] = f"{len(result.errors)} rows had errors"

    logger.info(f"WPBA CSV import: {result.imported_rows} rows imported, {len(result.errors)} errors")
    return JSONResponse(content=response)


@router.post("/wpa/{system_type}")
async def import_wpa_csv(
    system_type: str,
    file: UploadFile = File(...),
    user: dict = Depends(require_director_or_admin),
):
    """
    Import WPA rankings from CSV file.

    system_type: men, women, heyball_men, heyball_women

    Expected CSV format:
    Player Name,Rank,Points,Country,License Number
    """
    valid_types = ["men", "women", "heyball_men", "heyball_women"]
    if system_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"system_type must be one of: {valid_types}")

    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV file")

    system_map = {
        "men": "WPA_Men",
        "women": "WPA_Women",
        "heyball_men": "WPA_Heyball_Men",
        "heyball_women": "WPA_Heyball_Women",
    }
    db_system = system_map.get(system_type.lower())
    if not db_system:
        raise HTTPException(status_code=400, detail=f"system_type must be one of: {list(system_map.keys())}")
    _ensure_csv_import_allowed(user, [db_system])

    content = await file.read()
    content_str = content.decode('utf-8')

    result = process_wpa_csv(content_str, system_type)

    response = {
        "message": f"WPA {system_type} CSV import completed",
        "statistics": {
            "total_rows": result.total_rows,
            "valid_rows": result.valid_rows,
            "imported_rows": result.imported_rows,
            "errors_count": len(result.errors)
        },
        "errors": result.errors[:10]
    }

    if result.errors:
        response["warnings"] = f"{len(result.errors)} rows had errors"

    logger.info(f"WPA {system_type} CSV import: {result.imported_rows} rows imported, {len(result.errors)} errors")
    return JSONResponse(content=response)


@router.get("/status")
async def get_csv_import_status(_user: dict = Depends(require_director_or_admin)):
    """Get status of recent CSV imports"""
    # Import history tracking not yet implemented
    return {
        "message": "CSV import endpoints are ready",
        "supported_formats": {
            "WPBA": ["Player Name", "Rank", "Points", "Country", "License Number"],
            "WPA": ["Player Name", "Rank", "Points", "Country", "License Number"]
        },
        "endpoints": [
            "POST /api/csv-import/wpba",
            "POST /api/csv-import/wpa/{men|women|heyball_men|heyball_women}"
        ]
    }