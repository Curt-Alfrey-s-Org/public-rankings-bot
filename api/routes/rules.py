"""
WPA Rules API: list and serve official WPA rule PDFs from docs/wpa-rules.
"""

import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from project_root import PROJECT_ROOT

router = APIRouter(prefix="/api/rules", tags=["rules"])
RULES_DIR = PROJECT_ROOT / "docs" / "wpa-rules"

# Ordered list of (filename, display title) for the WPA rules page.
# Canonical WPA-hosted Rules Of Play URL when refreshing bundles: docs/wpa-rules/README.md
WPA_RULES_LIST = [
    ("2026.01.02-WPA-Rules.pdf", "Rules Of Play"),
    ("2025.09.15-WPA-Regs-NP.pdf", "Rule Regulations"),
    ("2022-WPA-Sports-Regulations-v2-1.pdf", "Sports Regulations"),
    ("2025.02.12-WPA-Sanctioning-Regulations.pdf", "Sanctioning Regulations"),
    ("RECOMMENDED-EQUIPMENT-SPECIFICATIONS.pdf", "Equipment Specification"),
    ("2025.07.19-Pyramid-Rules.pdf", "Pyramid Rules"),
    ("250816-Rules-of-Heyball.pdf", "Heyball Rules"),
    ("APD-Guidelines-FINAL-WPA-Update-Notes.pdf", "Artistic Guidelines"),
    ("International_8_Ball_Rules_Feb2021.pdf", "IEPF Int'l Rules"),
]


@router.get("", response_model=list[dict])
def list_rules():
    """Return list of WPA rule PDFs with filename and title."""
    return [{"filename": f, "title": t} for f, t in WPA_RULES_LIST]


@router.get("/files/{filename:path}")
async def serve_rule_file(filename: str):
    """Serve a single WPA rule PDF by filename."""
    if ".." in filename or "/" in filename.strip("/"):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = (RULES_DIR / filename.strip("/")).resolve()
    if not path.is_file() or not str(path).startswith(str(RULES_DIR.resolve())):
        raise HTTPException(status_code=404, detail="Not found")
    media_type, _ = mimetypes.guess_type(str(path))
    if not media_type:
        media_type = "application/pdf"
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Content-Disposition": "inline; filename=\"" + path.name + "\""},
    )
