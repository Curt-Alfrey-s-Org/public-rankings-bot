"""
Celery worker for AI Coach background analysis
Runs Grok API calls asynchronously to keep API responsive
"""

# Doc refs (AI / maintainers): docs/OLLAMA_AND_AI_MONITOR.md; docs/ENV_VARS.md (Celery/Redis);
#   docs/PRODUCTION_DEPLOYMENT.md (worker service)

import asyncio
import logging
import os
from datetime import datetime
from celery import Celery
from sqlalchemy.orm import Session

from project_root import PROJECT_ROOT

# Celery app
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
app = Celery(
    "ai_coach",
    broker=CELERY_BROKER_URL,
    backend=CELERY_BROKER_URL,
)
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    task_time_limit=600,  # 10 min max per task
)

logger = logging.getLogger(__name__)


def get_db_session() -> Session:
    """Create database session for Celery worker (runs in separate process)."""
    import sys
    from pathlib import Path
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from database import get_session_local
    return get_session_local()()


@app.task(bind=True, name="ai_coach.analyze_video")
def analyze_video_task(self, analysis_id: str, user_id: str):
    """
    Background task: load frames from storage, call Grok, update analysis.
    Frames are already saved by the API before this task is queued.
    """
    import sys
    from pathlib import Path
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from api.models.ai_coach import AICoachAnalysis, AICoachUsage
    from api.services.grok_client import GrokCoachClient
    from api.services.frame_storage import OracleFrameStorage

    db = get_db_session()
    try:
        # Load analysis
        analysis = db.query(AICoachAnalysis).filter_by(id=analysis_id, user_id=user_id).first()
        if not analysis:
            logger.error(f"Analysis {analysis_id} not found")
            return {"status": "failed", "error": "Analysis not found"}

        # Update to processing
        analysis.status = "processing"
        analysis.started_processing_at = datetime.utcnow()
        db.commit()

        # Load frames from storage
        storage = OracleFrameStorage(
            storage_root=os.getenv("FRAME_STORAGE_ROOT", "/app/pools_coaching_frames")
        )
        stored = asyncio.run(storage.retrieve_frames(analysis_id))
        if not stored or not stored.get("frames"):
            analysis.status = "failed"
            analysis.error_message = "Could not load frames from storage"
            analysis.completed_at = datetime.utcnow()
            db.commit()
            return {"status": "failed", "error": analysis.error_message}

        frames = [f["data"] for f in stored["frames"]]

        # Call Grok
        api_key = os.getenv("XAI_API_KEY")
        if not api_key:
            analysis.status = "failed"
            analysis.error_message = "XAI_API_KEY not configured"
            analysis.completed_at = datetime.utcnow()
            db.commit()
            return {"status": "failed", "error": analysis.error_message}

        client = GrokCoachClient(api_key)
        game_info = {}
        if analysis.player_name:
            game_info["player_name"] = analysis.player_name
        if analysis.opponent_name:
            game_info["opponent_name"] = analysis.opponent_name
        if analysis.game_format:
            game_info["game_format"] = analysis.game_format

        async def run_analysis():
            try:
                return await client.analyze_pool_game(
                    frames=frames,
                    game_info=game_info if game_info else None,
                    transcript=None
                )
            finally:
                await client.close()

        result = asyncio.run(run_analysis())

        # Update analysis with results
        analysis.status = "completed"
        analysis.completed_at = datetime.utcnow()
        analysis.analysis_json = result.get("analysis")
        usage_data = result.get("usage", {})
        analysis.grok_tokens_input = usage_data.get("input_tokens", 0)
        analysis.grok_tokens_output = usage_data.get("output_tokens", 0)
        analysis.grok_cost_usd = result.get("cost_usd", 0)

        # Extract scores and summary
        a = result.get("analysis", {}) or {}
        analysis.stroke_mechanics_score = _safe_float(a.get("stroke_mechanics", {}).get("score"))
        analysis.strategy_score = _safe_float(a.get("strategy", {}).get("score"))
        analysis.mental_game_score = _safe_float(a.get("mental_game", {}).get("score"))
        scores = [x for x in [analysis.stroke_mechanics_score, analysis.strategy_score, analysis.mental_game_score] if x is not None]
        analysis.overall_score = sum(scores) / len(scores) if scores else None
        analysis.summary_text = a.get("critical_focus_area") or str(a.get("overall_assessment", {}).get("skill_estimate", ""))[:500]

        # Increment usage
        usage = db.query(AICoachUsage).filter_by(user_id=user_id).first()
        if usage:
            usage.analyses_this_month += 1
            usage.lifetime_analyses += 1
            usage.last_analysis_at = datetime.utcnow()

        db.commit()

        # Update ALFA rating based on video analysis results
        try:
            update_alfa_rating_from_video_analysis(analysis_id, user_id, analysis.player_name, analysis.bot_type)
        except Exception as e:
            logger.warning(f"Failed to update ALFA rating for analysis {analysis_id}: {e}")
            # Don't fail the analysis if rating update fails

        # Discard video/frames after analysis (only assessment is kept)
        try:
            deleted = asyncio.run(storage.delete_analysis(analysis_id))
            if deleted:
                logger.info(f"Frames discarded for analysis {analysis_id}")
            else:
                logger.debug(f"No frames to discard for analysis {analysis_id}")
        except Exception as e:
            logger.warning(f"Failed to discard frames for analysis {analysis_id}: {e}")

        logger.info(f"Analysis {analysis_id} completed")
        return {"status": "completed", "analysis_id": analysis_id}

    except Exception as e:
        logger.exception(f"Analysis {analysis_id} failed: {e}")
        try:
            analysis = db.query(AICoachAnalysis).filter_by(id=analysis_id).first()
            if analysis:
                analysis.status = "failed"
                analysis.error_message = str(e)[:500]
                analysis.completed_at = datetime.utcnow()
                db.commit()
        except Exception as persist_error:
            logger.warning("Could not persist failure state for analysis %s: %s", analysis_id, persist_error)
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


