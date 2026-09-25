"""
MarketFlux – Supabase Admin Client
Shared service-role client for backend database operations.
Uses the service role key to bypass RLS for server-side operations.
"""
import logging
from typing import Optional
from supabase import create_client, Client

from ..config.settings import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_KEY

log = logging.getLogger("marketflux.supabase_client")

_client: Optional[Client] = None


def get_supabase() -> Client:
    """Return a singleton Supabase client with service-role privileges."""
    global _client
    if _client is None:
        key = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY
        if not SUPABASE_URL or not key:
            raise RuntimeError(
                "Supabase credentials not configured. "
                "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in your .env file."
            )
        _client = create_client(SUPABASE_URL, key)
        log.info("Supabase service-role client initialized")
    return _client
