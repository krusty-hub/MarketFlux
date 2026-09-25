"""
MarketFlux – Local Historical Data Ingestion
Recursively parses and merges BTC/USDT futures historical CSV files from the
local data directory. Handles validation, deduplication, and timezone alignment.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

log = logging.getLogger("marketflux.data_ingest")

# Root directory for BTC/USDT futures data
_DATA_ROOT = Path(__file__).parents[3] / "data" / "btcusdt_futures"

# Expected OHLCV columns from Binance klines exports
_KLINE_COLS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "trades", "taker_base", "taker_quote", "ignore",
]

# Structure columns appended by the structure processor
_STRUCTURE_EXTRA_COLS = [
    "swing_high", "swing_low", "bos_bullish", "bos_bearish",
    "choch_bullish", "choch_bearish", "break_confirmed_close",
    "broken_swing_level", "break_candle_time", "break_direction",
    "structure_event", "structure", "last_swing_high", "last_swing_low",
]


# ═══════════════════════════════════════════════════════════════════════════════
#  KLINE INGESTION
# ═══════════════════════════════════════════════════════════════════════════════

def load_klines(
    timeframe: str = "5M",
    max_rows: Optional[int] = None,
    tail_rows: Optional[int] = None,
) -> pd.DataFrame:
    """
    Load raw OHLCV klines from the local CSV files.

    Args:
        timeframe: One of '5M', '15M', '1H', '4H'
        max_rows:  If set, only read the first N rows (for fast dev iteration)
        tail_rows: If set, only keep the last N rows (most recent data)

    Returns:
        DataFrame with columns [open, high, low, close, volume, ...]
        and a proper DatetimeIndex (UTC).
    """
    filename = f"BTCUSDT_{timeframe}.csv"
    path = _DATA_ROOT / "klines" / filename

    if not path.exists():
        raise FileNotFoundError(
            f"Klines file not found: {path}\n"
            f"Available files: {list((_DATA_ROOT / 'klines').glob('*.csv'))}"
        )

    log.info(f"Loading klines from {path} ...")

    df = pd.read_csv(
        path,
        nrows=max_rows,
        parse_dates=["open_time"],
        dtype={
            "open": np.float64,
            "high": np.float64,
            "low": np.float64,
            "close": np.float64,
            "volume": np.float64,
            "quote_volume": np.float64,
            "trades": np.int64,
        },
    )

    # ── Validation ────────────────────────────────────────────────────────────
    df = _validate_ohlcv(df)

    # Set DatetimeIndex (UTC)
    df["open_time"] = pd.to_datetime(df["open_time"], utc=True, format="mixed")
    df = df.set_index("open_time").sort_index()

    # Remove duplicate timestamps
    dup_count = df.index.duplicated().sum()
    if dup_count > 0:
        log.warning(f"Removed {dup_count} duplicate timestamps")
        df = df[~df.index.duplicated(keep="last")]

    # Tail slice
    if tail_rows and len(df) > tail_rows:
        df = df.tail(tail_rows)

    log.info(
        f"Loaded {len(df):,} kline rows | "
        f"Date range: {df.index[0]} → {df.index[-1]}"
    )
    return df


def _validate_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and clean OHLCV data."""
    required = ["open", "high", "low", "close", "volume"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    # Drop rows where OHLCV are all zeros or NaN
    ohlcv_mask = (
        (df["open"] > 0) & (df["high"] > 0) &
        (df["low"] > 0) & (df["close"] > 0)
    )
    invalid_count = (~ohlcv_mask).sum()
    if invalid_count > 0:
        log.warning(f"Dropped {invalid_count} invalid OHLCV rows (zeros or NaN)")
        df = df[ohlcv_mask].copy()

    # Forward-fill any remaining NaN values in numeric columns
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].ffill()

    return df


# ═══════════════════════════════════════════════════════════════════════════════
#  STRUCTURE DATA INGESTION
# ═══════════════════════════════════════════════════════════════════════════════

def load_structure(timeframe: str = "5M") -> pd.DataFrame:
    """
    Load pre-computed market structure data (BOS, CHoCH, swing points).
    """
    filename = f"BTCUSDT_{timeframe}_structure.csv"
    path = _DATA_ROOT / "structure" / filename

    if not path.exists():
        log.warning(f"Structure file not found: {path}, returning empty DataFrame")
        return pd.DataFrame()

    log.info(f"Loading structure data from {path} ...")

    df = pd.read_csv(path, parse_dates=["open_time"])
    df["open_time"] = pd.to_datetime(df["open_time"], utc=True, format="mixed")
    df = df.set_index("open_time").sort_index()

    # Remove duplicate timestamps
    df = df[~df.index.duplicated(keep="last")]

    # Keep only structure-specific columns (avoid duplicating OHLCV)
    struct_cols = [c for c in _STRUCTURE_EXTRA_COLS if c in df.columns]
    if struct_cols:
        df = df[struct_cols]

    log.info(f"Loaded {len(df):,} structure rows with {len(struct_cols)} features")
    return df


