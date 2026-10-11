"""
AI Coach API Routes
6 endpoints for video analysis, history, usage, and referrals
Connects GrokCoachClient + FrameStorage + Database
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import base64
import logging
import os
import uuid

from database import get_db
from api.models.ai_coach import (
    AICoachAnalysis, AICoachUsage, PromoCode, Referral,
)
from api.config.admin_config import get_effective_tier_config
from api.models.user import User
from api.auth import get_current_user_object as get_current_user
from api.rate_limiter import check_ai_coach_limit
from api.services.grok_client import GrokCoachClient
from api.services.frame_storage import OracleFrameStorage
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai-coach", tags=["ai-coach"])

# Service instances
grok_client = None
frame_storage = None


def get_frame_storage():
    """Get frame storage with optional env-based root"""
    global frame_storage
    if frame_storage is None:
        import os
        root = os.getenv("FRAME_STORAGE_ROOT")
        frame_storage = OracleFrameStorage(storage_root=root) if root else OracleFrameStorage()
    return frame_storage


async def get_grok_client():
    """Get or create Grok client"""
    global grok_client
    if grok_client is None:
        import os
        api_key = os.getenv("XAI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="Grok API key not configured")
        grok_client = GrokCoachClient(api_key)
    return grok_client


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class AnalyzeRequest(BaseModel):
    """Submit video for analysis"""
    bot_type: str  # 'rankings', 'trading', 'contracts', 'credit'
    video_source: str = "youtube"  # 'youtube' or 'upload'
    video_url: Optional[str] = None  # For YouTube
    frames_base64: Optional[List[str]] = None  # For file upload
    player_name: Optional[str] = None
    opponent_name: Optional[str] = None
    game_format: Optional[str] = None  # Optional; AI can infer or ask
    transcript: Optional[str] = None
    promo_code: Optional[str] = None
    player_hair_color: Optional[str] = None
    player_shirt_color: Optional[str] = None
    opponent_hair_color: Optional[str] = None
    opponent_shirt_color: Optional[str] = None
    text_question: Optional[str] = None  # Pure text coaching (no frames needed)


class AnalyzeResponse(BaseModel):
    """Response when analysis is submitted"""
    analysis_id: str
    status: str  # 'processing'
    estimated_time_seconds: int
    message: str


class AnalysisStatus(BaseModel):
    """Current status of an analysis"""
    analysis_id: str
    status: str  # 'processing', 'completed', 'failed'
    progress_percent: int
    estimated_remaining_seconds: int
    results: Optional[dict] = None
    error_message: Optional[str] = None


class PollResponse(BaseModel):
    """Poll endpoint response - matches expected format"""
    analysis_id: str
    status: str  # 'pending', 'processing', 'completed', 'failed'
    progress: int  # 0-100
    result: Optional[dict] = None  # Analysis JSON when completed
    error_message: Optional[str] = None
    estimated_remaining_seconds: Optional[int] = None


class HistoryItem(BaseModel):
    """Item in analysis history"""
    analysis_id: str
    created_at: str
    title: str
    status: str
    overall_score: Optional[float]
    summary: Optional[str]


class HistoryResponse(BaseModel):
    """List of past analyses"""
    analyses: List[HistoryItem]
    total: int
    limit: int
    offset: int


class UsageResponse(BaseModel):
    """Current usage against tier limits"""
    tier: str
    analyses_used: int
    analyses_limit: Optional[int]
    analyses_remaining: int
    lifetime_analyses: int
    lifetime_limit: Optional[int]
    max_video_duration_seconds: int
    trial_expires_at: Optional[str] = None
    discount_percent: int = 0
    discount_expires_at: Optional[str] = None
    month_reset_date: str


class CouponRequest(BaseModel):
    """Redeem a coupon code"""
    code: str


class CouponResponse(BaseModel):
    """Result of coupon redemption"""
    success: bool
    message: str
    tier_granted: Optional[str] = None
    duration_days: Optional[int] = None


class ReferralResponse(BaseModel):
    """Influencer referral information"""
    code: str
    total_referrals: int
    active_conversions: int
    revenue_generated: float
    bonus_earned: float
    upcoming_bonuses: dict


class PatchAnalysisRequest(BaseModel):
    """Update user-editable fields of an assessment"""
    summary_text: Optional[str] = None


class ProgressionRequest(BaseModel):
    """Submit new video for progression review vs a previous assessment"""
    previous_analysis_id: str
    bot_type: str = "rankings"
    frames_base64: List[str]
    player_name: Optional[str] = None
    opponent_name: Optional[str] = None
    game_format: Optional[str] = None


# Frame validation constants
MAX_FRAMES = 100
MAX_FRAME_SIZE_BYTES = 500 * 1024  # 500KB per frame (before base64)
MAX_TOTAL_SIZE_MB = 50


class TextCoachRequest(BaseModel):
    """Text-only coaching question (routed to Ollama, no vision needed)"""
    question: str
    player_name: Optional[str] = None
    game_format: Optional[str] = None


class TextCoachResponse(BaseModel):
    """Response from text-only coaching"""
    answer: str
    model: str
    duration_seconds: float
    source: str = "ollama"


def _filter_results_pointers_only(data: dict) -> dict:
    """For non-admin users: expose only pointers/tips, not weaknesses."""
    if not isinstance(data, dict):
        return data
    out = dict(data)
    if "weaknesses" in out:
        out["weaknesses"] = []
        out["_message"] = "Full opponent analysis (weaknesses) is available for admin tier."
    for key in list(out):
        if "weakness" in key.lower() and key != "_message":
            out[key] = [] if isinstance(out[key], list) else None
    return out


# ============================================================================
# ENDPOINT 0: POST /api/ai-coach/ask  (text-only, Ollama-powered)
# ============================================================================

_TEXT_COACHING_SYSTEM = """You are an elite pool/billiards coach with 30+ years professional experience.
You hold WPBA and BCA credentials. Answer the player's question with specific,
actionable advice. Be conversational but professional. If the question is about
rules, cite the official WPA/BCA rulebook. If about technique, give measurable
drills. If about strategy, explain the decision framework."""


@router.post("/ask", response_model=TextCoachResponse)
async def text_coaching(
    request: TextCoachRequest,
    user: User = Depends(get_current_user),
):
    """
    Text-only coaching question. Routed to local Ollama (free, fast).
    Falls back to Grok if Ollama is unavailable and XAI_API_KEY is set.
    """
    from api.services.ollama_client import get_ollama_client

    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    player_ctx = ""
    if request.player_name:
        player_ctx += f"\nPlayer: {request.player_name}"
    if request.game_format:
        player_ctx += f"\nGame format: {request.game_format}"

    user_msg = request.question.strip()
    if player_ctx:
        user_msg = f"{player_ctx}\n\nQuestion: {user_msg}"

    ollama = get_ollama_client()
    if ollama is not None:
        resp = await ollama.chat(
            messages=[
                {"role": "system", "content": _TEXT_COACHING_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            model=ollama.model_chat,
            temperature=0.3,
            feature="text_coaching",
            log_metadata={"trust_zone": "app_authenticated"},
        )
        if not resp.error:
            return TextCoachResponse(
                answer=resp.content,
                model=resp.model,
                duration_seconds=round(resp.duration_seconds, 2),
                source="ollama",
            )
        logger.warning("Ollama text coaching failed, trying Grok: %s", resp.error)

    # Grok fallback
    try:
        client = await get_grok_client()
        answer = await client.chat_text(f"{_TEXT_COACHING_SYSTEM}\n\n{user_msg}")
        return TextCoachResponse(
            answer=answer,
            model="grok-4",
            duration_seconds=0.0,
            source="grok",
        )
    except Exception as e:
        logger.error("Both Ollama and Grok unavailable for text coaching: %s", e)
        raise HTTPException(
            status_code=503,
            detail="AI coaching is temporarily unavailable. Please try again later.",
        )


# ============================================================================
# ENDPOINT 1: POST /api/ai-coach/analyze
# ============================================================================

@router.post("/analyze", response_model=AnalyzeResponse)
async def submit_analysis(
    request: AnalyzeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit video for AI coaching analysis.
    Validates frames, saves to storage, queues Celery task.
    Returns analysis_id for polling.
    """
    logger.info(f"Analysis submission from user {user.id}")

    # Text-only shortcut: if text_question is provided with no frames, use /ask endpoint logic
    if request.text_question and not request.frames_base64:
        text_req = TextCoachRequest(
            question=request.text_question,
            player_name=request.player_name,
            game_format=request.game_format,
        )
        result = await text_coaching(text_req, user=user)
        analysis_id = str(uuid.uuid4())
        return AnalyzeResponse(
            analysis_id=analysis_id,
            status="completed",
            estimated_time_seconds=0,
            message=result.answer,
        )

    # Ensure Grok is configured so the queued task can run
    if not os.getenv("XAI_API_KEY", "").strip():
        raise HTTPException(
            status_code=503,
            detail="AI Coach is not configured (XAI_API_KEY missing). Contact admin.",
        )

    # Throttle non-admin users to prevent overuse (admin+ is never throttled)
    if getattr(user, "role", None) not in ("admin", "super_admin"):
        allowed, retry_after = check_ai_coach_limit(str(user.id))
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"AI Coach rate limit exceeded. Please wait {int(retry_after)} seconds before submitting another analysis.",
            )

    # Validate frames (required for upload)
    frames = request.frames_base64 or []
    if not frames:
        raise HTTPException(
            status_code=400,
            detail="frames_base64 required. Extract frames client-side (e.g. ffmpeg.wasm) and send as array."
        )
    if len(frames) > MAX_FRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_FRAMES} frames allowed. You sent {len(frames)}."
        )
    total_bytes = 0
    for i, b64 in enumerate(frames):
        decoded = base64.b64decode(b64, validate=True)
        if len(decoded) > MAX_FRAME_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"Frame {i} exceeds {MAX_FRAME_SIZE_BYTES // 1024}KB limit."
            )
        total_bytes += len(decoded)
    total_mb = total_bytes / (1024 * 1024)
    if total_mb > MAX_TOTAL_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"Total frame size {total_mb:.1f}MB exceeds {MAX_TOTAL_SIZE_MB}MB limit."
        )

    # Get or create usage tracking (super_admin gets PRO/unlimited)
    usage = db.query(AICoachUsage).filter_by(user_id=user.id).first()
    if not usage:
        tier = "PRO" if getattr(user, "role", None) == "super_admin" else "FREEBIE"
        tier_config = get_effective_tier_config().get(tier, {})
        usage = AICoachUsage(
            user_id=user.id,
            tier=tier,
            analyses_limit=tier_config.get("monthly_limit") or 999999,
            lifetime_limit=tier_config.get("lifetime_limit")
        )
        db.add(usage)
        db.commit()

    # super_admin: always allow (unlimited)
    if getattr(user, "role", None) != "super_admin":
        usage.reset_if_new_month()
        if not usage.is_within_limits():
            raise HTTPException(
                status_code=429,
                detail=f"Analysis limit reached for {usage.tier} tier. Please upgrade."
            )

    # Create analysis ID and save frames first
    analysis_id = str(uuid.uuid4())
    storage = get_frame_storage()
    storage_result = await storage.save_frames(
        analysis_id=analysis_id,
        user_id=user.id,
        frames_base64=frames,
        bot_type=request.bot_type,
        metadata={
            "player_name": request.player_name,
            "opponent_name": request.opponent_name,
            "game_format": request.game_format,
            "player_hair_color": request.player_hair_color,
            "player_shirt_color": request.player_shirt_color,
            "opponent_hair_color": request.opponent_hair_color,
            "opponent_shirt_color": request.opponent_shirt_color,
        }
    )
    storage_path = storage_result["storage_path"]
    frame_count = storage_result["frame_count"]
    frame_size_mb = storage_result["total_size_mb"]

    # Create analysis record (status=pending)
    analysis = AICoachAnalysis(
        id=analysis_id,
        user_id=user.id,
        bot_type=request.bot_type,
        video_source=request.video_source,
        video_url=request.video_url,
        status="pending",
        player_name=request.player_name,
        opponent_name=request.opponent_name,
        game_format=request.game_format,
        frame_count=frame_count,
        frame_size_mb=frame_size_mb,
        frame_storage_path=storage_path,
    )
    db.add(analysis)
    db.commit()

    # Queue Celery task
    try:
        from api.services.celery_worker import analyze_video_task
        analyze_video_task.delay(analysis_id, user.id)
    except Exception as e:
        logger.error(f"Failed to queue Celery task: {e}")
        analysis.status = "failed"
        analysis.error_message = "Failed to queue analysis"
        db.commit()
        raise HTTPException(status_code=503, detail="Analysis queue unavailable. Try again later.")

    logger.info(f"Analysis {analysis_id} queued, status=pending")

    return AnalyzeResponse(
        analysis_id=analysis_id,
        status="pending",
        estimated_time_seconds=180,
        message="Analysis queued. Poll /api/ai-coach/analyses/{id}/poll for status."
    )


