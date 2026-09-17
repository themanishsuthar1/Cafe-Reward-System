import sqlite3
import os
from contextlib import contextmanager
from typing import Generator
from src.logger import get_logger

logger = get_logger("storage.database")

DEFAULT_DB_PATH = "cafe_rewards.db"

def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """
    Returns an SQLite connection configured with WAL mode and row factory.
    """
    conn = sqlite3.connect(db_path, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Configure WAL mode for high concurrency
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=10000;")
    return conn

def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """
    Initializes tables and indexes if they do not exist.
    """
    logger.info(f"Initializing SQLite database at '{db_path}'...")
    conn = get_connection(db_path)
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS members (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                phone TEXT NOT NULL UNIQUE,
                tier TEXT NOT NULL DEFAULT 'BASE',
                join_date TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_members_phone ON members(phone);

            CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY,
                member_id TEXT NOT NULL,
                type TEXT NOT NULL,
                amount_spent REAL NOT NULL DEFAULT 0.0,
                points_delta INTEGER NOT NULL,
                tier_at_time TEXT NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                staff_id TEXT,
                terminal_id TEXT,
                FOREIGN KEY (member_id) REFERENCES members(id)
            );

            CREATE INDEX IF NOT EXISTS idx_transactions_member_id ON transactions(member_id);
            CREATE INDEX IF NOT EXISTS idx_transactions_idempotency ON transactions(idempotency_key);

            CREATE TABLE IF NOT EXISTS reward_items (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                points_cost INTEGER NOT NULL CHECK(points_cost > 0),
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS member_balance_cache (
                member_id TEXT PRIMARY KEY,
                current_points INTEGER NOT NULL DEFAULT 0,
                lifetime_points INTEGER NOT NULL DEFAULT 0,
                current_tier TEXT NOT NULL DEFAULT 'BASE',
                last_transaction_id TEXT,
                FOREIGN KEY (member_id) REFERENCES members(id),
                FOREIGN KEY (last_transaction_id) REFERENCES transactions(id)
            );

            CREATE TABLE IF NOT EXISTS idempotency_records (
                idempotency_key TEXT PRIMARY KEY,
                response_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS outbox (
                id TEXT PRIMARY KEY,
                aggregate_type TEXT NOT NULL,
                aggregate_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_outbox_status ON outbox(status);

            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                hashed_password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'staff',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
        """)
    conn.close()
    migrate_db(db_path)
    seed_default_rewards(db_path)


def migrate_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """
    Applies safe, additive migrations to existing databases.
    Idempotent — safe to run on every startup.
    Detects the old restrictive CHECK constraint via sqlite_master SQL text,
    then recreates the table without it. Uses execute() (not executescript)
    to avoid implicit COMMIT side-effects.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        # Check whether the transactions table DDL contains the old restrictive CHECK
        cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='transactions';"
        )
        row = cursor.fetchone()
        if not row:
            return  # table doesn't exist yet, init_db will create it fresh

        table_sql = row["sql"] or ""
        # Old constraint text that must be removed
        if "CHECK(type IN ('PURCHASE', 'REDEMPTION'))" not in table_sql and \
           "CHECK(type IN (\"PURCHASE\", \"REDEMPTION\"))" not in table_sql:
            logger.info("transactions table already supports EXPIRATION type — no migration needed.")
            return

        logger.info("Migrating transactions table to support EXPIRATION type...")
        # Disable foreign key checks during migration
        conn.execute("PRAGMA foreign_keys = OFF;")
        conn.execute("BEGIN IMMEDIATE;")
        try:
            conn.execute("ALTER TABLE transactions RENAME TO transactions_old;")
            conn.execute("""
                CREATE TABLE transactions (
                    id TEXT PRIMARY KEY,
                    member_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    amount_spent REAL NOT NULL DEFAULT 0.0,
                    points_delta INTEGER NOT NULL,
                    tier_at_time TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    staff_id TEXT,
                    terminal_id TEXT,
                    FOREIGN KEY (member_id) REFERENCES members(id)
                );
            """)
            conn.execute("INSERT INTO transactions SELECT * FROM transactions_old;")
            conn.execute("DROP TABLE transactions_old;")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_member_id ON transactions(member_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_idempotency ON transactions(idempotency_key);")
            conn.execute("COMMIT;")
            conn.execute("PRAGMA foreign_keys = ON;")
            logger.info("Migration complete: EXPIRATION type now supported in transactions table.")
        except Exception as e:
            conn.execute("ROLLBACK;")
            conn.execute("PRAGMA foreign_keys = ON;")
            logger.error(f"Migration failed: {e}", exc_info=True)
            raise
    finally:
        conn.close()


def seed_default_rewards(db_path: str = DEFAULT_DB_PATH) -> None:
    """
    Seeds initial reward items if none exist.
    """
    conn = get_connection(db_path)
    with conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM reward_items;")
        if cursor.fetchone()["count"] == 0:
            rewards = [
                ("rw_espresso", "Free Espresso", 100, 1),
                ("rw_cappuccino", "Free Cappuccino / Latte", 150, 1),
                ("rw_pastry", "Free Fresh Pastry", 200, 1),
                ("rw_bagel_sandwich", "Free Gourmet Bagel Sandwich", 350, 1),
                ("rw_tumbler", "Custom Cafe Tumbler", 750, 1),
            ]
            cursor.executemany(
                "INSERT INTO reward_items (id, name, points_cost, active) VALUES (?, ?, ?, ?);",
                rewards
            )
    conn.close()
