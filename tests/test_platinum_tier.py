import pytest
import uuid
from src.domain.tier import Tier, evaluate_tier, get_tier_multiplier, next_tier_info
from src.storage.database import get_connection, init_db
from src.services.lookup_service import MemberLookupService
from src.services.purchase_service import PurchaseService

def test_platinum_tier_domain_evaluation():
    # Base: < 500, Silver: 500-1499, Gold: 1500-4999, Platinum: >= 5000
    assert evaluate_tier(4999) == Tier.GOLD
    assert evaluate_tier(5000) == Tier.PLATINUM
    assert evaluate_tier(10000) == Tier.PLATINUM

    assert get_tier_multiplier(Tier.PLATINUM) == 2.0

    gold_info = next_tier_info(3000)
    assert gold_info["current_tier"] == Tier.GOLD
    assert gold_info["next_tier"] == Tier.PLATINUM
    assert gold_info["points_needed"] == 2000

    plat_info = next_tier_info(6000)
    assert plat_info["current_tier"] == Tier.PLATINUM
    assert plat_info["next_tier"] is None
    assert plat_info["points_needed"] == 0

def test_platinum_tier_purchase_upgrade(tmp_path):
    db_file = str(tmp_path / "test_plat.db")
    init_db(db_file)
    conn = get_connection(db_file)

    lookup_svc = MemberLookupService(db_file)
    purchase_svc = PurchaseService(db_file)

    member = lookup_svc.register_member(conn, "Platinum Member Test", "555-444-0000")
    member_id = member["id"]

    # Purchase $3334 at Base tier 1.0x -> earns 3334 points -> upgrades to GOLD (3334 >= 1500)
    res1 = purchase_svc.record_purchase(
        conn=conn,
        member_id=member_id,
        amount_spent=3334.0,
        idempotency_key=f"plat_1_{uuid.uuid4().hex}"
    )
    assert res1["new_tier"] == "GOLD"
    assert res1["lifetime_points"] == 3334

    # Second purchase $1200 at Gold tier 1.5x -> earns 1800 points -> total 3334 + 1800 = 5134 points >= 5000 -> upgrades to PLATINUM!
    res2 = purchase_svc.record_purchase(
        conn=conn,
        member_id=member_id,
        amount_spent=1200.0,
        idempotency_key=f"plat_2_{uuid.uuid4().hex}"
    )
    assert res2["new_tier"] == "PLATINUM"
    assert res2["tier_upgraded"] is True
    assert res2["lifetime_points"] == 5134

    # Third purchase $100.0 at Platinum tier 2.0x -> earns 200 points!
    res3 = purchase_svc.record_purchase(
        conn=conn,
        member_id=member_id,
        amount_spent=100.0,
        idempotency_key=f"plat_3_{uuid.uuid4().hex}"
    )
    assert res3["tier_at_time"] == "PLATINUM"
    assert res3["points_earned"] == 200

    conn.close()
