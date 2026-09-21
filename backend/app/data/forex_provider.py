"""
MarketFlux – Forex Data Provider (Twelve Data primary + Dukascopy fallback)
Fetches historical OHLCV data.
Twelve Data is the primary source; Dukascopy is used as a reliable fallback.
"""
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import requests

from ..config.settings import (
    DUKASCOPY_URL,
    FOREX_PAIRS,
    FOREX_TIMEFRAMES,
    PRICE_FETCH_TIMEOUT,
    REQUEST_HEADERS,
    DEFAULT_CANDLES_LIMIT,
    TWELVEDATA_API_KEY,
)

log = logging.getLogger("marketflux.forex")

# ── In-memory cache (5-min TTL) ───────────────────────────────────────────────
_CACHE: dict = {}
_CACHE_TTL: int = 300  # seconds

# Tracks endpoints/symbols that hit premium/unsupported errors.
# Prevents repeated wasted API calls in a single server session.
_TD_UNAVAILABLE: set = set()

# ── Twelve Data timeframe map ─────────────────────────────────────────────────
_TD_TF_MAP: dict = {
    "1m":  "1min",
    "5m":  "5min",
    "15m": "15min",
    "30m": "30min",
    "1h":  "1h",
    "4h":  "4h",
    "1d":  "1day",
    "1wk": "1week",
    "1mo": "1month",
}

# ── Dukascopy timeframe map ───────────────────────────────────────────────────
_DUKASCOPY_TF_MAP: dict = {
    "1m":  "MIN1",
    "5m":  "MIN5",
    "15m": "MIN15",
    "30m": "MIN30",
    "1h":  "HOUR1",
    "4h":  "HOUR4",
    "1d":  "DAY1",
}


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def fetch_forex_ohlcv(
    symbol: str,
    timeframe: str = "5m",
    limit: int = DEFAULT_CANDLES_LIMIT,
) -> Optional[pd.DataFrame]:
    """
    Main entry point for forex OHLCV data.
    1. Tries Twelve Data first.
    2. Falls back to Dukascopy if Twelve Data fails, is unavailable, or rate-limited.
    Returns a DataFrame with columns: [open, high, low, close, volume] indexed by timestamp.
    """
    if symbol not in FOREX_PAIRS:
        log.error(f"Unsupported forex symbol: {symbol}. Supported: {list(FOREX_PAIRS)}")
        return None
    if timeframe not in FOREX_TIMEFRAMES:
        log.error(f"Unsupported timeframe: {timeframe}. Supported: {FOREX_TIMEFRAMES}")
        return None

    cache_key = f"{symbol}_{timeframe}_{limit}"
    now = time.time()
    if cache_key in _CACHE:
        cached_df, cached_time = _CACHE[cache_key]
        if now - cached_time < _CACHE_TTL:
            log.info(f"Serving {symbol} {timeframe} from cache.")
            return cached_df

    # 1. Primary: Twelve Data
    df = _fetch_twelve_data(symbol, timeframe, limit)

    # 2. Fallback: Dukascopy
    if df is None or df.empty:
        log.warning(f"Twelve Data unavailable for {symbol} {timeframe}. Falling back to Dukascopy.")
        df = _fetch_dukascopy_fallback(symbol, timeframe, limit)

    if df is not None and not df.empty:
        _CACHE[cache_key] = (df, now)
        return df

    log.error(f"All providers failed for {symbol} {timeframe}.")
    return None


def get_forex_symbols() -> dict:
    """Return mapping of symbol → human label."""
    return {k: v["label"] for k, v in FOREX_PAIRS.items()}


