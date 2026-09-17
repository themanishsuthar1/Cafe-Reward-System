from fastapi import APIRouter, HTTPException, Depends
import sqlite3

from src.api.deps import get_db, get_redemption_service, get_current_user
from src.api.schemas.redemption import RedemptionRequest, RedemptionResponse
from src.services.redemption_service import RedemptionService
from src.storage.repository import (
    MemberNotFoundError,
    RewardItemNotFoundError,
    InsufficientPointsError
)

router = APIRouter(prefix="/redemptions", tags=["Redemptions"])


@router.post("", response_model=RedemptionResponse, status_code=200)
def redeem_reward(
    req: RedemptionRequest,
    conn: sqlite3.Connection = Depends(get_db),
    redemption_svc: RedemptionService = Depends(get_redemption_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Redeem points for a reward item inside an atomic database transaction.
    Re-verifies live balance on the server under write lock to prevent race conditions.
    Requires staff authentication.
    """
    staff_id = req.staff_id or current_user.get("username", "STAFF_UNKNOWN")
    try:
        return redemption_svc.redeem_reward(
            conn=conn,
            member_id=req.member_id,
            reward_id=req.reward_id,
            idempotency_key=req.idempotency_key,
            terminal_id=req.terminal_id,
            staff_id=staff_id
        )
    except InsufficientPointsError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "INSUFFICIENT_POINTS",
                "message": str(e),
                "available_points": e.current_points,
                "required_points": e.required_points
            }
        )
    except (MemberNotFoundError, RewardItemNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
