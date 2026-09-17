import sys
import argparse
import sqlite3
from src.storage.database import get_connection, init_db, DEFAULT_DB_PATH
from src.services.reconcile_service import reconcile_member_balance

def main():
    parser = argparse.ArgumentParser(description="Rebuild and verify member balance from immutable transaction ledger replay.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="Path to SQLite database file")
    parser.add_argument("--member-id", help="Specific Member ID to reconcile")
    parser.add_argument("--all", action="store_true", help="Reconcile all members in database")

    args = parser.parse_args()

    init_db(args.db)
    conn = get_connection(args.db)

    try:
        cursor = conn.cursor()
        if args.member_id:
            member_ids = [args.member_id]
        else:
            cursor.execute("SELECT id FROM members;")
            member_ids = [row["id"] for row in cursor.fetchall()]

        if not member_ids:
            print("No members found in database.")
            return

        print(f"=== Running Ledger Reconciliation Replay Audit for {len(member_ids)} Member(s) ===")
        discrepancies_found = 0

        for m_id in member_ids:
            res = reconcile_member_balance(conn, m_id)
            if res["is_reconciled"]:
                print(f"[OK] Member {m_id}: Current Balance = {res['recalculated_current_points']} pts | Lifetime = {res['recalculated_lifetime_points']} pts")
            else:
                discrepancies_found += 1
                print(f"[FAIL] Member {m_id}: DISCREPANCY DETECTED!")
                print(f"       Cached Current: {res['cached_current_points']} vs Replayed: {res['recalculated_current_points']}")
                print(f"       Cached Lifetime: {res['cached_lifetime_points']} vs Replayed: {res['recalculated_lifetime_points']}")

        print("\n=======================================================")
        if discrepancies_found == 0:
            print("ALL MEMBERS 100% RECONCILED. ZERO BALANCE DRIFT DETECTED.")
            sys.exit(0)
        else:
            print(f"AUDIT FAILED: {discrepancies_found} member(s) have balance discrepancies!")
            sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
