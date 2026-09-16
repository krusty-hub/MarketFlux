"""
MarketFlux – Forex Data Provider (Dukascopy)
Fetches historical OHLCV data from Dukascopy's free public API.
No API key required.

Supported pairs: XAUUSD, USDCAD, USDCHF, EURUSD
Note: Dukascopy does not provide real-time volume; volume fields will be 0.0
      and this is handled explicitly here (not silently left as NaN).
"""
import logging
import struct
import zlib
from datetime import datetime, timezone
from typing import Optional
from io import BytesIO

import pandas as pd
import requests

from ..config.settings import (
    DUKASCOPY_URL,
    FOREX_PAIRS,
    FOREX_TIMEFRAMES,
    PRICE_FETCH_TIMEOUT,
    REQUEST_HEADERS,
    DEFAULT_CANDLES_LIMIT,
)

log = logging.getLogger("marketflux.forex")

# Dukascopy timeframe mapping
_DUKASCOPY_TF_MAP = {
    "1m":  "MIN1",
    "5m":  "MIN5",
    "15m": "MIN15",
    "1h":  "HOUR1",
    "4h":  "HOUR4",
    "1d":  "DAY1",
}


def fetch_dukascopy_ohlcv(
    symbol: str,
    timeframe: str = "1h",
    limit: int = DEFAULT_CANDLES_LIMIT,
) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV data from Dukascopy public API.

    Returns a DataFrame indexed by UTC timestamp with columns:
      [open, high, low, close, volume]

    Volume is always 0.0 for forex — this is explicit and documented,
    not a silent failure.
    """
    if symbol not in FOREX_PAIRS:
        log.error(f"Unsupported forex symbol: {symbol}. Supported: {list(FOREX_PAIRS)}")
        return None
    if timeframe not in FOREX_TIMEFRAMES:
        log.error(f"Unsupported timeframe: {timeframe}. Supported: {FOREX_TIMEFRAMES}")
        return None

    duka_symbol = FOREX_PAIRS[symbol]["dukascopy"]
    duka_tf = _DUKASCOPY_TF_MAP.get(timeframe)
    if duka_tf is None:
        log.error(f"No Dukascopy mapping for timeframe: {timeframe}")
        return None

    # Dukascopy JSON endpoint
    url = f"{DUKASCOPY_URL}?path=chart/json/{duka_symbol}/{duka_tf}/BIDASK&limit={limit}"

    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=PRICE_FETCH_TIMEOUT)
        resp.raise_for_status()
        raw = resp.json()

        if not raw or not isinstance(raw, list):
            log.warning(f"Dukascopy returned empty/unexpected data for {symbol} {timeframe}")
            return None

        records = []
        for candle in raw:
            # Dukascopy format: [timestamp_ms, open_bid, high_bid, low_bid, close_bid, volume]
            ts = pd.to_datetime(candle[0], unit="ms", utc=True)
            records.append({
                "timestamp": ts,
                "open":   float(candle[1]),
                "high":   float(candle[2]),
                "low":    float(candle[3]),
                "close":  float(candle[4]),
                "volume": 0.0,  # Dukascopy does not provide tick volume in this endpoint
            })

        df = pd.DataFrame(records).set_index("timestamp")
        df = df.sort_index()
        log.info(f"✓ Dukascopy OHLCV {symbol} {timeframe}: {len(df)} candles (volume=0, expected for forex)")
        return df

    except Exception as e:
        log.warning(f"Dukascopy fetch failed ({symbol} {timeframe}): {e}")

    # Fallback: try Alpha Vantage if ALPHA_VANTAGE_API_KEY is set
    return _fetch_alpha_vantage_fallback(symbol, timeframe, limit)


def _fetch_alpha_vantage_fallback(
    symbol: str,
    timeframe: str,
    limit: int,
) -> Optional[pd.DataFrame]:
    """
    Fallback to Alpha Vantage FX endpoint if Dukascopy fails.
    Requires ALPHA_VANTAGE_API_KEY in environment.
    """
    import os
    av_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
    if not av_key:
        log.warning("No ALPHA_VANTAGE_API_KEY set, cannot use fallback.")
        return None

    _AV_TF = {"1m": "1min", "5m": "5min", "15m": "15min", "1h": "60min"}
    _AV_DAILY = {"1d": "FX_DAILY"}

    av_from = symbol[:3]
    av_to   = symbol[3:]
    av_url  = "https://www.alphavantage.co/query"

    try:
        if timeframe in _AV_DAILY:
            params = {
                "function": "FX_DAILY",
                "from_symbol": av_from,
                "to_symbol": av_to,
                "outputsize": "full",
                "apikey": av_key,
            }
            resp = requests.get(av_url, params=params, timeout=PRICE_FETCH_TIMEOUT)
            resp.raise_for_status()
            data = resp.json().get("Time Series FX (Daily)", {})
        elif timeframe in _AV_TF:
            params = {
                "function": "FX_INTRADAY",
                "from_symbol": av_from,
                "to_symbol": av_to,
                "interval": _AV_TF[timeframe],
                "outputsize": "full",
                "apikey": av_key,
            }
            resp = requests.get(av_url, params=params, timeout=PRICE_FETCH_TIMEOUT)
            resp.raise_for_status()
            key = f"Time Series FX ({_AV_TF[timeframe]})"
            data = resp.json().get(key, {})
        else:
            log.warning(f"Alpha Vantage fallback: no mapping for timeframe {timeframe}")
            return None

        if not data:
            return None

        records = []
        for ts_str, bar in sorted(data.items()):
            records.append({
                "timestamp": pd.to_datetime(ts_str, utc=True),
                "open":   float(bar["1. open"]),
                "high":   float(bar["2. high"]),
                "low":    float(bar["3. low"]),
                "close":  float(bar["4. close"]),
                "volume": 0.0,  # AV FX endpoints also don't provide reliable volume
            })

        df = pd.DataFrame(records).set_index("timestamp").sort_index().tail(limit)
        log.info(f"✓ Alpha Vantage fallback {symbol} {timeframe}: {len(df)} candles")
        return df

    except Exception as e:
        log.warning(f"Alpha Vantage fallback failed ({symbol} {timeframe}): {e}")
        return None


def get_forex_symbols() -> dict:
    """Return mapping of symbol → human label."""
    return {k: v["label"] for k, v in FOREX_PAIRS.items()}
