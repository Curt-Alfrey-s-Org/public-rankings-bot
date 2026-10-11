"""
xAI Grok AI Coach Client
Provides pool/billiards coaching analysis via Grok Vision API
"""

import asyncio
import base64
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from enum import Enum
import httpx

logger = logging.getLogger(__name__)


class AnalysisStatus(str, Enum):
    """Status of an analysis request"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class GrokCoachClient:
    """
    Client for xAI Grok API - specialized for pool/billiards coaching
    """
    
    XAI_API_BASE = "https://api.x.ai/v1"
    MODEL = "grok-4"
    
    # Pricing (as of Feb 2026)
    INPUT_COST_PER_1M_TOKENS = 0.20
    OUTPUT_COST_PER_1M_TOKENS = 0.50
    
    # Retry configuration
    MAX_RETRIES = 3
    RETRY_BACKOFF_SECONDS = 2
    REQUEST_TIMEOUT_SECONDS = 300  # 5 minutes for long analysis
    
    def __init__(self, api_key: str):
        """
        Initialize Grok client
        
        Args:
            api_key: xAI API key (from environment)
        """
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            timeout=self.REQUEST_TIMEOUT_SECONDS,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        )
        logger.info("GrokCoachClient initialized")
    
    async def close(self) -> None:
        """Close HTTP client connection"""
        await self.client.aclose()
    
    def _build_pool_coaching_prompt(
        self,
        game_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build specialized pool coaching prompt for Grok
        
        Args:
            game_info: Metadata about the game (player names, format, etc)
        
        Returns:
            System prompt for pool coaching analysis
        """
        player_context = ""
        if game_info:
            if game_info.get("player_name"):
                player_context = f"\nAnalyzing game for: {game_info['player_name']}"
            if game_info.get("opponent_name"):
                player_context += f"\nOpponent: {game_info['opponent_name']}"
            if game_info.get("game_format"):
                player_context += f"\nFormat: {game_info['game_format']} (8-ball, 9-ball, etc)"
        
        return f"""You are an elite pool/billiards coach with 30+ years professional experience.
You hold WPBA (Women's Professional Billiards Association) and BCA (Billiard Congress of America) credentials.

Your task: Analyze the provided video frames from a pool/billiards match and provide detailed coaching feedback.{player_context}

ANALYSIS FRAMEWORK:

1. STROKE MECHANICS (Rate 0-10)
   - Bridge stability and hand positioning
   - Grip pressure and cue control
   - Follow-through length and acceleration
   - Stance balance and body alignment
   - Cue stroke straightness (0-5mm deviation ideal)
   - Draw, English, and spin consistency

2. SHOT SELECTION & STRATEGY (Rate 0-10)
   - Ball selection logic and sequence optimization
   - Table management and position play
   - Safety execution effectiveness
   - Long shot vs. safeties risk-reward
   - End-game / end-table positioning
   - Use of speed control for position

3. MENTAL GAME & COMPOSURE (Rate 0-10)
   - Confidence level (not overconfidence)
   - Reaction to missed shots
   - Focus and concentration maintenance
   - Pressure handling (break vs. down scenarios)
   - Consistency across consecutive shots

4. ACTIONABLE FEEDBACK
   - 3-5 specific praise points (what they're doing well - reference video moments)
   - 3-5 specific improvement areas (with concrete examples from the frames)
   - One critical "focus area" for next practice session

5. DAILY PRACTICE DRILLS
   Provide 2-3 targeted exercises:
   - Drill name
   - Objective
   - Setup instructions
   - Success criteria
   - Time estimate (15-30 minutes each)
   - How often to practice

6. MATCH STATISTICS (if visible in frames)
   - Balls made / attempted shots
   - Overall accuracy %
   - Effective safeties
   - Position play success rate
   - Longest run achieved
   - Critical mistakes (if any)

7. OVERALL ASSESSMENT
   - Current skill level estimate
   - Realistic 30-day improvement goals
   - Areas requiring most practice time

FORMAT YOUR RESPONSE AS VALID JSON with this structure:
{{
  "stroke_mechanics": {{
    "score": 0-10,
    "strengths": ["strength1", "strength2"],
    "improvements": ["area1", "area2"],
    "technical_notes": "detailed feedback"
  }},
  "strategy": {{
    "score": 0-10,
    "strengths": ["strength1", "strength2"],
    "improvements": ["area1", "area2"],
    "analysis": "detailed analysis"
  }},
  "mental_game": {{
    "score": 0-10,
    "observations": ["observation1", "observation2"],
    "pressure_handling": "notes"
  }},
  "performance_stats": {{
    "balls_made": 0,
    "shots_attempted": 0,
    "accuracy_percent": 0,
    "safeties_effective": 0,
    "longest_run": 0
  }},
  "praise": ["point1", "point2", "point3"],
  "improvements": ["improvement1", "improvement2", "improvement3"],
  "critical_focus_area": "Most important thing to work on",
  "daily_drills": [
    {{
      "name": "Drill Name",
      "objective": "What to improve",
      "setup": "How to set up",
      "success_criteria": "How to know you're doing it right",
      "duration_minutes": 15,
      "frequency": "Daily / 3x weekly / etc"
    }}
  ],
  "overall_assessment": {{
    "skill_estimate": "Intermediate / Advanced / etc",
    "six_month_goals": ["goal1", "goal2"],
    "recommended_focus_hours_per_week": 5
  }}
}}

Be conversational but professional. Use specific observations from the video frames.
Focus on actionable, measurable improvements."""
    
    async def analyze_pool_game(
        self,
        frames: List[str],
        game_info: Optional[Dict[str, Any]] = None,
        transcript: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze pool game video frames and return coaching analysis
        
        Args:
            frames: List of base64-encoded JPEG images
            game_info: Metadata about the game (player names, format, etc)
            transcript: Optional audio transcription from the video
        
        Returns:
            Dictionary with analysis results and cost information
        
        Raises:
            ValueError: If frames validation fails
            RuntimeError: If API call fails after retries
        """
        if not frames:
            raise ValueError("No frames provided for analysis")
        
        if len(frames) > 100:
            logger.warning(f"Received {len(frames)} frames (typical: 30-60)")
        
        # Build message with frames
        content = [
            {
                "type": "text",
                "text": self._build_pool_coaching_prompt(game_info)
            }
        ]
        
        # Add frames as images
        for i, frame_b64 in enumerate(frames):
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": frame_b64
                }
            })
        
        # Add transcript if provided
        if transcript:
            content.append({
                "type": "text",
                "text": f"\nVIDEO AUDIO TRANSCRIPT:\n{transcript}"
            })
        
        # Prepare request
        request_body = {
            "messages": [
                {
                    "role": "user",
                    "content": content
                }
            ],
            "model": self.MODEL,
            "stream": False,
            "temperature": 0.1,  # Low temp for consistent coaching
        }
        
        # Execute with retries
        result = await self._call_with_retry(request_body, frames, game_info)
        
        return result

    def _build_progression_prompt(
        self,
        previous_summary: str,
        previous_result_json: Dict[str, Any],
        game_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build prompt for progression review: compare previous assessment with new video."""
        try:
            prev_json_str = json.dumps(previous_result_json, indent=2)[:8000]
        except Exception:
            prev_json_str = str(previous_result_json)[:8000]
        player_context = ""
        if game_info:
            if game_info.get("player_name"):
                player_context = f"\nPlayer: {game_info['player_name']}"
            if game_info.get("opponent_name"):
                player_context += f"\nOpponent: {game_info['opponent_name']}"
            if game_info.get("game_format"):
                player_context += f"\nFormat: {game_info['game_format']}"
        return f"""You are an elite pool/billiards coach. Your task is PROGRESSION REVIEW.

Below is this player's PREVIOUS coaching assessment (from an earlier video). The images that follow are from a NEW video of the same player.

PREVIOUS ASSESSMENT SUMMARY:
{previous_summary or "No summary."}

PREVIOUS FULL ASSESSMENT (JSON):
{prev_json_str}
{player_context}

Compare the new video frames with the previous assessment. Provide a structured JSON analysis (same schema as a normal coaching analysis) that:
1. Notes what has IMPROVED since the previous assessment.
2. Notes what STILL NEEDS WORK or has regressed.
3. Updates scores (stroke_mechanics, strategy, mental_game) and overall_score based on the new footage.
4. Gives updated recommendations and daily_drills if appropriate.
5. Includes an overall_assessment with skill_estimate and six_month_goals reflecting progression.

Return ONLY valid JSON in the same format as your standard pool coaching analysis (stroke_mechanics, strategy, mental_game, praise, improvements, critical_focus_area, daily_drills, overall_assessment, overall_score). Add a short "progression_notes" string at top level summarizing improvement vs areas to focus on."""

    async def analyze_progression(
        self,
        previous_summary: str,
        previous_result_json: Dict[str, Any],
        frames: List[str],
        game_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Compare a previous coaching assessment with new video frames and return progression analysis.
        """
        if not frames:
            raise ValueError("No frames provided for progression analysis")
        content = [
            {"type": "text", "text": self._build_progression_prompt(previous_summary, previous_result_json, game_info)}
        ]
        for frame_b64 in frames:
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": frame_b64}
            })
        request_body = {
            "messages": [{"role": "user", "content": content}],
            "model": self.MODEL,
            "stream": False,
            "temperature": 0.1,
        }
        result = await self._call_with_retry(request_body, frames, game_info)
        return result
    
    async def _call_with_retry(
        self,
        request_body: Dict,
        frames: List[str],
        game_info: Optional[Dict] = None,
        attempt: int = 1
    ) -> Dict[str, Any]:
        """
        Execute API call with exponential backoff retry logic
        """
        try:
            logger.info(f"Calling Grok API (attempt {attempt}/{self.MAX_RETRIES})")
            logger.info(f"Frames: {len(frames)}, Content type: application/json")
            
            response = await self.client.post(
                f"{self.XAI_API_BASE}/chat/completions",
                json=request_body
            )
            
            # Check for API errors
            if response.status_code == 429:  # Rate limit
                if attempt < self.MAX_RETRIES:
                    wait_seconds = self.RETRY_BACKOFF_SECONDS ** attempt
                    logger.warning(f"Rate limited. Retrying in {wait_seconds}s...")
                    await asyncio.sleep(wait_seconds)
                    return await self._call_with_retry(request_body, frames, game_info, attempt + 1)
                else:
                    raise RuntimeError("Rate limit exceeded after retries")
            
            elif response.status_code == 503:  # Service unavailable
                if attempt < self.MAX_RETRIES:
                    wait_seconds = self.RETRY_BACKOFF_SECONDS ** attempt
                    logger.warning(f"Service unavailable. Retrying in {wait_seconds}s...")
                    await asyncio.sleep(wait_seconds)
                    return await self._call_with_retry(request_body, frames, game_info, attempt + 1)
                else:
                    raise RuntimeError("Service unavailable after retries")
            
            elif response.status_code != 200:
                error_text = response.text
                logger.error(f"API error {response.status_code}: {error_text}")
                raise RuntimeError(f"Grok API error: {response.status_code} - {error_text}")
            
            # Parse successful response
            data = response.json()
            
            # Extract analysis from response
            if "choices" not in data or not data["choices"]:
                raise RuntimeError("Unexpected API response format")
            
            message_content = data["choices"][0]["message"]["content"]
            
            # Parse JSON response from Grok
            try:
                analysis_json = json.loads(message_content)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse Grok response as JSON: {message_content[:200]}")
                raise RuntimeError("Grok returned non-JSON response")
            
            # Extract token usage
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            
            # Calculate cost
            input_cost = (input_tokens / 1_000_000) * self.INPUT_COST_PER_1M_TOKENS
            output_cost = (output_tokens / 1_000_000) * self.OUTPUT_COST_PER_1M_TOKENS
            total_cost = input_cost + output_cost
            
            logger.info(f"Analysis complete. Tokens: {input_tokens} in, {output_tokens} out. Cost: ${total_cost:.4f}")
            
            return {
                "status": "completed",
                "analysis": analysis_json,
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens
                },
                "cost_usd": round(total_cost, 4),
                "model": self.MODEL,
                "timestamp": datetime.utcnow().isoformat(),
                "frames_analyzed": len(frames)
            }
        
        except RuntimeError:
            raise  # Re-raise our own errors
        except Exception as e:
            logger.error(f"Unexpected error in Grok call: {str(e)}")
            if attempt < self.MAX_RETRIES:
                wait_seconds = self.RETRY_BACKOFF_SECONDS ** attempt
                logger.info(f"Retrying in {wait_seconds}s...")
                await asyncio.sleep(wait_seconds)
                return await self._call_with_retry(request_body, frames, game_info, attempt + 1)
            else:
                raise RuntimeError(f"Grok API call failed: {str(e)}")

    async def chat_text(self, user_message: str) -> str:
        """
        Send a single text message to Grok and return the assistant's reply. Used for recon (no frames).
        """
        request_body = {
            "messages": [{"role": "user", "content": user_message}],
            "model": self.MODEL,
            "stream": False,
            "temperature": 0.2,
        }
        response = await self.client.post(
            f"{self.XAI_API_BASE}/chat/completions",
            json=request_body,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Grok API error: {response.status_code} - {response.text[:300]}")
        data = response.json()
        if "choices" not in data or not data["choices"]:
            raise RuntimeError("Unexpected Grok response format")
        return (data["choices"][0].get("message") or {}).get("content") or ""

    def estimate_analysis_cost(
        self,
        num_frames: int = 30,
        transcript_length: int = 2000,
        estimated_output_tokens: int = 2000
    ) -> float:
        """
        Estimate the cost of an analysis BEFORE calling Grok
        
        Args:
            num_frames: Number of frames in analysis (default 30)
            transcript_length: Characters in audio transcript (default 2000)
            estimated_output_tokens: Expected output tokens (coaching analysis)
        
        Returns:
            Estimated cost in USD
        """
        # Rough estimation: 
        # - System prompt: ~2000 tokens
        # - Per frame: ~100 tokens (base64 + content)
        # - Transcript: ~0.25 tokens per character
        # - Output: provided estimate
        
        system_tokens = 2000
        frame_tokens = num_frames * 100
        transcript_tokens = int(transcript_length * 0.25)
        
        total_input = system_tokens + frame_tokens + transcript_tokens
        total_output = estimated_output_tokens
        
        input_cost = (total_input / 1_000_000) * self.INPUT_COST_PER_1M_TOKENS
        output_cost = (total_output / 1_000_000) * self.OUTPUT_COST_PER_1M_TOKENS
        
        return round(input_cost + output_cost, 4)


# Example usage and testing
async def test_grok_client():
    """Test the Grok client with a simple query"""
    import os
    
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        print("ERROR: XAI_API_KEY not set in environment")
        return
    
    client = GrokCoachClient(api_key)
    
    try:
        # Test with mock frame (just text for testing)
        test_frames = [""] * 3  # Would be real base64 frames
        
        # Estimate cost first
        estimated_cost = client.estimate_analysis_cost()
        print(f"Estimated cost: ${estimated_cost}")
        
        # In real use, would call with actual frames:
        # result = await client.analyze_pool_game(
        #     frames=frames,
        #     game_info={"player_name": "Test Player"},
        #     transcript="Test audio"
        # )
        # print(json.dumps(result, indent=2))
        
    finally:
        await client.close()


# Test function removed in cleanup - use API endpoint for testing
