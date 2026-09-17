from typing import Generator, Dict, Any
import sqlite3

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from jose import JWTError

from src.storage.database import get_connection, DEFAULT_DB_PATH
from src.services.lookup_service import MemberLookupService
from src.services.purchase_service import PurchaseService
from src.services.redemption_service import RedemptionService
from src.services.clock_service import ClockService
from src.services.outbox_service import OutboxService

# Shared ClockService instance to maintain simulated clock state across API requests
_clock_service_instance = ClockService(DEFAULT_DB_PATH)

# OAuth2 scheme — tokenUrl matches /auth/login endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """
    Dependency generator for SQLite database connections.
    Closes connection reliably after request completion.
    """
    conn = get_connection(DEFAULT_DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    conn: sqlite3.Connection = Depends(get_db)
) -> Dict[str, Any]:
    """
    JWT authentication guard. Decodes the Bearer token and returns the
    authenticated user's payload. Raises 401 if token is missing/invalid/expired.
    """
    from src.auth.service import decode_access_token  # local import to avoid circular

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        if not user_id:
            raise credentials_exception
        return payload
    except JWTError:
        raise credentials_exception


def require_role(*roles: str):
    """
    RBAC dependency factory. Returns a FastAPI dependency that verifies the
    authenticated user holds one of the specified roles.

    Usage:
        _: dict = Depends(require_role("admin"))
        _: dict = Depends(require_role("admin", "staff"))
    """
    def _check(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        user_role = current_user.get("role", "")
        if user_role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role(s): {', '.join(roles)}. Your role: '{user_role}'.",
            )
        return current_user
    return _check


def get_lookup_service() -> MemberLookupService:
    """Dependency provider for MemberLookupService."""
    return MemberLookupService(DEFAULT_DB_PATH)


def get_purchase_service() -> PurchaseService:
    """Dependency provider for PurchaseService."""
    return PurchaseService(DEFAULT_DB_PATH)


def get_redemption_service() -> RedemptionService:
    """Dependency provider for RedemptionService."""
    return RedemptionService(DEFAULT_DB_PATH)


def get_clock_service() -> ClockService:
    """Dependency provider for ClockService."""
    return _clock_service_instance


def get_outbox_service() -> OutboxService:
    """Dependency provider for OutboxService."""
    return OutboxService(DEFAULT_DB_PATH)
