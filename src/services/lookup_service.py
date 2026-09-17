from typing import Optional, List, Dict, Any, Tuple
import sqlite3
from src.storage.repository import Repository
from src.domain.tier import next_tier_info, get_tier_multiplier

class MemberLookupService:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def register_member(self, conn: sqlite3.Connection, name: str, phone: str) -> Dict[str, Any]:
        repo = Repository(conn)
        return repo.create_member(name=name, phone=phone)

    def find_by_phone(self, conn: sqlite3.Connection, phone: str) -> Optional[Dict[str, Any]]:
        repo = Repository(conn)
        member = repo.find_member_by_phone(phone)
        if not member:
            return None
        
        tier_progress = next_tier_info(member["lifetime_points"])
        multiplier = get_tier_multiplier(member["tier"])
        member.update({
            "tier_progress": tier_progress,
            "points_multiplier": multiplier
        })
        return member

    def search_members(self, conn: sqlite3.Connection, query: str) -> List[Dict[str, Any]]:
        repo = Repository(conn)
        members = repo.search_members(query)
        for m in members:
            m["tier_progress"] = next_tier_info(m["lifetime_points"])
            m["points_multiplier"] = get_tier_multiplier(m["tier"])
        return members

    def search_members_paginated(
        self, conn: sqlite3.Connection, query: str, page: int = 1, size: int = 10
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Returns (items_with_tier_info, total_count) for paginated member search."""
        repo = Repository(conn)
        members, total = repo.search_members_paginated(query, page=page, size=size)
        for m in members:
            m["tier_progress"] = next_tier_info(m["lifetime_points"])
            m["points_multiplier"] = get_tier_multiplier(m["tier"])
        return members, total

    def get_ledger_history(self, conn: sqlite3.Connection, member_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        repo = Repository(conn)
        return repo.get_member_transactions(member_id, limit=limit)

    def get_ledger_history_paginated(
        self, conn: sqlite3.Connection, member_id: str, page: int = 1, size: int = 10
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Returns (items, total_count) for paginated ledger history."""
        repo = Repository(conn)
        return repo.get_member_transactions_paginated(member_id, page=page, size=size)

