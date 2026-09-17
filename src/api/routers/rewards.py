from fastapi import APIRouter, Depends
from typing import List
import sqlite3

from src.api.deps import get_db, get_redemption_service
from src.api.schemas.redemption import RewardItemResponse
from src.services.redemption_service import RedemptionService

router = APIRouter(prefix="/rewards", tags=["Rewards Catalog"])

@router.get("", response_model=List[RewardItemResponse])
def list_rewards(
    conn: sqlite3.Connection = Depends(get_db),
    redemption_svc: RedemptionService = Depends(get_redemption_service)
):
    """Retrieve catalog of active reward items and point costs."""
    return redemption_svc.list_rewards(conn)
