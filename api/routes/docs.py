"""
Serve documentation files (e.g. NOTIFICATIONS_EMAIL.md) for in-app links.
"""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from project_root import PROJECT_ROOT

router = APIRouter()


@router.get("/notifications-email", response_class=PlainTextResponse)
async def get_notifications_email_doc():
    """Return the email notifications documentation as plain text (markdown)."""
    path = PROJECT_ROOT / "docs" / "NOTIFICATIONS_EMAIL.md"
    if not path.exists():
        return PlainTextResponse(content="# Not found\n\nDoc not found.", status_code=404)
    content = path.read_text(encoding="utf-8", errors="replace")
    return PlainTextResponse(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": "inline; filename=NOTIFICATIONS_EMAIL.md"},
    )


@router.get("/director-import", response_class=PlainTextResponse)
async def get_director_import_doc():
    """Return the Director import documentation (manual entry and file upload) as plain text (markdown)."""
    path = PROJECT_ROOT / "docs" / "DIRECTOR_IMPORT.md"
    if not path.exists():
        return PlainTextResponse(content="# Not found\n\nDoc not found.", status_code=404)
    content = path.read_text(encoding="utf-8", errors="replace")
    return PlainTextResponse(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": "inline; filename=DIRECTOR_IMPORT.md"},
    )
