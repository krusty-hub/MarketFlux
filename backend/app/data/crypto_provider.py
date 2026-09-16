"""
MarketFlux – Crypto Data Provider
Fetches OHLCV and live price data using Yahoo Finance (primary) and Alpaca (fallback).
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

import pandas as pd
import yfinance as yf
import requests

from ..config.settings import (
    CRYPTO_PAIRS,
    CRYPTO_TIMEFRAMES,
    DEFAULT_CANDLES_LIMIT,
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY,
)

log = logging.getLogger("marketflux.crypto")


def _get_yf_symbol(symbol: str) -> str:
    """Convert BTCUSDT to BTC-USD for Yahoo Finance."""
    if symbol.endswith("USDT"):
        return symbol.replace("USDT", "-USD")
    elif symbol.endswith("USD"):
        return symbol[:3] + "-USD"
    return symbol


def _get_alpaca_symbol(symbol: str) -> str:
    """Convert BTCUSDT to BTC/USD for Alpaca."""
    if symbol.endswith("USDT"):
        return symbol.replace("USDT", "/USD")
    elif symbol.endswith("USD"):
        return symbol[:3] + "/USD"
    return symbol


def fetch_alpaca_ohlcv(
    symbol: str,
    timeframe: str,
    limit: int,
) -> Optional[pd.DataFrame]:
    """Fetch OHLCV data from Alpaca crypto endpoint."""
    alpaca_symbol = _get_alpaca_symbol(symbol)
    
    tf_map = {
        "1m": "1Min", "5m": "5Min", "15m": "15Min",
        "1h": "1Hour", "4h": "4Hour", "1d": "1Day"
    }
    alpaca_tf = tf_map.get(timeframe)
    if not alpaca_tf:
        return None

    if not ALPACA_API_KEY:
        log.warning("Alpaca API key not set, skipping Alpaca fallback.")
        return None

    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
    }
    if ALPACA_SECRET_KEY:
        headers["APCA-API-SECRET-KEY"] = ALPACA_SECRET_KEY
    else:
        # Paper trading/free endpoints sometimes accept just the key, or we just send empty
        headers["APCA-API-SECRET-KEY"] = ""

    url = "https://data.alpaca.markets/v1beta3/crypto/us/bars"
    params = {
        "symbols": alpaca_symbol,
        "timeframe": alpaca_tf,
        "limit": limit
    }

    try:
        log.info(f"Fetching {alpaca_symbol} data from Alpaca ...")
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        bars = data.get("bars", {}).get(alpaca_symbol, [])
        if not bars:
            return None

        df = pd.DataFrame(bars)
        # Alpaca returns: t (timestamp), o (open), h (high), l (low), c (close), v (volume)
        df = df.rename(columns={
            "t": "timestamp", "o": "open", "h": "high", 
            "l": "low", "c": "close", "v": "volume"
        })
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp")[["open", "high", "low", "close", "volume"]]
        
        log.info(f"✓ Alpaca OHLCV {symbol} {timeframe}: {len(df)} candles")
        return df
    except Exception as e:
        log.warning(f"Alpaca fetch failed ({symbol} {timeframe}): {e}")
        return None


def fetch_ohlcv(
    symbol: str,
    timeframe: str = "5m",
    limit: int = DEFAULT_CANDLES_LIMIT,
) -> pd.DataFrame:
    """
    Fetch OHLCV candles (Primary: Yahoo Finance, Fallback: Alpaca).
    Returns a DataFrame indexed by UTC timestamp with columns [open, high, low, close, volume].
    """
    if symbol not in CRYPTO_PAIRS:
        raise ValueError(f"Unsupported symbol: {symbol}")
    if timeframe not in CRYPTO_TIMEFRAMES:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    yf_symbol = _get_yf_symbol(symbol)
    
    if timeframe in ["1m"]:
        period = "7d"
    elif timeframe in ["5m", "15m"]:
        period = "60d"
    else:
        period = "1y"

    try:
        log.info(f"Fetching {yf_symbol} data from Yahoo Finance ...")
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period=period, interval=timeframe)
        
        if df.empty:
            raise RuntimeError(f"Yahoo Finance returned no data for {yf_symbol} {timeframe}")
            
        df = df.rename(columns={
            "Open": "open", "High": "high", "Low": "low", 
            "Close": "close", "Volume": "volume"
        })
        
        if df.index.tzinfo is None:
            df.index = df.index.tz_localize("UTC")
        else:
            df.index = df.index.tz_convert("UTC")
            
        df.index.name = "timestamp"
        df = df[["open", "high", "low", "close", "volume"]]
        df = df.tail(limit)
        
        log.info(f"✓ yfinance OHLCV {symbol} {timeframe}: {len(df)} candles")
        return df

    except Exception as e:
        log.warning(f"yfinance OHLCV fetch failed ({symbol} {timeframe}): {e}")
        log.info("Trying Alpaca fallback...")
        
        df_alpaca = fetch_alpaca_ohlcv(symbol, timeframe, limit)
        if df_alpaca is not None and not df_alpaca.empty:
            return df_alpaca
            
        raise RuntimeError(
            f"Could not fetch OHLCV data for {symbol} {timeframe} from any source."
        )


def get_live_price(symbol: str, exchange: str = "yfinance") -> Tuple[float, str]:
    """Get live price with fallback to Alpaca."""
    yf_symbol = _get_yf_symbol(symbol)
    try:
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period="1d", interval="1m")
        if df.empty:
            raise RuntimeError(f"No recent live price for {yf_symbol}")
            
        price = float(df["Close"].iloc[-1])
        log.debug(f"✓ yfinance live price {symbol}: ${price:.4f}")
        return price, "yfinance"
    except Exception as e:
        log.warning(f"yfinance live price failed ({symbol}): {e}")
        
        # Alpaca fallback
        try:
            alpaca_symbol = _get_alpaca_symbol(symbol)
            url = f"https://data.alpaca.markets/v1beta3/crypto/us/latest/trades?symbols={alpaca_symbol}"
            headers = {"APCA-API-KEY-ID": ALPACA_API_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY or ""}
            resp = requests.get(url, headers=headers, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            trade = data.get("trades", {}).get(alpaca_symbol, {})
            price = float(trade.get("p", 0))
            if price > 0:
                log.debug(f"✓ Alpaca live price {symbol}: ${price:.4f}")
                return price, "alpaca"
        except Exception as e2:
            log.warning(f"Alpaca live price failed ({symbol}): {e2}")
            
        raise RuntimeError(f"Live price fetch failed for {symbol} after retries.")


def get_supported_symbols() -> Dict[str, str]:
    """Return mapping of symbol → human label."""
    return {k: v["label"] for k, v in CRYPTO_PAIRS.items()}
