from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime, timezone, timedelta
import sqlite3

from src.api.deps import get_db, get_clock_service, require_role
from src.api.schemas.clock import ClockRequest, ClockResponse
from src.services.clock_service import ClockService

router = APIRouter(prefix="/clock", tags=["Clock & Expiration Automation"])


@router.post("", response_model=ClockResponse)
def update_clock_and_expire(
    req: ClockRequest,
    conn: sqlite3.Connection = Depends(get_db),
    clock_svc: ClockService = Depends(get_clock_service),
    _: dict = Depends(require_role("admin"))
):
    """
    Time-Travel / Clock Automation Endpoint (Level 2 Twist):
    Advances or sets virtual system clock, executes 90-day unredeemed point expiration sweeps,
    appends atomic EXPIRATION transactions to the ledger, and returns summary details.
    Requires admin role.
    """
    target_time: datetime

    if req.current_time:
        try:
            target_time = datetime.fromisoformat(req.current_time.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid ISO timestamp format: '{req.current_time}'")
    elif req.advance_days:
        current_now = clock_svc.get_current_time()
        target_time = current_now + timedelta(days=req.advance_days)
    else:
        current_now = clock_svc.get_current_time()
        target_time = current_now + timedelta(days=90)

    clock_svc.set_clock_time(target_time)
    sweep_results = clock_svc.run_expiration_sweep(conn, as_of_time=target_time)
    return sweep_results