@app.task(bind=True, name="ai_coach.progression_video")
def progression_video_task(self, analysis_id: str, user_id: str):
    """
    Background task: load new frames + previous assessment, call Grok progression, update analysis.
    """
    import sys
    from pathlib import Path
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from api.models.ai_coach import AICoachAnalysis, AICoachUsage
    from api.services.grok_client import GrokCoachClient
    from api.services.frame_storage import OracleFrameStorage

    db = get_db_session()
    try:
        analysis = db.query(AICoachAnalysis).filter_by(id=analysis_id, user_id=user_id).first()
        if not analysis:
            logger.error(f"Progression analysis {analysis_id} not found")
            return {"status": "failed", "error": "Analysis not found"}
        if not analysis.progression_from_id:
            logger.error(f"Progression analysis {analysis_id} has no progression_from_id")
            analysis.status = "failed"
            analysis.error_message = "Invalid progression request"
            analysis.completed_at = datetime.utcnow()
            db.commit()
            return {"status": "failed", "error": "Invalid progression request"}

        previous = db.query(AICoachAnalysis).filter_by(
            id=analysis.progression_from_id,
            user_id=user_id
        ).first()
        if not previous or previous.status != "completed":
            analysis.status = "failed"
            analysis.error_message = "Previous assessment not found or not completed"
            analysis.completed_at = datetime.utcnow()
            db.commit()
            return {"status": "failed", "error": analysis.error_message}

        analysis.status = "processing"
        analysis.started_processing_at = datetime.utcnow()
        db.commit()

        storage = OracleFrameStorage(
            storage_root=os.getenv("FRAME_STORAGE_ROOT", "/app/pools_coaching_frames")
        )
        stored = asyncio.run(storage.retrieve_frames(analysis_id))
        if not stored or not stored.get("frames"):
            analysis.status = "failed"
            analysis.error_message = "Could not load frames from storage"
            analysis.completed_at = datetime.utcnow()
            db.commit()
            return {"status": "failed", "error": analysis.error_message}

        frames = [f["data"] for f in stored["frames"]]
        api_key = os.getenv("XAI_API_KEY")
        if not api_key:
            analysis.status = "failed"
            analysis.error_message = "XAI_API_KEY not configured"
            analysis.completed_at = datetime.utcnow()
            db.commit()
            return {"status": "failed", "error": analysis.error_message}

        client = GrokCoachClient(api_key)
        game_info = {}
        if analysis.player_name:
            game_info["player_name"] = analysis.player_name
        if analysis.opponent_name:
            game_info["opponent_name"] = analysis.opponent_name
        if analysis.game_format:
            game_info["game_format"] = analysis.game_format
        previous_summary = previous.summary_text or ""
        previous_json = previous.analysis_json if isinstance(previous.analysis_json, dict) else {}

        async def run_progression():
            try:
                return await client.analyze_progression(
                    previous_summary=previous_summary,
                    previous_result_json=previous_json,
                    frames=frames,
                    game_info=game_info if game_info else None,
                )
            finally:
                await client.close()

        result = asyncio.run(run_progression())

        analysis.status = "completed"
        analysis.completed_at = datetime.utcnow()
        analysis.analysis_json = result.get("analysis")
        usage_data = result.get("usage", {})
        analysis.grok_tokens_input = usage_data.get("input_tokens", 0)
        analysis.grok_tokens_output = usage_data.get("output_tokens", 0)
        analysis.grok_cost_usd = result.get("cost_usd", 0)
        a = result.get("analysis", {}) or {}
        analysis.stroke_mechanics_score = _safe_float(a.get("stroke_mechanics", {}).get("score"))
        analysis.strategy_score = _safe_float(a.get("strategy", {}).get("score"))
        analysis.mental_game_score = _safe_float(a.get("mental_game", {}).get("score"))
        scores = [x for x in [analysis.stroke_mechanics_score, analysis.strategy_score, analysis.mental_game_score] if x is not None]
        analysis.overall_score = sum(scores) / len(scores) if scores else None
        analysis.summary_text = a.get("progression_notes") or a.get("critical_focus_area") or str(a.get("overall_assessment", {}).get("skill_estimate", ""))[:500]

        usage = db.query(AICoachUsage).filter_by(user_id=user_id).first()
        if usage:
            usage.analyses_this_month += 1
            usage.lifetime_analyses += 1
            usage.last_analysis_at = datetime.utcnow()
        db.commit()

        try:
            deleted = asyncio.run(storage.delete_analysis(analysis_id))
            if deleted:
                logger.info(f"Frames discarded for progression analysis {analysis_id}")
        except Exception as e:
            logger.warning(f"Failed to discard frames for progression {analysis_id}: {e}")

        logger.info(f"Progression analysis {analysis_id} completed")
        return {"status": "completed", "analysis_id": analysis_id}

    except Exception as e:
        logger.exception(f"Progression {analysis_id} failed: {e}")
        try:
            analysis = db.query(AICoachAnalysis).filter_by(id=analysis_id).first()
            if analysis:
                analysis.status = "failed"
                analysis.error_message = str(e)[:500]
                analysis.completed_at = datetime.utcnow()
                db.commit()
        except Exception as persist_error:
            logger.warning("Could not persist failure state for progression %s: %s", analysis_id, persist_error)
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


