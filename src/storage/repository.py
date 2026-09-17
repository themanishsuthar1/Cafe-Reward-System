import json
import uuid
import sqlite3
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple

from src.storage.models import (
    MemberModel,
    TransactionModel,
    RewardItemModel,
    MemberBalanceCacheModel,
)
from src.domain.member import normalize_phone
from src.domain.tier import evaluate_tier, get_tier_multiplier, Tier
from src.logger import get_logger

logger = get_logger("storage.repository")


class InsufficientPointsError(Exception):
    """Raised when a redemption attempt exceeds current points balance."""
    def __init__(self, current_points: int, required_points: int):
        self.current_points = current_points
        self.required_points = required_points
        super().__init__(f"Insufficient points: available {current_points}, required {required_points}.")

class IdempotencyDuplicateError(Exception):
    """Raised if an idempotency key was previously processed."""
    def __init__(self, response_data: Dict[str, Any]):
        self.response_data = response_data
        super().__init__("Idempotent request already processed.")

class MemberNotFoundError(Exception):
    pass

class RewardItemNotFoundError(Exception):
    pass

class Repository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_idempotency_record(self, key: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT response_json FROM idempotency_records WHERE idempotency_key = ?;", (key,))
        row = cursor.fetchone()
        if row:
            return json.loads(row["response_json"])
        return None

    def create_member(self, name: str, phone: str) -> Dict[str, Any]:
        normalized = normalize_phone(phone)
        member_id = f"mem_{uuid.uuid4().hex[:12]}"
        now_str = datetime.now(timezone.utc).isoformat()
        
        # SQLite transaction block
        self.conn.execute("BEGIN IMMEDIATE;")
        try:
            # Check unique phone
            cursor = self.conn.cursor()
            cursor.execute("SELECT id FROM members WHERE phone = ?;", (normalized,))
            if cursor.fetchone():
                self.conn.rollback()
                raise ValueError(f"Member with phone number '{phone}' already exists.")
            
            cursor.execute(
                "INSERT INTO members (id, name, phone, tier, join_date) VALUES (?, ?, ?, 'BASE', ?);",
                (member_id, name, normalized, now_str)
            )
            cursor.execute(
                "INSERT INTO member_balance_cache (member_id, current_points, lifetime_points, current_tier, last_transaction_id) VALUES (?, 0, 0, 'BASE', NULL);",
                (member_id,)
            )
            self.conn.commit()
            return {
                "id": member_id,
                "name": name,
                "phone": normalized,
                "tier": "BASE",
                "join_date": now_str,
                "current_points": 0,
                "lifetime_points": 0
            }
        except Exception:
            self.conn.rollback()
            raise

    def find_member_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        try:
            normalized = normalize_phone(phone)
        except ValueError:
            return None
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT m.id, m.name, m.phone, m.tier, m.join_date,
                   c.current_points, c.lifetime_points, c.last_transaction_id
            FROM members m
            JOIN member_balance_cache c ON m.id = c.member_id
            WHERE m.phone = ?;
        """, (normalized,))
        row = cursor.fetchone()
        if not row:
            return None
        return dict(row)

    def search_members(self, query: str) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        raw_digits = "".join(filter(str.isdigit, query))
        
        if raw_digits:
            sql = """
                SELECT m.id, m.name, m.phone, m.tier, m.join_date,
                       c.current_points, c.lifetime_points
                FROM members m
                JOIN member_balance_cache c ON m.id = c.member_id
                WHERE m.phone LIKE ? OR m.name LIKE ?
                ORDER BY m.name ASC LIMIT 20;
            """
            cursor.execute(sql, (f"%{raw_digits}%", f"%{query}%"))
        else:
            sql = """
                SELECT m.id, m.name, m.phone, m.tier, m.join_date,
                       c.current_points, c.lifetime_points
                FROM members m
                JOIN member_balance_cache c ON m.id = c.member_id
                WHERE m.name LIKE ?
                ORDER BY m.name ASC LIMIT 20;
            """
            cursor.execute(sql, (f"%{query}%",))
        
        return [dict(row) for row in cursor.fetchall()]

    def search_members_paginated(
        self, query: str, page: int = 1, size: int = 10
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Paginated member search. Returns (items, total_count).
        page is 1-indexed, size is items-per-page.
        """
        cursor = self.conn.cursor()
        offset = (page - 1) * size
        raw_digits = "".join(filter(str.isdigit, query))

        if raw_digits:
            where_clause = "WHERE m.phone LIKE ? OR m.name LIKE ?"
            params_data = (f"%{raw_digits}%", f"%{query}%", size, offset)
            params_count = (f"%{raw_digits}%", f"%{query}%")
        else:
            where_clause = "WHERE m.name LIKE ?"
            params_data = (f"%{query}%", size, offset)
            params_count = (f"%{query}%",)

        # Count total matching records
        cursor.execute(f"""
            SELECT COUNT(*) as total
            FROM members m
            JOIN member_balance_cache c ON m.id = c.member_id
            {where_clause};
        """, params_count)
        total = cursor.fetchone()["total"]

        # Fetch page
        cursor.execute(f"""
            SELECT m.id, m.name, m.phone, m.tier, m.join_date,
                   c.current_points, c.lifetime_points
            FROM members m
            JOIN member_balance_cache c ON m.id = c.member_id
            {where_clause}
            ORDER BY m.name ASC
            LIMIT ? OFFSET ?;
        """, params_data)

        items = [dict(row) for row in cursor.fetchall()]
        return items, total


    def get_member_balance_cache(self, member_id: str) -> Dict[str, Any]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT member_id, current_points, lifetime_points, current_tier, last_transaction_id
            FROM member_balance_cache WHERE member_id = ?;
        """, (member_id,))
        row = cursor.fetchone()
        if not row:
            raise MemberNotFoundError(f"Member with ID '{member_id}' not found.")
        return dict(row)

    def get_reward_item(self, reward_id: str) -> Dict[str, Any]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, points_cost, active FROM reward_items WHERE id = ? AND active = 1;", (reward_id,))
        row = cursor.fetchone()
        if not row:
            raise RewardItemNotFoundError(f"Reward item '{reward_id}' not found or inactive.")
        return dict(row)

    def list_active_rewards(self) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, points_cost, active FROM reward_items WHERE active = 1 ORDER BY points_cost ASC;")
        return [dict(row) for row in cursor.fetchall()]

    def record_purchase_transaction(
        self,
        member_id: str,
        amount_spent: float,
        points_delta: int,
        idempotency_key: str,
        staff_id: Optional[str] = None,
        terminal_id: Optional[str] = None,
        created_at: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes purchase transaction inside a strict atomic database transaction:
        1. Checks idempotency key.
        2. Locks member balance row (BEGIN IMMEDIATE).
        3. Appends transaction to ledger.
        4. Re-evaluates tier & updates member balance cache + member tier atomically.
        5. Saves idempotency record.
        """
        # 1. Quick idempotency check
        existing = self.get_idempotency_record(idempotency_key)
        if existing:
            logger.info(f"Idempotency match found for purchase key '{idempotency_key}'. Returning stored response.")
            return existing

        now_str = created_at or datetime.now(timezone.utc).isoformat()
        tx_id = f"tx_{uuid.uuid4().hex[:12]}"


        # Begin exclusive write transaction
        self.conn.execute("BEGIN IMMEDIATE;")
        try:
            # Re-check idempotency under transaction lock
            cursor = self.conn.cursor()
            cursor.execute("SELECT response_json FROM idempotency_records WHERE idempotency_key = ?;", (idempotency_key,))
            existing_row = cursor.fetchone()
            if existing_row:
                self.conn.rollback()
                logger.info(f"Idempotency match under lock for key '{idempotency_key}'. Returning stored response.")
                return json.loads(existing_row["response_json"])


            # Fetch current balance cache & member info
            cursor.execute("""
                SELECT m.id, m.name, m.tier as member_tier,
                       c.current_points, c.lifetime_points, c.current_tier as cache_tier
                FROM members m
                JOIN member_balance_cache c ON m.id = c.member_id
                WHERE m.id = ?;
            """, (member_id,))
            row = cursor.fetchone()
            if not row:
                self.conn.rollback()
                raise MemberNotFoundError(f"Member with ID '{member_id}' not found.")

            current_points = row["current_points"]
            current_lifetime = row["lifetime_points"]
            tier_at_time = row["cache_tier"]

            new_points = current_points + points_delta
            new_lifetime = current_lifetime + points_delta
            new_tier = evaluate_tier(new_lifetime).value

            # Insert transaction ledger row
            cursor.execute("""
                INSERT INTO transactions (
                    id, member_id, type, amount_spent, points_delta,
                    tier_at_time, idempotency_key, created_at, staff_id, terminal_id
                ) VALUES (?, ?, 'PURCHASE', ?, ?, ?, ?, ?, ?, ?);
            """, (
                tx_id, member_id, amount_spent, points_delta,
                tier_at_time, idempotency_key, now_str, staff_id, terminal_id
            ))

            # Update cache
            cursor.execute("""
                UPDATE member_balance_cache
                SET current_points = ?, lifetime_points = ?, current_tier = ?, last_transaction_id = ?
                WHERE member_id = ?;
            """, (new_points, new_lifetime, new_tier, tx_id, member_id))

            # Update member table tier & emit outbox event if changed
            if new_tier != row["member_tier"]:
                cursor.execute("UPDATE members SET tier = ? WHERE id = ?;", (new_tier, member_id))
                
                # Transactional Outbox Pattern: Emit TIER_UPGRADED event in same DB Tx
                outbox_id = f"out_{uuid.uuid4().hex[:12]}"
                event_payload = {
                    "event_type": "TIER_UPGRADED",
                    "member_id": member_id,
                    "old_tier": tier_at_time,
                    "new_tier": new_tier,
                    "lifetime_points": new_lifetime,
                    "timestamp": now_str
                }
                cursor.execute("""
                    INSERT INTO outbox (id, aggregate_type, aggregate_id, event_type, payload_json, status, created_at)
                    VALUES (?, 'MEMBER', ?, 'TIER_UPGRADED', ?, 'PENDING', ?);
                """, (outbox_id, member_id, json.dumps(event_payload), now_str))
                logger.info(f"Emitted TIER_UPGRADED event to Outbox: member='{member_id}', '{tier_at_time}' -> '{new_tier}'.")


            response_payload = {
                "status": "SUCCESS",
                "transaction_id": tx_id,
                "member_id": member_id,
                "type": "PURCHASE",
                "amount_spent": amount_spent,
                "points_earned": points_delta,
                "tier_at_time": tier_at_time,
                "new_tier": new_tier,
                "tier_upgraded": (new_tier != tier_at_time),
                "current_points": new_points,
                "lifetime_points": new_lifetime,
                "idempotency_key": idempotency_key,
                "created_at": now_str
            }

            # Save idempotency record
            cursor.execute("""
                INSERT INTO idempotency_records (idempotency_key, response_json, created_at)
                VALUES (?, ?, ?);
            """, (idempotency_key, json.dumps(response_payload), now_str))

            self.conn.commit()
            logger.info(f"Purchase recorded successfully: member='{member_id}', tx='{tx_id}', spent=${amount_spent:.2f}, +{points_delta} pts, new_balance={new_points} pts (tier={new_tier}).")
            return response_payload
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to record purchase transaction for member '{member_id}': {e}", exc_info=True)
            raise


    def record_redemption_transaction(
        self,
        member_id: str,
        reward_id: str,
        idempotency_key: str,
        staff_id: Optional[str] = None,
        terminal_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes redemption transaction inside a strict atomic database transaction:
        1. Checks idempotency key.
        2. Locks member balance row (BEGIN IMMEDIATE).
        3. Re-verifies live server balance under lock (points >= cost).
        4. Appends REDEMPTION transaction to ledger.
        5. Updates member balance cache.
        6. Saves idempotency record.
        """
        existing = self.get_idempotency_record(idempotency_key)
        if existing:
            return existing

        now_str = datetime.now(timezone.utc).isoformat()
        tx_id = f"tx_{uuid.uuid4().hex[:12]}"

        self.conn.execute("BEGIN IMMEDIATE;")
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT response_json FROM idempotency_records WHERE idempotency_key = ?;", (idempotency_key,))
            existing_row = cursor.fetchone()
            if existing_row:
                self.conn.rollback()
                return json.loads(existing_row["response_json"])

            # Get reward item
            cursor.execute("SELECT id, name, points_cost FROM reward_items WHERE id = ? AND active = 1;", (reward_id,))
            reward = cursor.fetchone()
            if not reward:
                self.conn.rollback()
                raise RewardItemNotFoundError(f"Reward item '{reward_id}' not found or inactive.")

            reward_name = reward["name"]
            points_cost = reward["points_cost"]

            # Lock and fetch live balance
            cursor.execute("""
                SELECT m.id, m.tier as member_tier,
                       c.current_points, c.lifetime_points, c.current_tier as cache_tier
                FROM members m
                JOIN member_balance_cache c ON m.id = c.member_id
                WHERE m.id = ?;
            """, (member_id,))
            row = cursor.fetchone()
            if not row:
                self.conn.rollback()
                raise MemberNotFoundError(f"Member with ID '{member_id}' not found.")

            current_points = row["current_points"]
            tier_at_time = row["cache_tier"]

            # Server-side live balance validation under lock
            if current_points < points_cost:
                self.conn.rollback()
                logger.warning(f"Redemption rejected for member '{member_id}': available={current_points} pts, required={points_cost} pts for reward '{reward_name}'.")
                raise InsufficientPointsError(current_points=current_points, required_points=points_cost)

            new_points = current_points - points_cost
            points_delta = -points_cost

            # Insert transaction ledger row
            cursor.execute("""
                INSERT INTO transactions (
                    id, member_id, type, amount_spent, points_delta,
                    tier_at_time, idempotency_key, created_at, staff_id, terminal_id
                ) VALUES (?, ?, 'REDEMPTION', 0.0, ?, ?, ?, ?, ?, ?);
            """, (
                tx_id, member_id, points_delta,
                tier_at_time, idempotency_key, now_str, staff_id, terminal_id
            ))

            # Update cache (lifetime points DOES NOT decrease on redemption)
            cursor.execute("""
                UPDATE member_balance_cache
                SET current_points = ?, last_transaction_id = ?
                WHERE member_id = ?;
            """, (new_points, tx_id, member_id))

            response_payload = {
                "status": "SUCCESS",
                "transaction_id": tx_id,
                "member_id": member_id,
                "type": "REDEMPTION",
                "reward_id": reward_id,
                "reward_name": reward_name,
                "points_redeemed": points_cost,
                "tier_at_time": tier_at_time,
                "current_points": new_points,
                "lifetime_points": row["lifetime_points"],
                "idempotency_key": idempotency_key,
                "created_at": now_str
            }

            cursor.execute("""
                INSERT INTO idempotency_records (idempotency_key, response_json, created_at)
                VALUES (?, ?, ?);
            """, (idempotency_key, json.dumps(response_payload), now_str))

            self.conn.commit()
            logger.info(f"Redemption successful: member='{member_id}', reward='{reward_name}', -{points_cost} pts, remaining_balance={new_points} pts.")
            return response_payload
        except InsufficientPointsError:
            raise
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to process redemption transaction for member '{member_id}': {e}", exc_info=True)
            raise


    def get_member_transactions(self, member_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, member_id, type, amount_spent, points_delta,
                   tier_at_time, idempotency_key, created_at, staff_id, terminal_id
            FROM transactions
            WHERE member_id = ?
            ORDER BY created_at DESC
            LIMIT ?;
        """, (member_id, limit))
        return [dict(row) for row in cursor.fetchall()]

    def get_member_transactions_paginated(
        self, member_id: str, page: int = 1, size: int = 10
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Paginated ledger history. Returns (items, total_count).
        page is 1-indexed, size is items-per-page.
        """
        cursor = self.conn.cursor()
        offset = (page - 1) * size

        # Total count
        cursor.execute(
            "SELECT COUNT(*) as total FROM transactions WHERE member_id = ?;",
            (member_id,)
        )
        total = cursor.fetchone()["total"]

        # Page data
        cursor.execute("""
            SELECT id, member_id, type, amount_spent, points_delta,
                   tier_at_time, idempotency_key, created_at, staff_id, terminal_id
            FROM transactions
            WHERE member_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?;
        """, (member_id, size, offset))
        items = [dict(row) for row in cursor.fetchall()]
        return items, total


    def compute_ledger_replay_balance(self, member_id: str) -> Tuple[int, int]:
        """
        Reconstructs member current_points and lifetime_points by replaying the complete ledger history.
        Returns (recalculated_current_points, recalculated_lifetime_points).
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT type, points_delta
            FROM transactions
            WHERE member_id = ?
            ORDER BY created_at ASC;
        """, (member_id,))
        rows = cursor.fetchall()

        recalculated_current = 0
        recalculated_lifetime = 0

        for row in rows:
            delta = row["points_delta"]
            recalculated_current += delta
            if delta > 0:
                recalculated_lifetime += delta

        return recalculated_current, recalculated_lifetime

    def record_expiration_transaction(
        self,
        member_id: str,
        expired_points: int,
        idempotency_key: str,
        as_of_iso_time: str
    ) -> Dict[str, Any]:
        """
        Executes an EXPIRATION transaction inside an atomic database transaction.
        Appends EXPIRATION transaction to ledger (-expired_points) and updates MemberBalanceCache.
        """
        if expired_points <= 0:
            raise ValueError("Expired points must be greater than zero.")

        existing = self.get_idempotency_record(idempotency_key)
        if existing:
            return existing

        tx_id = f"tx_exp_{uuid.uuid4().hex[:12]}"

        self.conn.execute("BEGIN IMMEDIATE;")
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT m.id, c.current_points, c.lifetime_points, c.current_tier
                FROM members m
                JOIN member_balance_cache c ON m.id = c.member_id
                WHERE m.id = ?;
            """, (member_id,))
            row = cursor.fetchone()
            if not row:
                self.conn.rollback()
                raise MemberNotFoundError(f"Member with ID '{member_id}' not found.")

            current_points = row["current_points"]
            tier_at_time = row["current_tier"]
            actual_expired = min(current_points, expired_points)
            if actual_expired <= 0:
                self.conn.rollback()
                return {"status": "SKIPPED", "message": "No points available to expire."}

            new_points = current_points - actual_expired
            points_delta = -actual_expired

            # Insert transaction ledger row
            cursor.execute("""
                INSERT INTO transactions (
                    id, member_id, type, amount_spent, points_delta,
                    tier_at_time, idempotency_key, created_at, staff_id, terminal_id
                ) VALUES (?, ?, 'EXPIRATION', 0.0, ?, ?, ?, ?, 'SYSTEM_CLOCK', 'CLOCK_JOB');
            """, (tx_id, member_id, points_delta, tier_at_time, idempotency_key, as_of_iso_time))

            # Update cache (lifetime points DOES NOT decrease on expiration)
            cursor.execute("""
                UPDATE member_balance_cache
                SET current_points = ?, last_transaction_id = ?
                WHERE member_id = ?;
            """, (new_points, tx_id, member_id))

            response_payload = {
                "status": "EXPIRED",
                "transaction_id": tx_id,
                "member_id": member_id,
                "type": "EXPIRATION",
                "points_expired": actual_expired,
                "remaining_points": new_points,
                "idempotency_key": idempotency_key,
                "created_at": as_of_iso_time
            }

            cursor.execute("""
                INSERT INTO idempotency_records (idempotency_key, response_json, created_at)
                VALUES (?, ?, ?);
            """, (idempotency_key, json.dumps(response_payload), as_of_iso_time))

            self.conn.commit()
            logger.info(f"Points expired for member '{member_id}': -{actual_expired} pts, new_balance={new_points} pts.")
            return response_payload
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to record expiration transaction for member '{member_id}': {e}", exc_info=True)
            raise

    def get_outbox_events(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        if status:
            cursor.execute("""
                SELECT id, aggregate_type, aggregate_id, event_type, payload_json, status, created_at
                FROM outbox WHERE status = ? ORDER BY created_at ASC;
            """, (status,))
        else:
            cursor.execute("""
                SELECT id, aggregate_type, aggregate_id, event_type, payload_json, status, created_at
                FROM outbox ORDER BY created_at ASC;
            """)
        events = []
        for row in cursor.fetchall():
            d = dict(row)
            d["payload"] = json.loads(d["payload_json"])
            events.append(d)
        return events

    def mark_outbox_processed(self, event_ids: List[str]) -> int:
        if not event_ids:
            return 0
        cursor = self.conn.cursor()
        self.conn.execute("BEGIN IMMEDIATE;")
        try:
            placeholders = ",".join("?" for _ in event_ids)
            cursor.execute(f"UPDATE outbox SET status = 'PROCESSED' WHERE id IN ({placeholders});", event_ids)
            count = cursor.rowcount
            self.conn.commit()
            return count
        except Exception:
            self.conn.rollback()
            raise

