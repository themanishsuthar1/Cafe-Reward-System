from fastapi import APIRouter, HTTPException, Depends
import sqlite3

from src.api.deps import get_db, get_lookup_service, get_current_user
from src.api.schemas.member import CreateMemberRequest
from src.services.lookup_service import MemberLookupService

router = APIRouter(prefix="/members", tags=["Members"])


@router.post("", status_code=201)
def create_member(
    req: CreateMemberRequest,
    conn: sqlite3.Connection = Depends(get_db),
    lookup_svc: MemberLookupService = Depends(get_lookup_service),
    _: dict = Depends(get_current_user)
):
    """Register a new loyalty member. Requires staff authentication."""
    try:
        return lookup_svc.register_member(conn, name=req.name, phone=req.phone)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
