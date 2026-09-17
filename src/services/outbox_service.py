import sqlite3
from typing import List, Dict, Any, Optional
from src.storage.repository import Repository
from src.logger import get_logger

logger = get_logger("services.outbox")

class OutboxService:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def list_events(self, conn: sqlite3.Connection, status: Optional[str] = None) -> List[Dict[str, Any]]:
        repo = Repository(conn)
        return repo.get_outbox_events(status=status)

    def process_pending_events(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        """
        Simulates Notification Service processing of pending outbox events.
        Marks pending events as PROCESSED.
        """
        repo = Repository(conn)
        pending = repo.get_outbox_events(status="PENDING")
        if not pending:
            return {"status": "SUCCESS", "processed_count": 0, "message": "No pending outbox events to process."}

        event_ids = [e["id"] for e in pending]
        count = repo.mark_outbox_processed(event_ids)
        logger.info(f"Processed {count} pending notification outbox events.")

        return {
            "status": "SUCCESS",
            "processed_count": count,
            "processed_events": pending
        }
