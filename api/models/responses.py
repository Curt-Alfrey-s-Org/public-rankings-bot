"""
Response Models for API endpoints
"""

from pydantic import BaseModel
from typing import Optional

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    version: str

class ErrorResponse(BaseModel):
    """Error response"""
    error: str
    detail: Optional[str] = None
