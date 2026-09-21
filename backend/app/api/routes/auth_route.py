"""
Auth Routes
GET /api/auth/me -> Returns validated user identity
"""
import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends

from ...core.auth import get_current_user

log = logging.getLogger("marketflux.routes.auth")
router = APIRouter()


@router.get("/me")
def get_me(user: Dict[str, Any] = Depends(get_current_user)):
    """Return authenticated Supabase user profile verified by FastAPI."""
    return {"status": "authenticated", "user": user}
