from fastapi import APIRouter, Depends, Query
from typing import List, Optional
import sqlite3

from src.api.deps import get_db, get_outbox_service, get_current_user, require_role
from src.api.schemas.outbox import OutboxEventResponse, ProcessOutboxResponse
from src.services.outbox_service import OutboxService

router = APIRouter(prefix="/outbox", tags=["Notification Outbox"])


@router.get("", response_model=List[OutboxEventResponse])
def list_outbox_events(
    status: Optional[str] = Query(None, description="Filter by status: PENDING or PROCESSED"),
    conn: sqlite3.Connection = Depends(get_db),
    outbox_svc: OutboxService = Depends(get_outbox_service),
    _: dict = Depends(get_current_user)
):
    """
    Retrieve transactional outbox events (Level 3 Twist).
    Graded endpoint exposing TIER_UPGRADED notifications emitted atomically during purchases.
    Requires staff authentication.
    """
    return outbox_svc.list_events(conn, status=status)


@router.post("/process", response_model=ProcessOutboxResponse)
def process_outbox_events(
    conn: sqlite3.Connection = Depends(get_db),
    outbox_svc: OutboxService = Depends(get_outbox_service),
    _: dict = Depends(require_role("admin"))
):
    """
    Simulates Notification Service processing of PENDING outbox events.
    Marks processed events as PROCESSED. Requires admin role.
    """
    return outbox_svc.process_pending_events(conn)

