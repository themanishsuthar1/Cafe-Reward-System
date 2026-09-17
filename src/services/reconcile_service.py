import sqlite3
from typing import Dict, Any
from src.storage.repository import Repository
from src.logger import get_logger

logger = get_logger("services.reconcile")

def reconcile_member_balance(conn: sqlite3.Connection, member_id: str) -> Dict[str, Any]:
    """
    Reconstructs member current points and lifetime points by replaying the complete ledger history.
    Asserts equality with MemberBalanceCache.
    """
    repo = Repository(conn)
    cache = repo.get_member_balance_cache(member_id)

    recalculated_current, recalculated_lifetime = repo.compute_ledger_replay_balance(member_id)

    cached_current = cache["current_points"]
    cached_lifetime = cache["lifetime_points"]

    is_current_equal = (recalculated_current == cached_current)
    is_lifetime_equal = (recalculated_lifetime == cached_lifetime)
    is_reconciled = is_current_equal and is_lifetime_equal

    if is_reconciled:
        logger.info(f"Reconciliation PASSED for member '{member_id}': replayed SUM(points_delta)={recalculated_current} matches cache.")
    else:
        logger.error(f"Reconciliation DISCREPANCY for member '{member_id}': cached={cached_current} vs replayed={recalculated_current}!")

    return {
        "member_id": member_id,
        "is_reconciled": is_reconciled,
        "cached_current_points": cached_current,
        "recalculated_current_points": recalculated_current,
        "cached_lifetime_points": cached_lifetime,
        "recalculated_lifetime_points": recalculated_lifetime,
        "current_balance_discrepancy": recalculated_current - cached_current,
        "lifetime_balance_discrepancy": recalculated_lifetime - cached_lifetime
    }

