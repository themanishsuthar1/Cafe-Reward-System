from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class CreateMemberRequest(BaseModel):
    name: str = Field(..., description="Full name of the member", example="Alice Smith")
    phone: str = Field(..., description="Phone number to normalize and index", example="555-123-4567")

class TierProgressSchema(BaseModel):
    current_tier: str
    next_tier: Optional[str] = None
    points_needed: int
    progress_percent: float

class MemberResponse(BaseModel):
    id: str
    name: str
    phone: str
    tier: str
    join_date: str
    current_points: int
    lifetime_points: int
    points_multiplier: float
    tier_progress: Optional[TierProgressSchema] = None
