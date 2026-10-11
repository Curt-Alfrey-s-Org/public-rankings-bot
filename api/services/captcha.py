import logging
import os
import httpx
from typing import Dict

logger = logging.getLogger(__name__)


async def verify_recaptcha(token: str) -> Dict:
    """
    Verify reCAPTCHA v3 token with Google's API.
    
    Args:
        token: reCAPTCHA token from the client
        
    Returns:
        Dictionary with verification results:
        - success: bool
        - score: float (0.0-1.0, higher = more likely human)
        - action: str (action returned from client)
        - challenge_ts: str (timestamp of challenge)
        - hostname: str (hostname of site where challenge was solved)
    """
    if not token:
        logger.warning("Empty CAPTCHA token received")
        return {"success": False, "score": 0.0}
    
    secret_key = os.getenv('RECAPTCHA_SECRET_KEY')
    if not secret_key:
        _is_production = os.environ.get("DEBUG", "false").lower() not in ("1", "true", "yes")
        if _is_production:
            logger.warning("RECAPTCHA_SECRET_KEY not configured in production; rejecting registration")
            return {"success": False, "score": 0.0}
        logger.warning("RECAPTCHA_SECRET_KEY not configured, allowing in dev mode")
        return {"success": True, "score": 0.9}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'https://www.google.com/recaptcha/api/siteverify',
                data={
                    'secret': secret_key,
                    'response': token
                },
                timeout=10.0
            )
            result = response.json()
            
            logger.info(f"reCAPTCHA verification: success={result.get('success')}, score={result.get('score')}")
            return result
    except Exception as e:
        logger.error(f"reCAPTCHA verification error: {str(e)}")
        return {"success": False, "score": 0.0, "error": str(e)}
