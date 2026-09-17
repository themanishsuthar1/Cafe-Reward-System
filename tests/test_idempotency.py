import pytest
import uuid
from src.storage.database import get_connection, init_db
from src.services.lookup_service import MemberLookupService
from src.services.purchase_service import PurchaseService
from src.services.redemption_service import RedemptionService

@pytest.fixture
def db_conn(tmp_path):
    db_file = str(tmp_path / "test_idempotency.db")
    init_db(db_file)
    conn = get_connection(db_file)
    yield conn
    conn.close()

def test_purchase_idempotency(db_conn):
    lookup_svc = MemberLookupService(":memory:")
    purchase_svc = PurchaseService(":memory:")
    
    # Create member
    member = lookup_svc.register_member(db_conn, "Idempotency Test", "555-001-0001")
    member_id = member["id"]

    idempotency_key = f"idem_purch_{uuid.uuid4().hex}"

    # First attempt
    res1 = purchase_svc.record_purchase(
        conn=db_conn,
        member_id=member_id,
        amount_spent=100.0,
        idempotency_key=idempotency_key,
        terminal_id="TERM_1"
    )

    assert res1["status"] == "SUCCESS"
    assert res1["points_earned"] == 100
    assert res1["current_points"] == 100

    # Second attempt with SAME idempotency key
    res2 = purchase_svc.record_purchase(
        conn=db_conn,
        member_id=member_id,
        amount_spent=100.0,
        idempotency_key=idempotency_key,
        terminal_id="TERM_1"
    )

    # Must return exact same result without duplicating points or ledger rows
    assert res2 == res1
    assert res2["current_points"] == 100

    # Verify balance in DB is still 100, not 200
    m_info = lookup_svc.find_by_phone(db_conn, "555-001-0001")
    assert m_info["current_points"] == 100
    assert m_info["lifetime_points"] == 100

def test_redemption_idempotency(db_conn):
    lookup_svc = MemberLookupService(":memory:")
    purchase_svc = PurchaseService(":memory:")
    redemption_svc = RedemptionService(":memory:")

    member = lookup_svc.register_member(db_conn, "Redeem Idem Test", "555-001-0002")
    member_id = member["id"]

    # Fund account with 200 points
    purchase_svc.record_purchase(
        conn=db_conn,
        member_id=member_id,
        amount_spent=200.0,
        idempotency_key=f"fund_{uuid.uuid4().hex}"
    )

    idempotency_key = f"idem_redeem_{uuid.uuid4().hex}"

    # First redemption (Espresso cost 100)
    res1 = redemption_svc.redeem_reward(
        conn=db_conn,
        member_id=member_id,
        reward_id="rw_espresso",
        idempotency_key=idempotency_key
    )

    assert res1["status"] == "SUCCESS"
    assert res1["points_redeemed"] == 100
    assert res1["current_points"] == 100

    # Retry same redemption with same key
    res2 = redemption_svc.redeem_reward(
        conn=db_conn,
        member_id=member_id,
        reward_id="rw_espresso",
        idempotency_key=idempotency_key
    )

    assert res2 == res1
    assert res2["current_points"] == 100

    # Balance should still be 100
    m_info = lookup_svc.find_by_phone(db_conn, "555-001-0002")
    assert m_info["current_points"] == 100
