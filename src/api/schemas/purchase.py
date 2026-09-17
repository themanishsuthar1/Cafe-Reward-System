from pydantic import BaseModel, Field
from typing import Optional

class PurchaseRequest(BaseModel):
    member_id: str = Field(..., description="ID of the purchasing member", example="mem_12345678")
    amount_spent: float = Field(..., gt=0, description="Transaction spend amount", example=12.50)
    idempotency_key: str = Field(..., description="Unique client idempotency key", example="idem_purch_999")
    terminal_id: Optional[str] = Field("TERM_COUNTER_1", example="TERM_COUNTER_1")
    staff_id: Optional[str] = Field("STAFF_01", example="STAFF_01")

class PurchaseResponse(BaseModel):
    status: str
    transaction_id: str
    member_id: str
    type: str
    amount_spent: float
    points_earned: int
    tier_at_time: str
    new_tier: str
    tier_upgraded: bool
    current_points: int
    lifetime_points: int
    idempotency_key: str
    created_at: str
