from pydantic import BaseModel, Field
from typing import Optional

class RedemptionRequest(BaseModel):
    member_id: str = Field(..., description="ID of the redeeming member", example="mem_12345678")
    reward_id: str = Field(..., description="ID of the reward item to redeem", example="rw_espresso")
    idempotency_key: str = Field(..., description="Unique client idempotency key", example="idem_red_888")
    terminal_id: Optional[str] = Field("TERM_COUNTER_1", example="TERM_COUNTER_1")
    staff_id: Optional[str] = Field("STAFF_01", example="STAFF_01")

class RedemptionResponse(BaseModel):
    status: str
    transaction_id: str
    member_id: str
    type: str
    reward_id: str
    reward_name: str
    points_redeemed: int
    tier_at_time: str
    current_points: int
    lifetime_points: int
    idempotency_key: str
    created_at: str

class RewardItemResponse(BaseModel):
    id: str
    name: str
    points_cost: int
    active: bool
