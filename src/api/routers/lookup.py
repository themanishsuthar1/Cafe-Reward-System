from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any
import sqlite3

from src.api.deps import get_db, get_lookup_service, get_current_user
from src.api.schemas.pagination import PaginatedResponse
from src.services.lookup_service import MemberLookupService
from src.services.reconcile_service import reconcile_member_balance

router = APIRouter(prefix="/members", tags=["Lookup & Audit"])


@router.get("/search", response_model=PaginatedResponse)
def search_members(
    query: str = Query(..., min_length=1, description="Phone number or name query"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    size: int = Query(10, ge=1, le=100, description="Items per page (max 100)"),
    conn: sqlite3.Connection = Depends(get_db),
    lookup_svc: MemberLookupService = Depends(get_lookup_service),
    _: dict = Depends(get_current_user)
):
    """
    Search members by phone (exact/prefix) or name with typeahead optimization.
    Supports pagination via `page` and `size` query parameters.
    Returns total records, total pages, current page, and page size.
    Requires staff authentication.
    """
    members, total = lookup_svc.search_members_paginated(conn, query=query, page=page, size=size)
    return PaginatedResponse.build(items=members, total=total, page=page, size=size)


@router.get("/phone/{phone}")
def get_member_by_phone(
    phone: str,
    conn: sqlite3.Connection = Depends(get_db),
    lookup_svc: MemberLookupService = Depends(get_lookup_service),
    _: dict = Depends(get_current_user)
):
    """Retrieve full member details, live cached balance, tier, and next-tier progress. Requires staff authentication."""
    member = lookup_svc.find_by_phone(conn, phone=phone)
    if not member:
        raise HTTPException(status_code=404, detail=f"Member with phone '{phone}' not found.")
    return member


@router.get("/{member_id}/ledger", response_model=PaginatedResponse)
def get_member_ledger(
    member_id: str,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    size: int = Query(10, ge=1, le=200, description="Items per page (max 200)"),
    conn: sqlite3.Connection = Depends(get_db),
    lookup_svc: MemberLookupService = Depends(get_lookup_service),
    _: dict = Depends(get_current_user)
):
    """
    Retrieve paginated transaction ledger history for a member.
    Ordered by most recent first. Supports `page` and `size` query parameters.
    Requires staff authentication.
    """
    items, total = lookup_svc.get_ledger_history_paginated(conn, member_id=member_id, page=page, size=size)
    return PaginatedResponse.build(items=items, total=total, page=page, size=size)


@router.get("/{member_id}/reconcile")
def reconcile_member(
    member_id: str,
    conn: sqlite3.Connection = Depends(get_db),
    _: dict = Depends(get_current_user)
):
    """
    Audit endpoint: Reconstructs balance from complete transaction ledger replay
    and verifies equality against cached balance. Requires staff authentication.
    """
    try:
        return reconcile_member_balance(conn, member_id=member_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