# ============================================================================
# ENDPOINT 2: GET /api/ai-coach/analyze/{analysis_id}
# ============================================================================

@router.get("/analyze/{analysis_id}", response_model=AnalysisStatus)
async def get_analysis_status(
    analysis_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Poll for analysis completion
    Returns status, progress, and results when done
    """
    
    # Get analysis record
    analysis = db.query(AICoachAnalysis).filter_by(
        id=analysis_id,
        user_id=user.id
    ).first()
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    logger.info(f"Status check for analysis {analysis_id}: {analysis.status}")
    
    # Calculate progress
    progress_percent = 0
    estimated_remaining = 0
    
    if analysis.status == "pending":
        progress_percent = 10
        estimated_remaining = 200
    elif analysis.status == "processing":
        # Assume 50% through (2.5 min avg)
        if analysis.started_processing_at:
            elapsed = (datetime.utcnow() - analysis.started_processing_at).total_seconds()
            progress_percent = min(90, int((elapsed / 150) * 100))
            estimated_remaining = max(0, 150 - int(elapsed))
        else:
            progress_percent = 50
            estimated_remaining = 120
    elif analysis.status == "completed":
        progress_percent = 100
        estimated_remaining = 0
    elif analysis.status == "failed":
        progress_percent = 0
        estimated_remaining = 0

    # Non-admin: only return pointers/tips, not weaknesses (paid/full analysis for admin+)
    results = analysis.analysis_json if analysis.analysis_json else None
    if results and getattr(user, "role", None) not in ("admin", "super_admin"):
        results = _filter_results_pointers_only(results)

    return AnalysisStatus(
        analysis_id=analysis_id,
        status=analysis.status,
        progress_percent=progress_percent,
        estimated_remaining_seconds=estimated_remaining,
        results=results,
        error_message=analysis.error_message
    )


# ============================================================================
# ENDPOINT 2b: GET /api/ai-coach/analyses/{analysis_id}/poll (expected format)
# ============================================================================

@router.get("/analyses/{analysis_id}/poll", response_model=PollResponse)
async def poll_analysis(
    analysis_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Poll for analysis completion.
    Returns: {status, progress, result (when completed)}
    """
    status_data = await get_analysis_status(analysis_id, user, db)
    return PollResponse(
        analysis_id=status_data.analysis_id,
        status=status_data.status,
        progress=status_data.progress_percent,
        result=status_data.results,
        error_message=status_data.error_message,
        estimated_remaining_seconds=status_data.estimated_remaining_seconds,
    )


# ============================================================================
# ENDPOINT 3: GET /api/ai-coach/history
# ============================================================================

@router.get("/history", response_model=HistoryResponse)
async def get_user_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's past analyses (most recent first)
    """
    
    # Get total count
    total = db.query(AICoachAnalysis).filter_by(
        user_id=user.id
    ).count()
    
    # Get paginated results
    analyses = db.query(AICoachAnalysis).filter_by(
        user_id=user.id
    ).order_by(AICoachAnalysis.created_at.desc()).offset(offset).limit(limit).all()
    
    history_items = [
        HistoryItem(
            analysis_id=a.id,
            created_at=a.created_at.isoformat(),
            title=f"{a.bot_type.title()} Analysis",
            status=a.status,
            overall_score=a.overall_score,
            summary=a.summary_text
        )
        for a in analyses
    ]
    
    return HistoryResponse(
        analyses=history_items,
        total=total,
        limit=limit,
        offset=offset
    )


# ============================================================================
# ENDPOINT 3b: PATCH /api/ai-coach/analyses/{analysis_id}
# ============================================================================

@router.patch("/analyses/{analysis_id}")
async def update_analysis(
    analysis_id: str,
    body: PatchAnalysisRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update user-editable fields of an assessment (e.g. summary/notes).
    Only the owner can update.
    """
    analysis = db.query(AICoachAnalysis).filter_by(
        id=analysis_id,
        user_id=user.id
    ).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if body.summary_text is not None:
        analysis.summary_text = body.summary_text[:2000] if body.summary_text else None
    db.commit()
    return {"success": True, "analysis_id": analysis_id, "message": "Assessment updated"}


# ============================================================================
# ENDPOINT 3c: DELETE /api/ai-coach/analyses/{analysis_id}
# ============================================================================

@router.delete("/analyses/{analysis_id}")
async def delete_analysis(
    analysis_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete an assessment. Only the owner can delete.
    Frames are already discarded after analysis; this removes the record.
    """
    analysis = db.query(AICoachAnalysis).filter_by(
        id=analysis_id,
        user_id=user.id
    ).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    db.delete(analysis)
    db.commit()
    return {"success": True, "message": "Assessment deleted"}


# ============================================================================
# ENDPOINT 3d: POST /api/ai-coach/progression
# ============================================================================

@router.post("/progression", response_model=AnalyzeResponse)
async def submit_progression(
    request: ProgressionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit new video for progression review. Compares with a previous assessment.
    Same throttling and usage limits as analyze; returns analysis_id for polling.
    """
    logger.info(f"Progression submission from user {user.id} (previous={request.previous_analysis_id})")

    if not os.getenv("XAI_API_KEY", "").strip():
        raise HTTPException(
            status_code=503,
            detail="AI Coach is not configured (XAI_API_KEY missing). Contact admin.",
        )

    if getattr(user, "role", None) not in ("admin", "super_admin"):
        allowed, retry_after = check_ai_coach_limit(str(user.id))
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"AI Coach rate limit exceeded. Please wait {int(retry_after)} seconds before submitting another analysis.",
            )

    previous = db.query(AICoachAnalysis).filter_by(
        id=request.previous_analysis_id,
        user_id=user.id
    ).first()
    if not previous:
        raise HTTPException(status_code=404, detail="Previous analysis not found")
    if previous.status != "completed":
        raise HTTPException(
            status_code=400,
            detail="Previous analysis must be completed to use progression review.",
        )

    frames = request.frames_base64 or []
    if not frames:
        raise HTTPException(
            status_code=400,
            detail="frames_base64 required for progression review.",
        )
    if len(frames) > MAX_FRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_FRAMES} frames allowed. You sent {len(frames)}.",
        )
    total_bytes = 0
    for i, b64 in enumerate(frames):
        decoded = base64.b64decode(b64, validate=True)
        if len(decoded) > MAX_FRAME_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"Frame {i} exceeds {MAX_FRAME_SIZE_BYTES // 1024}KB limit.",
            )
        total_bytes += len(decoded)
    total_mb = total_bytes / (1024 * 1024)
    if total_mb > MAX_TOTAL_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"Total frame size {total_mb:.1f}MB exceeds {MAX_TOTAL_SIZE_MB}MB limit.",
        )

    usage = db.query(AICoachUsage).filter_by(user_id=user.id).first()
    if not usage:
        tier = "PRO" if getattr(user, "role", None) == "super_admin" else "FREEBIE"
        tier_config = get_effective_tier_config().get(tier, {})
        usage = AICoachUsage(
            user_id=user.id,
            tier=tier,
            analyses_limit=tier_config.get("monthly_limit") or 999999,
            lifetime_limit=tier_config.get("lifetime_limit"),
        )
        db.add(usage)
        db.commit()
    if getattr(user, "role", None) != "super_admin":
        usage.reset_if_new_month()
        if not usage.is_within_limits():
            raise HTTPException(
                status_code=429,
                detail=f"Analysis limit reached for {usage.tier} tier. Please upgrade.",
            )

    analysis_id = str(uuid.uuid4())
    storage = get_frame_storage()
    storage_result = await storage.save_frames(
        analysis_id=analysis_id,
        user_id=user.id,
        frames_base64=frames,
        bot_type=request.bot_type,
        metadata={
            "player_name": request.player_name,
            "opponent_name": request.opponent_name,
            "game_format": request.game_format,
        },
    )
    storage_path = storage_result["storage_path"]
    frame_count = storage_result["frame_count"]
    frame_size_mb = storage_result["total_size_mb"]

    analysis = AICoachAnalysis(
        id=analysis_id,
        user_id=user.id,
        bot_type=request.bot_type,
        video_source="upload",
        video_url=None,
        status="pending",
        player_name=request.player_name,
        opponent_name=request.opponent_name,
        game_format=request.game_format,
        frame_count=frame_count,
        frame_size_mb=frame_size_mb,
        frame_storage_path=storage_path,
        progression_from_id=request.previous_analysis_id,
    )
    db.add(analysis)
    db.commit()

    try:
        from api.services.celery_worker import progression_video_task
        progression_video_task.delay(analysis_id, user.id)
    except Exception as e:
        logger.error(f"Failed to queue progression task: {e}")
        analysis.status = "failed"
        analysis.error_message = "Failed to queue progression"
        db.commit()
        raise HTTPException(status_code=503, detail="Progression queue unavailable. Try again later.")

    return AnalyzeResponse(
        analysis_id=analysis_id,
        status="pending",
        estimated_time_seconds=180,
        message="Progression review queued. Poll /api/ai-coach/analyses/{id}/poll for status.",
    )
    db.commit()
    return {"success": True, "message": "Assessment deleted"}


