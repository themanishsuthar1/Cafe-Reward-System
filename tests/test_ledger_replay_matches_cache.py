import pytest
import uuid
import random
from src.storage.database import get_connection, init_db
from src.services.lookup_service import MemberLookupService
from src.services.purchase_service import PurchaseService
from src.services.redemption_service import RedemptionService
from src.services.reconcile_service import reconcile_member_balance
from src.storage.repository import InsufficientPointsError

def test_ledger_replay_matches_cache(tmp_path):
    db_file = str(tmp_path / "test_reconcile.db")
    init_db(db_file)
    
    conn = get_connection(db_file)
    lookup_svc = MemberLookupService(db_file)
    purchase_svc = PurchaseService(db_file)
    redemption_svc = RedemptionService(db_file)

    # Register member
    member = lookup_svc.register_member(conn, "Reconciliation Proof Member", "555-777-8888")
    member_id = member["id"]

    # Execute a sequence of 20 random operations (purchases and redemptions)
    random.seed(42)
    rewards = ["rw_espresso", "rw_cappuccino", "rw_pastry", "rw_bagel_sandwich", "rw_tumbler"]

    for i in range(25):
        action = random.choice(["PURCHASE", "PURCHASE", "REDEMPTION"])
        
        if action == "PURCHASE":
            amount = round(random.uniform(5.0, 500.0), 2)
            idempotency_key = f"tx_seq_{i}_{uuid.uuid4().hex}"
            purchase_svc.record_purchase(
                conn=conn,
                member_id=member_id,
                amount_spent=amount,
                idempotency_key=idempotency_key,
                terminal_id=f"TERM_{random.randint(1, 4)}"
            )
        else: # REDEMPTION
            reward_id = random.choice(rewards)
            idempotency_key = f"tx_seq_{i}_{uuid.uuid4().hex}"
            try:
                redemption_svc.redeem_reward(
                    conn=conn,
                    member_id=member_id,
                    reward_id=reward_id,
                    idempotency_key=idempotency_key,
                    terminal_id=f"TERM_{random.randint(1, 4)}"
                )
            except InsufficientPointsError:
                # Expected when balance is too low for chosen reward
                pass

    # Replay full transaction history ledger and compare against MemberBalanceCache
    reconciliation = reconcile_member_balance(conn, member_id)

    # ASSERTIONS FOR PROOF OF CORRECTNESS
    assert reconciliation["is_reconciled"] is True
    assert reconciliation["current_balance_discrepancy"] == 0
    assert reconciliation["lifetime_balance_discrepancy"] == 0
    assert reconciliation["cached_current_points"] == reconciliation["recalculated_current_points"]
    assert reconciliation["cached_lifetime_points"] == reconciliation["recalculated_lifetime_points"]

    conn.close()
