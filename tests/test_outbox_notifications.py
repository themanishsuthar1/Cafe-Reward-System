import pytest
import uuid
from src.storage.database import get_connection, init_db
from src.services.lookup_service import MemberLookupService
from src.services.purchase_service import PurchaseService
from src.services.outbox_service import OutboxService

def test_outbox_tier_upgrade_notification(tmp_path):
    db_file = str(tmp_path / "test_outbox.db")
    init_db(db_file)
    conn = get_connection(db_file)

    lookup_svc = MemberLookupService(db_file)
    purchase_svc = PurchaseService(db_file)
    outbox_svc = OutboxService(db_file)

    member = lookup_svc.register_member(conn, "Outbox Test Member", "555-333-2222")
    member_id = member["id"]

    # Initial outbox should be empty
    initial_events = outbox_svc.list_events(conn)
    assert len(initial_events) == 0

    # Purchase $600 at Base tier (1.0x) -> 600 points >= 500 threshold -> Upgrades to SILVER!
    purchase_svc.record_purchase(
        conn=conn,
        member_id=member_id,
        amount_spent=600.0,
        idempotency_key=f"outbox_p1_{uuid.uuid4().hex}"
    )

    # Verify TIER_UPGRADED event was written to Outbox table in the SAME atomic DB transaction!
    pending_events = outbox_svc.list_events(conn, status="PENDING")
    assert len(pending_events) == 1

    event = pending_events[0]
    assert event["aggregate_id"] == member_id
    assert event["event_type"] == "TIER_UPGRADED"
    assert event["payload"]["old_tier"] == "BASE"
    assert event["payload"]["new_tier"] == "SILVER"
    assert event["payload"]["lifetime_points"] == 600

    # Simulate Notification Service processing the outbox event
    proc_res = outbox_svc.process_pending_events(conn)
    assert proc_res["processed_count"] == 1

    # Verify outbox event is now PROCESSED
    remaining_pending = outbox_svc.list_events(conn, status="PENDING")
    assert len(remaining_pending) == 0

    processed_events = outbox_svc.list_events(conn, status="PROCESSED")
    assert len(processed_events) == 1

    conn.close()
