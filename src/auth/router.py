from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
import sqlite3

from src.auth.schemas import RegisterRequest, TokenResponse, UserResponse
from src.auth.service import (
    register_user,
    authenticate_user,
    get_user_by_id,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_HOURS,
)
from src.api.deps import get_db, get_current_user
from src.logger import get_logger

logger = get_logger("auth.router")

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=201)
def register(
    req: RegisterRequest,
    conn: sqlite3.Connection = Depends(get_db)
):
    """
    Register a new staff account.
    The very first account created is automatically assigned the 'admin' role.
    """
    try:
        user = register_user(
            conn=conn,
            username=req.username,
            email=req.email,
            password=req.password,
            role=req.role or "staff"
        )
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Registration failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Registration failed. Please try again.")


@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    conn: sqlite3.Connection = Depends(get_db)
):
    """
    Authenticate a staff user and return a signed JWT Bearer token.
    Token expires in 8 hours.
    Compatible with OAuth2 password flow (Swagger UI authorize button).
    """
    user = authenticate_user(conn, username=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(data={
        "sub": user["id"],
        "username": user["username"],
        "role": user["role"],
    })

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        username=user["username"],
        role=user["role"]
    )


@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    current_user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_db)
):
    """
    Returns the profile of the currently authenticated staff user.
    Requires a valid Bearer token in the Authorization header.
    """
    user = get_user_by_id(conn, current_user["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")
    return user
