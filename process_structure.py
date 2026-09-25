import requests
import pandas as pd
import numpy as np
import time
from pathlib import Path
from datetime import datetime, timezone

# ============================================================
# CONFIGURATION
# ============================================================

SYMBOL = "BTCUSDT"
START_DATE = "2016-01-01"
END_DATE = "2026-09-18"

# Binance Futures API
BASE_URL = "https://fapi.binance.com"

# Timeframes for Klines (OHLCV) and Structure Analysis
# Format: { "Label": "Binance_Interval" }
TIMEFRAMES = {
    "4H": "4h",
    "1H": "1h",
    "15M": "15m",
    "5M": "5m",
}

OI_PERIOD = "1h"
SWING_LEFT = 3
SWING_RIGHT = 3

# Directories
BASE_DIR = Path("data/btcusdt_futures")
KLINES_DIR = BASE_DIR / "klines"
STRUCTURE_DIR = BASE_DIR / "structure"

# Create directories if they don't exist
BASE_DIR.mkdir(parents=True, exist_ok=True)
KLINES_DIR.mkdir(parents=True, exist_ok=True)
STRUCTURE_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# HELPERS
# ============================================================

def timestamp_ms(date_string):
    dt = datetime.fromisoformat(date_string)
    dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)

# ============================================================
# DOWNLOADERS
# ============================================================

def download_klines():
    print("\n--- Downloading OHLCV Klines ---")
    start_ms = timestamp_ms(START_DATE)
    end_ms = timestamp_ms(END_DATE)

    for label, interval in TIMEFRAMES.items():
        print(f"\nDownloading {label} klines...")
        start = start_ms
        rows = []

        while start < end_ms:
            url = f"{BASE_URL}/fapi/v1/klines"
            params = {
                "symbol": SYMBOL,
                "interval": interval,
                "startTime": start,
                "endTime": end_ms,
                "limit": 1500
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if not data:
                break

            rows.extend(data)
            last_time = data[-1][0]
            start = last_time + 1
            print(f"Records: {len(rows):,}", end="\r")
            time.sleep(0.2)

        if not rows:
            print(f"No {label} data found.")
            continue

        df = pd.DataFrame(rows, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_base", "taker_quote", "ignore"
        ])
        
        # Format types
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        df = df.drop_duplicates(subset=["open_time"]).sort_values("open_time").reset_index(drop=True)

        output_path = KLINES_DIR / f"{SYMBOL}_{label}.csv"
        df.to_csv(output_path, index=False)
        print(f"\nSaved {len(df):,} {label} kline records to {output_path}")

def download_funding():
    print("\n--- Downloading Funding Rate ---")
    start = timestamp_ms(START_DATE)
    end = timestamp_ms(END_DATE)
    rows = []

    while start < end:
        url = f"{BASE_URL}/fapi/v1/fundingRate"
        params = {"symbol": SYMBOL, "startTime": start, "endTime": end, "limit": 1000}
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if not data:
            break

        rows.extend(data)
        start = data[-1]["fundingTime"] + 1
        print(f"Funding records: {len(rows):,}", end="\r")
        time.sleep(0.2)

    df = pd.DataFrame(rows)
    if df.empty:
        print("\nNo funding data found.")
        return

    df["fundingTime"] = pd.to_datetime(df["fundingTime"], unit="ms", utc=True)
    df["fundingRate"] = pd.to_numeric(df["fundingRate"], errors="coerce")
    df = df.drop_duplicates(subset=["fundingTime"]).sort_values("fundingTime").reset_index(drop=True)
    df.to_csv(BASE_DIR / f"{SYMBOL}_funding_rate.csv", index=False)
    print(f"\nSaved {len(df):,} funding records.")

def download_open_interest():
    print("\n--- Downloading Open Interest ---")
    start = timestamp_ms(START_DATE)
    end = timestamp_ms(END_DATE)
    rows = []

    while start < end:
        url = f"{BASE_URL}/futures/data/openInterestHist"
        params = {"symbol": SYMBOL, "period": OI_PERIOD, "startTime": start, "endTime": end, "limit": 500}
        
        response = requests.get(url, params=params, timeout=30)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 400:
                print(f"\nWarning: Open Interest fetch stopped (API Limit). Binance only provides the last 30 days.")
                break
            else:
                raise
        data = response.json()

        if not data:
            break

        rows.extend(data)
        start = int(data[-1]["timestamp"]) + 1
        print(f"Open interest records: {len(rows):,}", end="\r")
        time.sleep(0.2)

    df = pd.DataFrame(rows)
    if df.empty:
        print("\nNo open interest data found.")
        return

    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df["sumOpenInterest"] = pd.to_numeric(df["sumOpenInterest"], errors="coerce")
    df["sumOpenInterestValue"] = pd.to_numeric(df["sumOpenInterestValue"], errors="coerce")
    df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    df.to_csv(BASE_DIR / f"{SYMBOL}_open_interest.csv", index=False)
    print(f"\nSaved {len(df):,} open-interest records.")

# ============================================================
# STRUCTURE PROCESSORS
# ============================================================

