from typing import Optional, Dict, Any
import sqlite3
from src.storage.repository import Repository
from src.domain.points import calculate_points_earned
from src.domain.tier import get_tier_multiplier, evaluate_tier, Tier
from src.logger import get_logger

logger = get_logger("services.purchase")


class PurchaseService:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def record_purchase(
        self,
        conn: sqlite3.Connection,
        member_id: str,
        amount_spent: float,
        idempotency_key: str,
        staff_id: Optional[str] = None,
        terminal_id: Optional[str] = None,
        created_at: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Orchestrates purchase recording:
        1. Checks idempotency.
        2. Retrieves member tier at time of purchase.
        3. Calculates points earned using domain rules.
        4. Writes transaction to ledger and updates balance cache atomically.
        """
        if amount_spent <= 0:
            raise ValueError("Amount spent must be greater than zero.")
        if not idempotency_key or not idempotency_key.strip():
            raise ValueError("Idempotency key is required.")

        repo = Repository(conn)

        # Quick check for idempotency before lock
        existing = repo.get_idempotency_record(idempotency_key)
        if existing:
            return existing

        # Fetch current balance cache to get active tier
        cache = repo.get_member_balance_cache(member_id)
        current_tier = cache["current_tier"]
        multiplier = get_tier_multiplier(current_tier)

        # Domain calculation
        points_earned = calculate_points_earned(amount_spent, multiplier)

        # Atomic transaction execution in repo
        return repo.record_purchase_transaction(
            member_id=member_id,
            amount_spent=amount_spent,
            points_delta=points_earned,
            idempotency_key=idempotency_key,
            staff_id=staff_id,
            terminal_id=terminal_id,
            created_at=created_at
        )