@app.task(bind=True, name="ai_coach.text_coaching")
def text_coaching_task(self, analysis_id: str, user_id: str, question: str, player_name: str = "", game_format: str = ""):
    """
    Background task: answer a text-only coaching question via Ollama (free).
    Falls back to Grok if Ollama is unavailable.
    """
    import sys
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from api.models.ai_coach import AICoachAnalysis, AICoachUsage

    db = get_db_session()
    try:
        analysis = db.query(AICoachAnalysis).filter_by(id=analysis_id, user_id=user_id).first()
        if not analysis:
            logger.error(f"Text coaching analysis {analysis_id} not found")
            return {"status": "failed", "error": "Analysis not found"}

        analysis.status = "processing"
        analysis.started_processing_at = datetime.utcnow()
        db.commit()

        system_prompt = (
            "You are an elite pool/billiards coach with 30+ years professional experience. "
            "You hold WPBA and BCA credentials. Answer with specific, actionable advice."
        )
        player_ctx = ""
        if player_name:
            player_ctx += f"\nPlayer: {player_name}"
        if game_format:
            player_ctx += f"\nGame format: {game_format}"
        user_msg = f"{player_ctx}\n\nQuestion: {question}" if player_ctx else question

        answer = None
        model_used = "unknown"
        cost = 0.0

        # Try Ollama first
        try:
            from api.services.ollama_client import get_ollama_client
            ollama = get_ollama_client()
            if ollama is not None:
                resp = asyncio.run(ollama.chat(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_msg},
                    ],
                    model=ollama.model_chat,
                    temperature=0.3,
                ))
                if not resp.error:
                    answer = resp.content
                    model_used = resp.model
                else:
                    logger.warning("Ollama text coaching failed: %s", resp.error)
        except Exception as e:
            logger.warning("Ollama unavailable for text coaching: %s", e)

        # Grok fallback
        if answer is None:
            api_key = os.getenv("XAI_API_KEY")
            if api_key:
                from api.services.grok_client import GrokCoachClient
                client = GrokCoachClient(api_key)
                try:
                    answer = asyncio.run(client.chat_text(f"{system_prompt}\n\n{user_msg}"))
                    model_used = "grok-4"
                finally:
                    asyncio.run(client.close())

        if answer is None:
            analysis.status = "failed"
            analysis.error_message = "Both Ollama and Grok unavailable"
            analysis.completed_at = datetime.utcnow()
            db.commit()
            return {"status": "failed", "error": analysis.error_message}

        analysis.status = "completed"
        analysis.completed_at = datetime.utcnow()
        analysis.analysis_json = {"text_answer": answer, "model": model_used}
        analysis.summary_text = answer[:500]
        analysis.grok_cost_usd = cost

        usage = db.query(AICoachUsage).filter_by(user_id=user_id).first()
        if usage:
            usage.analyses_this_month += 1
            usage.lifetime_analyses += 1
            usage.last_analysis_at = datetime.utcnow()
        db.commit()

        logger.info(f"Text coaching {analysis_id} completed via {model_used}")
        return {"status": "completed", "analysis_id": analysis_id}

    except Exception as e:
        logger.exception(f"Text coaching {analysis_id} failed: {e}")
        try:
            analysis = db.query(AICoachAnalysis).filter_by(id=analysis_id).first()
            if analysis:
                analysis.status = "failed"
                analysis.error_message = str(e)[:500]
                analysis.completed_at = datetime.utcnow()
                db.commit()
        except Exception as persist_error:
            logger.warning("Could not persist failure for text coaching %s: %s", analysis_id, persist_error)
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


