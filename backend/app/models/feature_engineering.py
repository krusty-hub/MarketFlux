"""
MarketFlux – Feature Engineering
Calculates SMC/ICT concepts + technical indicators from OHLCV data.
All features are derived deterministically from price/volume — no lookahead.
"""
from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np
import pandas as pd

log = logging.getLogger("marketflux.features")

# Session kill-zone hours (UTC)
_LONDON_KZ_START, _LONDON_KZ_END = 8, 10
_NY_KZ_START, _NY_KZ_END = 13, 15
_ASIA_KZ_START, _ASIA_KZ_END = 0, 3


def add_features(df: pd.DataFrame, live_price: Optional[float] = None) -> pd.DataFrame:
    """
    Add all SMC/ICT + technical indicator features to an OHLCV DataFrame.
    Input:  df with columns [open, high, low, close, volume], UTC timestamp index.
    Output: enriched df (copy).
    """
    df = df.copy()

    # ── Section 1: Basic Returns & Volatility ─────────────────────────────────
    df["ret_1"] = df["close"].pct_change(1)
    df["ret_5"] = df["close"].pct_change(5)
    df["rvol_14"] = df["ret_1"].rolling(14).std()

    # ATR
    prev_close = df["close"].shift(1)
    df["tr"] = np.maximum(
        df["high"] - df["low"],
        np.maximum(
            (df["high"] - prev_close).abs(),
            (prev_close - df["low"]).abs(),
        ),
    )
    df["atr_14"] = df["tr"].rolling(14).mean()

    # ── Section 2: Trend – Multi-EMA ─────────────────────────────────────────
    for span in [9, 21, 50, 200]:
        df[f"ema_{span}"] = df["close"].ewm(span=span, adjust=False).mean()

    df["ema_alignment"] = np.where(
        (df["ema_9"] > df["ema_21"]) & (df["ema_21"] > df["ema_50"]),  1.0,
        np.where(
            (df["ema_9"] < df["ema_21"]) & (df["ema_21"] < df["ema_50"]), -1.0,
            0.0,
        ),
    )

    # ── Section 3: RSI + MACD ─────────────────────────────────────────────────
    delta = df["close"].diff()
    gain  = delta.where(delta > 0, 0).rolling(14).mean()
    loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df["rsi_14"] = 100 - (100 / (1 + gain / (loss + 1e-9)))

    ema_12 = df["close"].ewm(span=12, adjust=False).mean()
    ema_26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"]        = ema_12 - ema_26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"]   = df["macd"] - df["macd_signal"]
    df["macd_bullish"] = (df["macd_hist"] > 0).astype(int)

    # RSI divergence
    df["rsi_high"]    = df["rsi_14"].rolling(14).max()
    df["rsi_low"]     = df["rsi_14"].rolling(14).min()
    df["price_high"]  = df["close"].rolling(14).max()
    df["price_low"]   = df["close"].rolling(14).min()
    df["bearish_divergence"] = (
        (df["close"] > df["price_high"].shift(1)) &
        (df["rsi_14"] < df["rsi_high"].shift(1))
    ).astype(int)
    df["bullish_divergence"] = (
        (df["close"] < df["price_low"].shift(1)) &
        (df["rsi_14"] > df["rsi_low"].shift(1))
    ).astype(int)

    # ── Section 4: SMC – Break of Structure (BOS) ────────────────────────────
    window = 5
    df["swing_high"] = df["high"].rolling(window=window).max()
    df["swing_low"]  = df["low"].rolling(window=window).min()
    df["bullish_bos"] = (df["close"] > df["swing_high"].shift(1)).astype(int)
    df["bearish_bos"] = (df["close"] < df["swing_low"].shift(1)).astype(int)

    # ── Section 5: SMC – Change of Character (CHoCH) ─────────────────────────
    df["higher_high"] = (df["high"] > df["high"].shift(1)).astype(int)
    df["lower_low"]   = (df["low"]  < df["low"].shift(1)).astype(int)
    df["hh_count"]    = df["higher_high"].rolling(3).sum()
    df["ll_count"]    = df["lower_low"].rolling(3).sum()
    df["choch_signal"] = (
        (df["hh_count"].shift(1) >= 2) & (df["ll_count"] >= 2)
    ).astype(int)

    # ── Section 6: SMC – Order Blocks ────────────────────────────────────────
    df["ob_signal"] = (
        (df["bullish_bos"] | df["bearish_bos"]) &
        ((df["rsi_14"] > 60) | (df["rsi_14"] < 40))
    ).astype(int)

    # ── Section 7: SMC – Fair Value Gaps (FVG) ───────────────────────────────
    df["bullish_fvg"]    = (df["low"] > df["high"].shift(2)).astype(int)
    df["bearish_fvg"]    = (df["high"] < df["low"].shift(2)).astype(int)
    df["fvg_depth_bull"] = np.where(df["bullish_fvg"], df["low"] - df["high"].shift(2), 0.0)
    df["fvg_depth_bear"] = np.where(df["bearish_fvg"], df["low"].shift(2) - df["high"], 0.0)

    # ── Section 8: ICT – Liquidity Zones + Sweep ─────────────────────────────
    win_liq = 8
    df["recent_high"] = df["high"].rolling(win_liq).max()
    df["recent_low"]  = df["low"].rolling(win_liq).min()
    df["touched_liquidity_high"] = (df["high"] >= df["recent_high"].shift(1)).astype(int)
    df["touched_liquidity_low"]  = (df["low"]  <= df["recent_low"].shift(1)).astype(int)

    # Prev candle direction
    prev_dir_up = (df["close"].shift(1) > df["open"].shift(1))

    df["liquidity_sweep_bull"] = (
        df["touched_liquidity_low"] & (df["close"] > df["close"].shift(1))
    ).astype(int)
    df["liquidity_sweep_bear"] = (
        df["touched_liquidity_high"] & (df["close"] < df["close"].shift(1))
    ).astype(int)
    df["liquidity_sweep"] = (
        df["liquidity_sweep_bull"] | df["liquidity_sweep_bear"]
    ).astype(int)

    # ── Section 9: Displacement ───────────────────────────────────────────────
    body = (df["close"] - df["open"]).abs()
    avg_body = body.rolling(20).mean()
    df["displacement"] = (body > avg_body * 1.5).astype(int)

    # ── Section 10: ICT – Session Kill Zones ─────────────────────────────────
    if hasattr(df.index, "hour"):
        hour = df.index.hour
    else:
        hour = pd.Series(0, index=df.index)
    df["london_kz"] = ((hour >= _LONDON_KZ_START) & (hour < _LONDON_KZ_END)).astype(int)
    df["ny_kz"]     = ((hour >= _NY_KZ_START)     & (hour < _NY_KZ_END)).astype(int)
    df["asia_kz"]   = ((hour >= _ASIA_KZ_START)   & (hour < _ASIA_KZ_END)).astype(int)
    df["in_kz"]     = (df["london_kz"] | df["ny_kz"]).astype(int)
    df["session"]   = np.where(
        df["london_kz"] == 1, "LONDON",
        np.where(df["ny_kz"] == 1, "NY",
        np.where(df["asia_kz"] == 1, "ASIA", "NONE")),
    )

    # ── Section 11: Volume Analysis ───────────────────────────────────────────
    df["vol_ma_20"]  = df["volume"].rolling(20).mean()
    df["vol_ratio"]  = df["volume"] / (df["vol_ma_20"] + 1e-9)
    df["vol_spike"]  = (df["vol_ratio"] > 1.5).astype(int)
    df["high_vol_break"] = (
        df["vol_spike"] & ((df["ret_1"] > 0.005) | (df["ret_1"] < -0.005))
    ).astype(int)

    # ── Section 12: Trend Strength + Regime ──────────────────────────────────
    df["dist_from_ema21"] = (df["close"] - df["ema_21"]) / (df["atr_14"] + 1e-9)
    df["trend_strength"]  = df["ema_alignment"] * np.tanh(df["dist_from_ema21"])
    df["regime"] = np.where(
        (df["rvol_14"] > df["rvol_14"].rolling(20).mean() * 1.2) |
        (df["dist_from_ema21"].abs() > 1.5),
        1, 0,
    )

    # ── Section 13: Support / Resistance ─────────────────────────────────────
    win_sr = 10
    df["support_1"]    = df["low"].rolling(win_sr).min()
    df["resistance_1"] = df["high"].rolling(win_sr).max()
    df["dist_to_support_atr"]    = (df["close"] - df["support_1"])    / (df["atr_14"] + 1e-9)
    df["dist_to_resistance_atr"] = (df["resistance_1"] - df["close"]) / (df["atr_14"] + 1e-9)

    # ── Section 14: Live Price Context ───────────────────────────────────────
    if live_price is not None:
        df["live_price"]    = live_price
        df["price_context"] = (live_price - df["close"]) / (df["atr_14"] + 1e-9)

    # ── Section 15: Simple bullish bias flag ─────────────────────────────────
    df["bullish"] = (df["close"] > df["open"]).astype(int)

    return df


