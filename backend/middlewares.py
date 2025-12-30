"""
Authentication middleware for Scoring Basket
Provides JWT token validation and user authentication
"""

from typing import Optional
from fastapi import HTTPException, status, Header, Depends
from sqlalchemy.orm import Session
from .database import get_db_session
from .models import User
from .security import verify_access_token


async def authorize_middleware(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: Session = Depends(get_db_session)
) -> User:
    """
    FastAPI dependency for JWT token authentication
    Returns authenticated User object or raises HTTPException
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Parse bearer token
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise ValueError("Invalid scheme")
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify token
    user_id = verify_access_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user