import pytest
import uuid
from datetime import datetime, timezone, timedelta
from src.storage.database import get_connection, init_db
from src.services.lookup_service import MemberLookupService
from src.services.purchase_service import PurchaseService
from src.services.clock_service import ClockService

def test_90_day_point_expiration(tmp_path):
    db_file = str(tmp_path / "test_expiration.db")
    init_db(db_file)
    conn = get_connection(db_file)

    lookup_svc = MemberLookupService(db_file)
    purchase_svc = PurchaseService(db_file)
    clock_svc = ClockService(db_file)

    member = lookup_svc.register_member(conn, "Expiration Test Member", "555-888-1111")
    member_id = member["id"]

    # Day 0: Member spends $100 -> earns 100 points
    now_base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    clock_svc.set_clock_time(now_base)

    purchase_svc.record_purchase(
        conn=conn,
        member_id=member_id,
        amount_spent=100.0,
        idempotency_key=f"exp_test_p1_{uuid.uuid4().hex}",
        created_at=now_base.isoformat()
    )


    m_info = lookup_svc.find_by_phone(conn, "555-888-1111")
    assert m_info["current_points"] == 100

    # Advance clock by 45 days (Day 45) -> No points should expire yet
    day_45 = now_base + timedelta(days=45)
    res_45 = clock_svc.run_expiration_sweep(conn, as_of_time=day_45)
    assert res_45["members_expired_count"] == 0

    m_info_45 = lookup_svc.find_by_phone(conn, "555-888-1111")
    assert m_info_45["current_points"] == 100

    # Advance clock by 91 days (Day 91) -> The 100 points earned on Day 0 are > 90 days old -> Expire!
    day_91 = now_base + timedelta(days=91)
    res_91 = clock_svc.run_expiration_sweep(conn, as_of_time=day_91)
    assert res_91["members_expired_count"] == 1
    assert res_91["total_points_expired"] == 100

    m_info_91 = lookup_svc.find_by_phone(conn, "555-888-1111")
    # Current points should drop to 0, while lifetime points remains 100!
    assert m_info_91["current_points"] == 0
    assert m_info_91["lifetime_points"] == 100

    # Verify ledger history contains EXPIRATION transaction
    history = lookup_svc.get_ledger_history(conn, member_id)
    exp_tx = [t for t in history if t["type"] == "EXPIRATION"]
    assert len(exp_tx) == 1
    assert exp_tx[0]["points_delta"] == -100

    conn.close()
