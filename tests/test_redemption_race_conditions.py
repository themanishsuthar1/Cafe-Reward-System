import pytest
import uuid
import concurrent.futures
from src.storage.database import get_connection, init_db
from src.services.lookup_service import MemberLookupService
from src.services.purchase_service import PurchaseService
from src.services.redemption_service import RedemptionService
from src.storage.repository import InsufficientPointsError

def test_concurrent_redemptions(tmp_path):
    db_file = str(tmp_path / "test_race.db")
    init_db(db_file)
    
    conn_setup = get_connection(db_file)
    lookup_svc = MemberLookupService(db_file)
    purchase_svc = PurchaseService(db_file)
    redemption_svc = RedemptionService(db_file)

    # Register member and give exactly 150 points (enough for 1 Cappuccino of 150 pts)
    member = lookup_svc.register_member(conn_setup, "Race Test Member", "555-999-0000")
    member_id = member["id"]

    purchase_svc.record_purchase(
        conn=conn_setup,
        member_id=member_id,
        amount_spent=150.0,
        idempotency_key=f"init_fund_{uuid.uuid4().hex}"
    )
    conn_setup.close()

    # Attempt two SIMULTANEOUS redemptions of 150 points each from two different worker threads/terminals
    def worker_attempt_redemption(terminal_name: str):
        conn = get_connection(db_file)
        try:
            res = redemption_svc.redeem_reward(
                conn=conn,
                member_id=member_id,
                reward_id="rw_cappuccino", # Costs 150 points
                idempotency_key=f"idem_race_{terminal_name}_{uuid.uuid4().hex}",
                terminal_id=terminal_name
            )
            conn.close()
            return ("SUCCESS", res)
        except InsufficientPointsError as e:
            conn.close()
            return ("INSUFFICIENT_POINTS", str(e))
        except Exception as e:
            conn.close()
            return ("ERROR", str(e))

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(worker_attempt_redemption, "TERM_A")
        f2 = executor.submit(worker_attempt_redemption, "TERM_B")
        
        r1 = f1.result()
        r2 = f2.result()

    results = [r1[0], r2[0]]

    # EXPLICIT ASSERTION: Exactly one thread succeeded, and exactly one got INSUFFICIENT_POINTS
    assert results.count("SUCCESS") == 1
    assert results.count("INSUFFICIENT_POINTS") == 1

    # Verify final balance in database is exactly 0
    conn_verify = get_connection(db_file)
    final_info = lookup_svc.find_by_phone(conn_verify, "555-999-0000")
    assert final_info["current_points"] == 0
    assert final_info["lifetime_points"] == 150
    conn_verify.close()
