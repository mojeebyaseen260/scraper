"""
JWT authentication helpers
"""

import os
import sys
import bcrypt
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from fastapi import HTTPException, Header
from typing import Optional

_DEFAULT_SECRET = "coldleads-jwt-secret-change-in-production-2024"
SECRET_KEY = os.environ.get("JWT_SECRET", _DEFAULT_SECRET)

if SECRET_KEY == _DEFAULT_SECRET and os.environ.get("PRODUCTION", "0") == "1":
    print(
        "SECURITY WARNING: JWT_SECRET env var is not set. "
        "Using the default insecure secret key in production is dangerous!",
        file=sys.stderr,
    )

ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_token(user_id: int, email: str, role: str, token_version: int = 0) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": str(user_id), "email": email, "role": role,
         "tv": int(token_version), "exp": exp},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(401, "Invalid or expired token")


def get_current_user(
    authorization: Optional[str] = Header(None),
) -> dict:
    """Accept JWT from Authorization header only, then verify the token has not
    been revoked (token_version must match the user's current value in the DB)."""
    if not (authorization and authorization.startswith("Bearer ")):
        raise HTTPException(401, "Authorization required")

    payload = decode_token(authorization[7:])

    # Revocation check — lazy import avoids a circular import at module load.
    from database import get_user_by_id
    try:
        uid = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(401, "Invalid token")
    user = get_user_by_id(uid)
    if not user:
        raise HTTPException(401, "User no longer exists")
    if int(payload.get("tv", 0)) != int(user.get("token_version", 0) or 0):
        raise HTTPException(401, "Session revoked — please log in again")
    return payload


def require_admin(
    authorization: Optional[str] = Header(None),
) -> dict:
    user = get_current_user(authorization)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    return user