# ═══════════════════════════════════════════════════════════════════════════════
#  FUNDING RATE INGESTION
# ═══════════════════════════════════════════════════════════════════════════════

def load_funding_rate() -> pd.DataFrame:
    """
    Load BTC/USDT perpetual funding rate data.
    Resamples to match kline timestamps for merge.
    """
    path = _DATA_ROOT / "BTCUSDT_funding_rate.csv"

    if not path.exists():
        log.warning(f"Funding rate file not found: {path}")
        return pd.DataFrame()

    log.info(f"Loading funding rate data from {path} ...")

    df = pd.read_csv(path, parse_dates=["fundingTime"])
    df["fundingTime"] = pd.to_datetime(df["fundingTime"], utc=True, format="mixed")
    df = df.set_index("fundingTime").sort_index()
    df = df[~df.index.duplicated(keep="last")]

    # Keep only the funding rate column
    if "fundingRate" in df.columns:
        df = df[["fundingRate"]].rename(columns={"fundingRate": "funding_rate"})
        df["funding_rate"] = pd.to_numeric(df["funding_rate"], errors="coerce")

    log.info(f"Loaded {len(df):,} funding rate records")
    return df


# ═══════════════════════════════════════════════════════════════════════════════
#  MERGED DATASET
# ═══════════════════════════════════════════════════════════════════════════════

def load_merged_dataset(
    timeframe: str = "5M",
    max_rows: Optional[int] = None,
    tail_rows: Optional[int] = None,
    include_structure: bool = True,
    include_funding: bool = True,
) -> pd.DataFrame:
    """
    Load and merge klines + structure + funding rate into a single DataFrame.
    This is the primary entry point for the training pipeline.

    Returns a clean DataFrame with DatetimeIndex (UTC) containing:
    - OHLCV data
    - Pre-computed market structure features (BOS, CHoCH, swings)
    - Funding rate data (forward-filled to kline frequency)
    """
    # 1. Load klines
    df = load_klines(timeframe, max_rows=max_rows, tail_rows=tail_rows)

    # 2. Merge structure data
    if include_structure:
        struct_df = load_structure(timeframe)
        if not struct_df.empty:
            df = df.join(struct_df, how="left")
            log.info(f"Merged structure data: {len(struct_df.columns)} new columns")

    # 3. Merge funding rate (forward-filled to kline frequency)
    if include_funding:
        funding_df = load_funding_rate()
        if not funding_df.empty:
            df = df.join(funding_df, how="left")
            df["funding_rate"] = df["funding_rate"].ffill().fillna(0.0001)
            log.info("Merged funding rate data (forward-filled)")

    # 4. Convert structure columns to numeric
    for col in _STRUCTURE_EXTRA_COLS:
        if col in df.columns:
            if df[col].dtype == object:
                # Encode string columns as categoricals
                if col in ("structure", "break_direction", "structure_event"):
                    df[col] = df[col].fillna("none")
                    df[f"{col}_encoded"] = pd.Categorical(df[col]).codes
                else:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # 5. Fill remaining NaN with 0
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].fillna(0)

    log.info(
        f"Final merged dataset: {len(df):,} rows × {len(df.columns)} columns | "
        f"Date range: {df.index[0]} → {df.index[-1]}"
    )
    return df


def get_available_timeframes() -> List[Dict[str, str]]:
    """Return list of available timeframes from local data."""
    klines_dir = _DATA_ROOT / "klines"
    if not klines_dir.exists():
        return []
    
    result = []
    for csv_file in sorted(klines_dir.glob("BTCUSDT_*.csv")):
        tf = csv_file.stem.split("_")[1]  # e.g. "5M"
        size_mb = csv_file.stat().st_size / (1024 * 1024)
        result.append({
            "timeframe": tf,
            "filename": csv_file.name,
            "size_mb": round(size_mb, 1),
        })
    return result


def get_dataset_info(timeframe: str = "5M") -> Dict:
    """Return summary metadata about a specific dataset."""
    try:
        df = load_klines(timeframe, max_rows=5)
        # Count total rows without loading entire file
        path = _DATA_ROOT / "klines" / f"BTCUSDT_{timeframe}.csv"
        total_rows = sum(1 for _ in open(path)) - 1

        return {
            "timeframe": timeframe,
            "total_rows": total_rows,
            "columns": list(df.columns),
            "size_mb": round(path.stat().st_size / (1024 * 1024), 1),
            "has_structure": (_DATA_ROOT / "structure" / f"BTCUSDT_{timeframe}_structure.csv").exists(),
            "has_funding_rate": (_DATA_ROOT / "BTCUSDT_funding_rate.csv").exists(),
        }
    except Exception as e:
        return {"error": str(e)}