# ─────────────────────────────────────────────────────────────────────────────
# Twelve Data
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_twelve_data(
    symbol: str,
    timeframe: str,
    limit: int,
) -> Optional[pd.DataFrame]:
    """Fetch OHLCV from Twelve Data REST API."""

    if not TWELVEDATA_API_KEY:
        log.warning("No TWELVEDATA_API_KEY set. Skipping Twelve Data.")
        return None

    unavail_key = f"{symbol}_{timeframe}"
    if unavail_key in _TD_UNAVAILABLE:
        log.warning(
            f"Twelve Data skipped for {symbol} {timeframe}: "
            "previously marked unavailable (premium/unsupported)."
        )
        return None

    td_symbol = FOREX_PAIRS[symbol].get("twelvedata")
    if not td_symbol:
        log.warning(f"No Twelve Data symbol mapping for {symbol}. Skipping.")
        return None

    td_interval = _TD_TF_MAP.get(timeframe)
    if not td_interval:
        log.warning(f"No Twelve Data interval mapping for timeframe {timeframe}.")
        return None

    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol":   td_symbol,
        "interval": td_interval,
        "outputsize": min(limit, 5000),   # TD max per call is 5000
        "format":   "JSON",
        "apikey":   TWELVEDATA_API_KEY,
    }

    try:
        resp = requests.get(url, params=params, timeout=PRICE_FETCH_TIMEOUT, headers=REQUEST_HEADERS)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout:
        log.warning(f"Twelve Data request timed out for {symbol} {timeframe}.")
        return None
    except requests.exceptions.ConnectionError as exc:
        log.warning(f"Twelve Data network error for {symbol} {timeframe}: {exc}")
        return None
    except Exception as exc:
        log.warning(f"Twelve Data unexpected error for {symbol} {timeframe}: {exc}")
        return None

    # ── Error response handling ───────────────────────────────────────────────
    status = data.get("status", "")
    code   = data.get("code", 0)
    message = data.get("message", "")

    if status == "error":
        # 400 = invalid symbol/interval, 401 = invalid key, 429 = rate limit
        # 403 = plan restriction
        if code == 401:
            log.error(f"Twelve Data: Invalid API key.")
        elif code == 429:
            log.warning(f"Twelve Data Rate Limit hit for {symbol} {timeframe}: {message}")
        elif code in (400, 403) or "premium" in message.lower() or "not available" in message.lower():
            log.warning(
                f"Twelve Data unavailable for {symbol} {timeframe}: "
                f"endpoint/symbol not on current plan ({message})"
            )
            _TD_UNAVAILABLE.add(unavail_key)
        else:
            log.warning(f"Twelve Data error for {symbol} {timeframe} [code {code}]: {message}")
        return None

    values = data.get("values")
    if not values:
        log.warning(f"Twelve Data returned empty data for {symbol} {timeframe}.")
        return None

    # ── Parse response ────────────────────────────────────────────────────────
    try:
        records = []
        for bar in values:
            records.append({
                "timestamp": pd.to_datetime(bar["datetime"], utc=True),
                "open":   float(bar["open"]),
                "high":   float(bar["high"]),
                "low":    float(bar["low"]),
                "close":  float(bar["close"]),
                "volume": 0.0,  # Forex has no centralised volume
            })
        df = (
            pd.DataFrame(records)
            .set_index("timestamp")
            .sort_index()
            .tail(limit)
        )
        log.info(f"✓ Twelve Data OHLCV {symbol} {timeframe}: {len(df)} candles")
        return df
    except (KeyError, ValueError) as exc:
        log.warning(f"Twelve Data parse error for {symbol} {timeframe}: {exc}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Dukascopy fallback
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_dukascopy_fallback(
    symbol: str,
    timeframe: str,
    limit: int,
) -> Optional[pd.DataFrame]:
    """Fallback OHLCV fetch from Dukascopy public API."""
    duka_symbol = FOREX_PAIRS[symbol].get("dukascopy")
    if not duka_symbol:
        log.warning(f"No Dukascopy symbol mapping for {symbol}.")
        return None

    duka_tf = _DUKASCOPY_TF_MAP.get(timeframe)
    if duka_tf is None:
        log.warning(f"No Dukascopy mapping for timeframe {timeframe}.")
        return None

    url = f"{DUKASCOPY_URL}?path=chart/json/{duka_symbol}/{duka_tf}/BIDASK&limit={limit}"

    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=PRICE_FETCH_TIMEOUT)
        resp.raise_for_status()
        raw = resp.json()
    except requests.exceptions.Timeout:
        log.warning(f"Dukascopy request timed out for {symbol} {timeframe}.")
        return None
    except Exception as exc:
        log.warning(f"Dukascopy fetch failed ({symbol} {timeframe}): {exc}")
        return None

    if not raw or not isinstance(raw, list):
        log.warning(f"Dukascopy returned empty data for {symbol} {timeframe}.")
        return None

    try:
        records = []
        for candle in raw:
            ts = pd.to_datetime(candle[0], unit="ms", utc=True)
            records.append({
                "timestamp": ts,
                "open":   float(candle[1]),
                "high":   float(candle[2]),
                "low":    float(candle[3]),
                "close":  float(candle[4]),
                "volume": 0.0,
            })
        df = (
            pd.DataFrame(records)
            .set_index("timestamp")
            .sort_index()
        )
        log.info(f"✓ Dukascopy OHLCV {symbol} {timeframe}: {len(df)} candles")
        return df
    except (KeyError, ValueError) as exc:
        log.warning(f"Dukascopy parse error ({symbol} {timeframe}): {exc}")
        return None
