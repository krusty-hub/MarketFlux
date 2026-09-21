"""
MarketFlux – Supabase Authentication & JWT Verification for FastAPI
Validates Bearer tokens against Supabase Auth server-side.
"""
import logging
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..config.settings import SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_ROLE_KEY

log = logging.getLogger("marketflux.auth")
security = HTTPBearer(auto_error=False)


def get_auth_client():
    """Return Supabase client with anon key or service role key for auth validation."""
    from supabase import create_client
    key = SUPABASE_KEY or SUPABASE_SERVICE_ROLE_KEY
    if not SUPABASE_URL or not key:
        return None
    return create_client(SUPABASE_URL, key)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Dict[str, Any]:
    """
    Validate Supabase JWT from Authorization header.
    Returns authenticated user object or raises 401.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    client = get_auth_client()

    if not client:
        # If Supabase not configured in local environment, reject or raise error
        log.warning("Supabase client not configured for auth verification")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable",
        )

    try:
        user_resp = client.auth.get_user(token)
        if not user_resp or not user_resp.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = user_resp.user
        return {
            "id": user.id,
            "email": user.email,
            "user_metadata": user.user_metadata or {},
            "created_at": str(user.created_at),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"JWT validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[Dict[str, Any]]:
    """
    Optional authentication: returns user object if valid token supplied, else None.
    """
    if not credentials or not credentials.credentials:
        return None
    try:
        return get_current_user(credentials)
    except HTTPException:
        return None