def detect_confirmed_swings(df):
    df = df.copy()
    df["swing_high"] = 0.0
    df["swing_low"] = 0.0
    highs, lows = df["high"].values, df["low"].values

    for i in range(SWING_LEFT, len(df) - SWING_RIGHT):
        current_high, current_low = highs[i], lows[i]
        left_highs = highs[i - SWING_LEFT:i]
        right_highs = highs[i + 1:i + SWING_RIGHT + 1]
        left_lows = lows[i - SWING_LEFT:i]
        right_lows = lows[i + 1:i + SWING_RIGHT + 1]

        # Swing High
        if current_high > max(left_highs) and current_high >= max(right_highs):
            df.loc[i + SWING_RIGHT, "swing_high"] = current_high
            
        # Swing Low
        if current_low < min(left_lows) and current_low <= min(right_lows):
            df.loc[i + SWING_RIGHT, "swing_low"] = current_low

    return df

def detect_structure(df):
    df = df.copy()
    
    # Event Flags
    for col in ["bos_bullish", "bos_bearish", "choch_bullish", "choch_bearish", "break_confirmed_close"]:
        df[col] = 0

    df["broken_swing_level"] = np.nan
    df["break_candle_time"] = pd.Series(pd.NaT, index=df.index, dtype='datetime64[ns, UTC]')
    df["break_direction"] = ""
    df["structure_event"] = ""
    df["structure"] = "neutral"

    last_swing_high, last_swing_low = np.nan, np.nan
    previous_structure = "neutral"
    high_broken, low_broken = False, False

    for i in range(len(df)):
        close = df.loc[i, "close"]
        candle_time = df.loc[i, "open_time"]

        if df.loc[i, "swing_high"] > 0:
            last_swing_high = df.loc[i, "swing_high"]
            high_broken = False
        if df.loc[i, "swing_low"] > 0:
            last_swing_low = df.loc[i, "swing_low"]
            low_broken = False

        bullish_break = not np.isnan(last_swing_high) and close > last_swing_high and not high_broken
        bearish_break = not np.isnan(last_swing_low) and close < last_swing_low and not low_broken

        if bullish_break:
            high_broken = True
            if previous_structure == "bearish":
                df.loc[i, "choch_bullish"] = 1
                df.loc[i, "structure_event"] = "CHoCH_BULLISH"
            else:
                df.loc[i, "bos_bullish"] = 1
                df.loc[i, "structure_event"] = "BOS_BULLISH"

            df.loc[i, ["broken_swing_level", "break_candle_time", "break_confirmed_close", "break_direction"]] = [last_swing_high, candle_time, 1, "bullish"]
            previous_structure = "bullish"

        elif bearish_break:
            low_broken = True
            if previous_structure == "bullish":
                df.loc[i, "choch_bearish"] = 1
                df.loc[i, "structure_event"] = "CHoCH_BEARISH"
            else:
                df.loc[i, "bos_bearish"] = 1
                df.loc[i, "structure_event"] = "BOS_BEARISH"

            df.loc[i, ["broken_swing_level", "break_candle_time", "break_confirmed_close", "break_direction"]] = [last_swing_low, candle_time, 1, "bearish"]
            previous_structure = "bearish"

        df.loc[i, "structure"] = previous_structure

    return df

def add_structure_levels(df):
    df = df.copy()
    df["last_swing_high"] = df["swing_high"].replace(0, np.nan).ffill()
    df["last_swing_low"] = df["swing_low"].replace(0, np.nan).ffill()
    return df

def process_timeframe(label):
    print(f"\nProcessing Structure for {label}...")
    input_path = KLINES_DIR / f"{SYMBOL}_{label}.csv"
    
    if not input_path.exists():
        print(f"Missing file: {input_path}")
        return

    df = pd.read_csv(input_path)
    df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
    
    # Process
    df = detect_confirmed_swings(df)
    df = detect_structure(df)
    df = add_structure_levels(df)

    # Clean data types
    df[["swing_high", "swing_low"]] = df[["swing_high", "swing_low"]].fillna(0)
    int_cols = ["bos_bullish", "bos_bearish", "choch_bullish", "choch_bearish", "break_confirmed_close"]
    df[int_cols] = df[int_cols].astype(int)

    # Save
    output_path = STRUCTURE_DIR / f"{SYMBOL}_{label}_structure.csv"
    df.to_csv(output_path, index=False)

    print(f"Bullish BOS/CHoCH: {df['bos_bullish'].sum():,} / {df['choch_bullish'].sum():,}")
    print(f"Bearish BOS/CHoCH: {df['bos_bearish'].sum():,} / {df['choch_bearish'].sum():,}")
    print(f"Saved: {output_path}")

# ============================================================
# EXECUTION
# ============================================================

if __name__ == "__main__":
    
    # 1. Download all required data
    # download_klines()
    # download_funding()
    # download_open_interest()
    
    print("\n======================================")
    print("DOWNLOAD COMPLETE - STARTING STRUCTURE")
    print("======================================")

    # 2. Process structure for each timeframe
    for label in TIMEFRAMES.keys():
        process_timeframe(label)

    print("\n======================================")
    print("PIPELINE EXECUTION COMPLETE")
    print("======================================")