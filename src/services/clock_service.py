import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from src.storage.repository import Repository
from src.logger import get_logger

logger = get_logger("services.clock")

class ClockService:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._current_simulated_time: Optional[datetime] = None

    def get_current_time(self) -> datetime:
        """Returns the current system or simulated clock time."""
        return self._current_simulated_time or datetime.now(timezone.utc)

    def set_clock_time(self, new_time: datetime) -> None:
        self._current_simulated_time = new_time
        logger.info(f"System clock updated to '{new_time.isoformat()}'.")

    def run_expiration_sweep(self, conn: sqlite3.Connection, as_of_time: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Executes a 90-day points expiration sweep across all members.
        Any points earned from purchases older than 90 days that have not been redeemed or expired
        are expired via atomic EXPIRATION transactions.
        """
        target_time = as_of_time or self.get_current_time()
        cutoff_time = target_time - timedelta(days=90)
        cutoff_iso = cutoff_time.isoformat()
        target_iso = target_time.isoformat()

        logger.info(f"Running 90-day points expiration sweep as of '{target_iso}' (cutoff date: '{cutoff_iso}').")

        repo = Repository(conn)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM members;")
        member_rows = cursor.fetchall()

        expired_records = []
        total_points_expired = 0

        for m_row in member_rows:
            member_id = m_row["id"]
            
            # Fetch total purchase points earned BEFORE or AT cutoff_time
            cursor.execute("""
                SELECT COALESCE(SUM(points_delta), 0) as old_earned
                FROM transactions
                WHERE member_id = ? AND type = 'PURCHASE' AND created_at <= ?;
            """, (member_id, cutoff_iso))
            old_earned = cursor.fetchone()["old_earned"]

            if old_earned <= 0:
                continue

            # Fetch total deductions (REDEMPTIONS & previous EXPIRATIONS) up to target_time
            cursor.execute("""
                SELECT COALESCE(SUM(ABS(points_delta)), 0) as total_deducted
                FROM transactions
                WHERE member_id = ? AND type IN ('REDEMPTION', 'EXPIRATION') AND created_at <= ?;
            """, (member_id, target_iso))
            total_deducted = cursor.fetchone()["total_deducted"]

            unredeemed_old_points = max(0, old_earned - total_deducted)

            if unredeemed_old_points > 0:
                date_key = cutoff_time.strftime("%Y%m%d")
                idempotency_key = f"exp_{member_id}_{date_key}"
                try:
                    res = repo.record_expiration_transaction(
                        member_id=member_id,
                        expired_points=unredeemed_old_points,
                        idempotency_key=idempotency_key,
                        as_of_iso_time=target_iso
                    )
                    if res.get("status") == "EXPIRED":
                        expired_records.append(res)
                        total_points_expired += res.get("points_expired", 0)
                except Exception as e:
                    logger.error(f"Error expiring points for member '{member_id}': {e}", exc_info=True)

        return {
            "status": "SUCCESS",
            "as_of_time": target_iso,
            "cutoff_time": cutoff_iso,
            "members_expired_count": len(expired_records),
            "total_points_expired": total_points_expired,
            "expiration_details": expired_records
        }
