from fastapi import APIRouter, HTTPException, Depends
import sqlite3

from src.api.deps import get_db, get_purchase_service, get_current_user
from src.api.schemas.purchase import PurchaseRequest, PurchaseResponse
from src.services.purchase_service import PurchaseService
from src.storage.repository import MemberNotFoundError

router = APIRouter(prefix="/purchases", tags=["Purchases"])


@router.post("", response_model=PurchaseResponse, status_code=200)
def record_purchase(
    req: PurchaseRequest,
    conn: sqlite3.Connection = Depends(get_db),
    purchase_svc: PurchaseService = Depends(get_purchase_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Record a purchase transaction inside an atomic database transaction.
    Enforces floor rounding rules, tier upgrades, and client idempotency.
    Requires staff authentication — staff_id auto-populated from JWT if not provided.
    """
    # Auto-populate staff_id from authenticated user if not explicitly provided
    staff_id = req.staff_id or current_user.get("username", "STAFF_UNKNOWN")
    try:
        return purchase_svc.record_purchase(
            conn=conn,
            member_id=req.member_id,
            amount_spent=req.amount_spent,
            idempotency_key=req.idempotency_key,
            terminal_id=req.terminal_id,
            staff_id=staff_id
        )
    except MemberNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
