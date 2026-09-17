import hashlib
import os
import uuid
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

import bcrypt as _bcrypt
from jose import JWTError, jwt

from src.logger import get_logger

logger = get_logger("auth.service")

# ── JWT Configuration ──────────────────────────────────────────────────────────
_DEFAULT_SECRET = "cafe-rewards-jwt-secret-key-change-in-production-2026"
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", _DEFAULT_SECRET)
if SECRET_KEY == _DEFAULT_SECRET:
    logger.warning(
        "JWT_SECRET_KEY env var is not set — using insecure default key. "
        "Set JWT_SECRET_KEY in production!"
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 8

# ── Password Hashing (bcrypt 4.x / 5.x compatible) ────────────────────────────
# passlib 1.7.4 is incompatible with bcrypt 5.x; we call bcrypt directly.
# SHA-256 pre-hash keeps passwords within bcrypt's 72-byte limit.
_BCRYPT_ROUNDS = 12


def _prehash(password: str) -> bytes:
    """SHA-256 pre-hash keeps passwords within bcrypt's 72-byte limit."""
    return hashlib.sha256(password.encode("utf-8")).digest()


def hash_password(plain_password: str) -> str:
    """Pre-hash then bcrypt-hash the password. Returns a UTF-8 string."""
    hashed = _bcrypt.hashpw(_prehash(plain_password), _bcrypt.gensalt(rounds=_BCRYPT_ROUNDS))
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password using the same SHA-256 pre-hash + bcrypt pipeline."""
    try:
        return _bcrypt.checkpw(_prehash(plain_password), hashed_password.encode("utf-8"))
    except Exception:
        return False


# ── JWT Token Operations ───────────────────────────────────────────────────────
def create_access_token(data: Dict[str, Any]) -> str:
    """
    Creates a signed JWT access token containing the provided claims.
    Expiry is set to ACCESS_TOKEN_EXPIRE_HOURS from now.
    """
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    logger.info(f"Access token created for user '{data.get('sub')}', expires at '{expire.isoformat()}'.")
    return token


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodes and validates a JWT token.
    Raises JWTError if the token is invalid, expired, or tampered.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning(f"JWT decode failed: {e}")
        raise


# ── User CRUD Operations ───────────────────────────────────────────────────────
def register_user(
    conn: sqlite3.Connection,
    username: str,
    email: str,
    password: str,
    role: str = "staff"
) -> Dict[str, Any]:
    """
    Creates a new staff user account with a hashed password.
    Raises ValueError if username or email already exists.
    """
    user_id = f"usr_{uuid.uuid4().hex[:12]}"
    now_str = datetime.now(timezone.utc).isoformat()
    hashed = hash_password(password)

    conn.execute("BEGIN IMMEDIATE;")
    try:
        cursor = conn.cursor()

        # Check username uniqueness
        cursor.execute("SELECT id FROM users WHERE username = ?;", (username,))
        if cursor.fetchone():
            conn.rollback()
            raise ValueError(f"Username '{username}' is already taken.")

        # Check email uniqueness
        cursor.execute("SELECT id FROM users WHERE email = ?;", (email,))
        if cursor.fetchone():
            conn.rollback()
            raise ValueError(f"Email '{email}' is already registered.")

        # Determine role: first user ever becomes admin automatically
        cursor.execute("SELECT COUNT(*) as cnt FROM users;")
        user_count = cursor.fetchone()["cnt"]
        effective_role = "admin" if user_count == 0 else role

        cursor.execute(
            "INSERT INTO users (id, username, email, hashed_password, role, created_at) VALUES (?, ?, ?, ?, ?, ?);",
            (user_id, username, email, hashed, effective_role, now_str)
        )
        conn.commit()

        logger.info(f"New user registered: id='{user_id}', username='{username}', role='{effective_role}'.")
        return {
            "id": user_id,
            "username": username,
            "email": email,
            "role": effective_role,
            "created_at": now_str
        }
    except Exception:
        conn.rollback()
        raise


def authenticate_user(conn: sqlite3.Connection, username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Verifies username + password and returns user dict if valid, else None.
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, email, hashed_password, role, created_at FROM users WHERE username = ?;",
        (username,)
    )
    row = cursor.fetchone()
    if not row:
        logger.warning(f"Login attempt for unknown username '{username}'.")
        return None

    if not verify_password(password, row["hashed_password"]):
        logger.warning(f"Invalid password for username '{username}'.")
        return None

    logger.info(f"User '{username}' authenticated successfully.")
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "role": row["role"],
        "created_at": row["created_at"]
    }


def get_user_by_id(conn: sqlite3.Connection, user_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a user record by ID."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, email, role, created_at FROM users WHERE id = ?;",
        (user_id,)
    )
    row = cursor.fetchone()
    return dict(row) if row else None