# ============================================================================
# ENDPOINT 4: GET /api/ai-coach/usage
# ============================================================================

@router.get("/usage", response_model=UsageResponse)
async def get_usage_meter(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current tier and usage metrics
    """
    
    # Get usage record (super_admin gets PRO/unlimited)
    usage = db.query(AICoachUsage).filter_by(user_id=user.id).first()
    is_super_admin = getattr(user, "role", None) == "super_admin"

    if not usage:
        tier = "PRO" if is_super_admin else "FREEBIE"
        tier_config = get_effective_tier_config().get(tier, {})
        usage = AICoachUsage(
            user_id=user.id,
            tier=tier,
            analyses_limit=tier_config.get("monthly_limit") or 999999,
            lifetime_limit=tier_config.get("lifetime_limit")
        )
        db.add(usage)
        db.commit()
    elif is_super_admin and usage.tier == "FREEBIE":
        # Upgrade existing super_admin from FREEBIE to PRO
        usage.tier = "PRO"
        usage.analyses_limit = 999999
        usage.lifetime_limit = None
        db.commit()

    if not is_super_admin:
        usage.reset_if_new_month()

    remaining = 999999 if is_super_admin else usage.uses_remaining()
    
    return UsageResponse(
        tier=usage.tier,
        analyses_used=usage.analyses_this_month,
        analyses_limit=usage.analyses_limit,
        analyses_remaining=remaining,
        lifetime_analyses=usage.lifetime_analyses,
        lifetime_limit=usage.lifetime_limit,
        max_video_duration_seconds=usage.max_video_duration_seconds,
        trial_expires_at=usage.trial_expires_at.isoformat() if usage.trial_expires_at else None,
        discount_percent=usage.discount_percent,
        discount_expires_at=usage.discount_expires_at.isoformat() if usage.discount_expires_at else None,
        month_reset_date=usage.month_reset_date.isoformat()
    )


# ============================================================================
# ENDPOINT 5: POST /api/coupon/redeem
# ============================================================================

@router.post("/coupon/redeem", response_model=CouponResponse)
async def redeem_coupon(
    request: CouponRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Apply promo code to user account
    Grants trial tier + optional discount
    """
    
    # Find promo code
    promo = db.query(PromoCode).filter_by(
        code=request.code.upper(),
        is_active=True
    ).first()
    
    if not promo:
        raise HTTPException(status_code=404, detail="Invalid or expired promo code")
    
    if not promo.is_valid():
        raise HTTPException(status_code=410, detail="Promo code has reached usage limit or expired")
    
    # Get user's usage record
    usage = db.query(AICoachUsage).filter_by(user_id=user.id).first()
    if not usage:
        usage = AICoachUsage(
            user_id=user.id,
            tier="FREEBIE",
            analyses_limit=0,
            lifetime_limit=3
        )
        db.add(usage)
    
    # Apply code
    usage.tier = promo.trial_tier
    usage.trial_expires_at = datetime.utcnow() + timedelta(days=promo.trial_duration_days)
    
    if promo.upgrade_discount_percent:
        usage.discount_percent = promo.upgrade_discount_percent
        usage.discount_expires_at = datetime.utcnow() + timedelta(
            days=promo.upgrade_duration_months * 30
        )
    
    # Update tier limits
    tier_config = get_effective_tier_config().get(promo.trial_tier, {})
    usage.analyses_limit = tier_config.get("monthly_limit") or 999999
    usage.lifetime_limit = tier_config.get("lifetime_limit")
    usage.max_video_duration_seconds = tier_config.get("max_video_duration", 30)
    
    db.commit()
    
    # Track usage
    promo.current_uses += 1
    
    # Create referral record
    referral = Referral(
        promo_code_id=promo.id,
        referred_user_id=user.id,
        referral_date=datetime.utcnow(),
        is_active=True
    )
    db.add(referral)
    db.commit()
    
    logger.info(f"Promo code {promo.code} redeemed by user {user.id}")
    
    return CouponResponse(
        success=True,
        message=f"Welcome to {promo.trial_tier}! {promo.trial_duration_days}-day trial activated.",
        tier_granted=promo.trial_tier,
        duration_days=promo.trial_duration_days
    )


# ============================================================================
# ENDPOINT 6: GET /api/ai-coach/referral
# ============================================================================

@router.get("/referral", response_model=ReferralResponse)
async def get_referral_info(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get referral information for influencers
    Shows code, referral count, and bonus tracking
    """
    
    # Find promo codes owned by this user
    promos = db.query(PromoCode).filter_by(influencer_id=user.id).all()
    
    if not promos:
        raise HTTPException(
            status_code=404,
            detail="You don't have a referral code yet. Contact support to become an influencer."
        )
    
    # Aggregate stats across all their codes
    primary_code = promos[0]
    
    all_referrals = db.query(Referral).filter(
        Referral.promo_code_id.in_([p.id for p in promos])
    ).all()
    
    active_conversions = sum(1 for r in all_referrals if r.is_active and r.conversion_date)
    total_revenue = sum(r.referral_value_usd or 0 for r in all_referrals if r.conversion_date)
    total_bonuses = sum(r.bonus_awarded for r in all_referrals)
    
    # Calculate upcoming bonuses
    upcoming_bonuses = {}
    if active_conversions >= 50 and active_conversions < 100:
        upcoming_bonuses["$250 @ 100 refs"] = 100 - active_conversions
    elif active_conversions >= 100 and active_conversions < 250:
        upcoming_bonuses["$500 @ 250 refs"] = 250 - active_conversions
    elif active_conversions >= 250:
        upcoming_bonuses["$1,000 @ 500 refs"] = 500 - active_conversions
    
    return ReferralResponse(
        code=primary_code.code,
        total_referrals=len(all_referrals),
        active_conversions=active_conversions,
        revenue_generated=total_revenue,
        bonus_earned=total_bonuses,
        upcoming_bonuses=upcoming_bonuses
    )


# Health check
@router.get("/health")
async def health():
    """Simple health check"""
    return {"status": "ok", "service": "ai-coach"}
