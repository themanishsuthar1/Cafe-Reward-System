from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class MemberModel:
    id: str
    name: str
    phone: str  # normalized, unique, indexed
    tier: str   # BASE, SILVER, GOLD, PLATINUM
    join_date: str

@dataclass
class TransactionModel:
    id: str
    member_id: str
    type: str  # PURCHASE, REDEMPTION, EXPIRATION
    amount_spent: float
    points_delta: int
    tier_at_time: str
    idempotency_key: str # unique indexed
    created_at: str
    staff_id: Optional[str] = None
    terminal_id: Optional[str] = None

@dataclass
class RewardItemModel:
    id: str
    name: str
    points_cost: int
    active: bool = True

@dataclass
class MemberBalanceCacheModel:
    member_id: str
    current_points: int
    lifetime_points: int
    current_tier: str
    last_transaction_id: Optional[str] = None

@dataclass
class OutboxModel:
    id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload_json: str
    status: str = "PENDING"
    created_at: Optional[str] = None
