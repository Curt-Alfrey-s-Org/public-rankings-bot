"""
Covert Ops API Routes
Recon: player inputs opponent ("victim") name; AI analyzes opponent's most current
YouTube match video and exposes weaknesses. "The battle is won before it's even begun."
"""

import logging
import os
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import require_admin_or_super_admin
from api.services.youtube_search import search_first_match_video

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/covert-ops", tags=["covert-ops"])


class ReconRequest(BaseModel):
    """Recon request: opponent (victim) name."""
    victim_name: str


class ReconResponse(BaseModel):
    """Recon result: weaknesses and video info."""
    victim_name: str
    video_url: Optional[str] = None
    video_title: Optional[str] = None
    weaknesses: list[str]
    summary: Optional[str] = None
    status: str  # 'completed', 'no_video', 'error'


def _parse_weaknesses_from_grok(text: str) -> tuple:
    """Extract bullet/numbered weaknesses and optional summary from Grok response."""
    weaknesses = []
    summary = None
    for line in (text or "").strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(?:\d+[.)]\s*|[-*•]\s*)(.+)", line, re.IGNORECASE)
        if m:
            weaknesses.append(m.group(1).strip())
        elif len(weaknesses) >= 3 and not summary:
            summary = line[:500]
    if not weaknesses and text:
        for s in re.split(r"[\n.;]+", text):
            s = s.strip()
            if 15 < len(s) < 200:
                weaknesses.append(s)
        weaknesses = weaknesses[:6]
    return (weaknesses[:8], summary or (text[:400] if text else None))


@router.post("/recon", response_model=ReconResponse)
async def run_recon(req: ReconRequest, _user: dict = Depends(require_admin_or_super_admin)):
    """
    Run recon on opponent: find their most current YouTube match video and
    analyze it with AI to expose weaknesses in their game. Admin and super_admin only.
    """
    victim = (req.victim_name or "").strip()
    if not victim:
        raise HTTPException(status_code=400, detail="Victim name is required")

    video_url, video_title = search_first_match_video(f"{victim} pool match")
    if not video_url:
        video_url, video_title = search_first_match_video(f"{victim} billiards")

    xai_key = os.getenv("XAI_API_KEY", "").strip()
    weaknesses = []
    summary = None
    status = "completed"

    if not video_url:
        status = "no_video"
        weaknesses = [
            "No recent match video found. Set YOUTUBE_API_KEY and ensure the opponent has public pool/billiards match videos.",
        ]
        summary = "The battle is won before it's even begun. Add a YouTube Data API key to search for opponent match videos."
    elif not xai_key:
        weaknesses = ["YouTube video found but AI analysis is disabled. Set XAI_API_KEY to enable Grok analysis."]
        summary = f"Video: {video_title}. Set XAI_API_KEY for weakness analysis."
    else:
        try:
            from api.services.grok_client import GrokCoachClient
            client = GrokCoachClient(xai_key)
            prompt = f"""You are an elite pool/billiards strategist. We are doing "recon" on an opponent before a match.

Opponent name: {victim}
Match video found: {video_title or 'N/A'}
Video URL: {video_url or 'N/A'}

Based on this opponent and the type of match video (pool/billiards), list 3-5 specific strategic weaknesses or tendencies that a player could exploit when facing someone like this. Focus on: break consistency, safety play, pressure shots, position play, and mental game. Be concise and actionable. Use short bullet points. Then add one sentence summary."""
            reply = await client.chat_text(prompt)
            await client.close()
            weaknesses, summary = _parse_weaknesses_from_grok(reply)
            if not weaknesses:
                weaknesses = [reply[:300] if reply else "No structured weaknesses returned."]
            if not summary:
                summary = "The battle is won before it's even begun."
        except Exception as e:
            logger.exception("Recon Grok failed for victim=%s: %s", victim, e)
            status = "error"
            weaknesses = []
            summary = str(e)

    return ReconResponse(
        victim_name=victim,
        video_url=video_url,
        video_title=video_title,
        weaknesses=weaknesses,
        summary=summary,
        status=status,
    )
