from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class ClockRequest(BaseModel):
    current_time: Optional[str] = Field(None, description="ISO timestamp to set current system clock (e.g. 2026-12-15T00:00:00Z)", example="2026-12-15T00:00:00Z")
    advance_days: Optional[int] = Field(None, ge=1, description="Number of days to advance system clock by", example=90)

class ClockResponse(BaseModel):
    status: str
    as_of_time: str
    cutoff_time: str
    members_expired_count: int
    total_points_expired: int
    expiration_details: List[Dict[str, Any]]