def _safe_float(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def update_alfa_rating_from_video_analysis(analysis_id: str, user_id: str, player_name: str, bot_type: str):
    """
    Update ALFA rating based on completed video analysis.

    This function calls the ALFA rating update endpoint with video analysis results
    to refine player ratings based on direct performance observation.
    """
    import requests

    # Determine association based on bot_type
    association_map = {
        'rankings': 'WPBA',  # Default to WPBA for rankings bot
        'wpba': 'WPBA',
        'wpa_women': 'WPA_Women',
        'wpa_men': 'WPA_Men'
    }
    association = association_map.get(bot_type.lower(), 'WPBA')

    # Call ALFA rating update endpoint
    api_url = "http://localhost:8003/api/alfa/video-analysis-update"  # Internal API call

    try:
        response = requests.post(
            api_url,
            json={
                "analysis_id": analysis_id,
                "user_id": user_id,
                "player_name": player_name,
                "association": association
            },
            headers={
                "Content-Type": "application/json",
                # Internal call - no auth header needed for this endpoint
            },
            timeout=30.0
        )

        if response.status_code == 200:
            result = response.json()
            logger.info(f"Updated ALFA rating for {player_name}: {result.get('old_rating', 'N/A')} -> {result.get('new_rating', 'N/A')}")
        else:
            logger.warning(f"Failed to update ALFA rating for analysis {analysis_id}: HTTP {response.status_code} - {response.text}")
    except requests.RequestException as e:
        logger.warning(f"Failed to update ALFA rating for analysis {analysis_id}: {e}")
