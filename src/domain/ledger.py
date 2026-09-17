from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

class TransactionType(str, Enum):
    PURCHASE = "PURCHASE"
    REDEMPTION = "REDEMPTION"
    EXPIRATION = "EXPIRATION"

@dataclass(frozen=True)
class LedgerEntry:
    id: str
    member_id: str
    type: TransactionType
    amount_spent: float
    points_delta: int
    tier_at_time: str
    idempotency_key: str
    created_at: datetime
    staff_id: Optional[str] = None
    terminal_id: Optional[str] = None
