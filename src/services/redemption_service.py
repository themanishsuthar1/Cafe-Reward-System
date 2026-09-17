from typing import Optional, Dict, Any, List
import sqlite3
from src.storage.repository import Repository
from src.logger import get_logger

logger = get_logger("services.redemption")


class RedemptionService:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def redeem_reward(
        self,
        conn: sqlite3.Connection,
        member_id: str,
        reward_id: str,
        idempotency_key: str,
        staff_id: Optional[str] = None,
        terminal_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Orchestrates reward redemption:
        1. Validates input.
        2. Delegates atomic redemption write & server-side balance validation to repository.
        """
        if not idempotency_key or not idempotency_key.strip():
            raise ValueError("Idempotency key is required.")

        repo = Repository(conn)
        return repo.record_redemption_transaction(
            member_id=member_id,
            reward_id=reward_id,
            idempotency_key=idempotency_key,
            staff_id=staff_id,
            terminal_id=terminal_id
        )

    def list_rewards(self, conn: sqlite3.Connection) -> List[Dict[str, Any]]:
        repo = Repository(conn)
        return repo.list_active_rewards()