def get_feature_cols(df: pd.DataFrame) -> List[str]:
    """
    Return the list of engineered feature columns to use for ML training/inference.
    Excludes raw OHLCV, intermediate calculations, and lookahead columns.
    """
    _exclude = {
        "open", "high", "low", "close", "volume",
        "tr", "swing_high", "swing_low",
        "rsi_high", "rsi_low", "price_high", "price_low",
        "recent_high", "recent_low", "vol_ma_20",
        "live_price", "session", "target", # Exclude target and string/non-numeric
    }
    # Also exclude raw returns used only for target generation
    return [
        col for col in df.columns
        if col not in _exclude
        and not col.startswith("ret_")
        and df[col].dtype in [np.float64, np.float32, np.int64, np.int32, np.int8, np.uint8, int, float]
    ]


def create_2r_1r_target(df: pd.DataFrame, risk_pct: float = 0.005, lookahead: int = 20) -> pd.DataFrame:
    """
    Create binary training label:
      target = 1 if the next `lookahead` candles hit a 2R take-profit BEFORE a 1R stop-loss.
      target = 0 otherwise.

    risk_pct:  fraction of entry price used as 1R (default 0.5%)
    lookahead: number of future candles to check (default 20)
    """
    df = df.copy()
    targets = np.zeros(len(df), dtype=np.int8)

    for i in range(len(df) - lookahead):
        entry = float(df["close"].iloc[i])
        risk  = entry * risk_pct
        tp    = entry + risk * 2   # 2R
        sl    = entry - risk       # 1R

        future   = df.iloc[i + 1 : i + 1 + lookahead]
        hit_tp   = (future["high"] >= tp).any()
        hit_sl   = (future["low"]  <= sl).any()

        if hit_tp and not hit_sl:
            targets[i] = 1
        elif hit_tp and hit_sl:
            # Whichever happened first wins
            tp_idx = future[future["high"] >= tp].index[0]
            sl_idx = future[future["low"]  <= sl].index[0]
            targets[i] = 1 if tp_idx <= sl_idx else 0

    df["target"] = targets
    log.info(
        f"Target distribution — 1 (WIN): {targets.sum()} | 0 (LOSS): {(targets==0).sum()} "
        f"| Win rate: {targets.mean():.1%}"
    )
    return df
