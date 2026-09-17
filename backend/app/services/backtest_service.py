"""
MarketFlux – Quantitative Backtesting Engine
Simulates historical execution using actual market candles, SMC feature engineering,
and trained ML models or confluence scoring. Computes Sharpe ratio, drawdown, and equity curves.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import joblib

from ..config.settings import MODEL_DIR, CRYPTO_PAIRS, FOREX_PAIRS
from ..data.crypto_provider import fetch_ohlcv as crypto_ohlcv
from ..data.forex_provider import fetch_dukascopy_ohlcv
from ..models.feature_engineering import add_features, get_feature_cols
from ..models.forecasting_engine import calculate_confluence_score

log = logging.getLogger("marketflux.backtest")


def run_backtest_simulation(
    symbol: str = "BTCUSDT",
    timeframe: str = "5m",
    limit: int = 1000,
    starting_balance: float = 10000.0,
    risk_per_trade_pct: float = 1.5,
    spread: float = 1.0,
    commission: float = 1.5,
    slippage_pct: float = 0.02,
    model_id: Optional[str] = None,
    min_confidence: float = 0.60,
) -> Dict[str, Any]:
    """
    Simulates trading over actual historical candles.
    """
    log.info(f"Running backtest for {symbol} ({timeframe}, {limit} bars)...")

    # 1. Fetch real market candles
    is_crypto = symbol in CRYPTO_PAIRS or symbol.endswith("USDT")
    if is_crypto:
        df_raw = crypto_ohlcv(symbol, timeframe, limit=limit)
    else:
        df_raw = fetch_dukascopy_ohlcv(symbol, timeframe, limit=limit)
        if df_raw is None or df_raw.empty:
            raise RuntimeError(f"No market data available for backtesting {symbol}")

    # 2. Add features
    df = add_features(df_raw)
    feature_cols = get_feature_cols(df)
    df = df.dropna(subset=feature_cols).copy()

    if len(df) < 50:
        raise RuntimeError("Not enough candles after feature engineering to conduct a reliable backtest.")

    # 3. Load Model if specified
    model = None
    if model_id:
        model_path = MODEL_DIR / f"{model_id}.joblib"
        if model_path.exists():
            try:
                model = joblib.load(model_path)
                log.info(f"Using ML model: {model_id}")
            except Exception as e:
                log.warning(f"Failed to load model {model_id}: {e}")

    # 4. Step-by-Step Simulation Loop
    capital = starting_balance
    peak_capital = starting_balance
    trades = []
    equity_curve = []
    drawdown_curve = []

    position = None  # None | "LONG" | "SHORT"
    entry_price = 0.0
    entry_time = None
    stop_loss = 0.0
    take_profit = 0.0
    position_size = 0.0
    risk_amount = 0.0

    trade_id_counter = 1

    for i in range(len(df)):
        row = df.iloc[i]
        bar_time = str(df.index[i])
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        atr = float(row.get("atr_14", close * 0.01))

        # Check existing position
        if position is not None:
            exit_triggered = False
            exit_price = 0.0
            exit_reason = ""

            if position == "LONG":
                if low <= stop_loss:
                    exit_triggered = True
                    exit_price = stop_loss * (1.0 - slippage_pct / 100.0)
                    exit_reason = "STOP_LOSS"
                elif high >= take_profit:
                    exit_triggered = True
                    exit_price = take_profit * (1.0 - slippage_pct / 100.0)
                    exit_reason = "TAKE_PROFIT"
            elif position == "SHORT":
                if high >= stop_loss:
                    exit_triggered = True
                    exit_price = stop_loss * (1.0 + slippage_pct / 100.0)
                    exit_reason = "STOP_LOSS"
                elif low <= take_profit:
                    exit_triggered = True
                    exit_price = take_profit * (1.0 + slippage_pct / 100.0)
                    exit_reason = "TAKE_PROFIT"

            if exit_triggered:
                # Realize P&L
                if position == "LONG":
                    gross_pnl = (exit_price - entry_price) * position_size
                else:
                    gross_pnl = (entry_price - exit_price) * position_size

                net_pnl = gross_pnl - commission
                capital += net_pnl
                pnl_pct = (net_pnl / max(capital - net_pnl, 1.0)) * 100.0

                trades.append({
                    "id": f"TRD-{trade_id_counter:04d}",
                    "side": position,
                    "entry_time": entry_time,
                    "exit_time": bar_time,
                    "entry_price": round(entry_price, 5),
                    "exit_price": round(exit_price, 5),
                    "amount": round(position_size, 4),
                    "pnl": round(net_pnl, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "exit_reason": exit_reason,
                    "running_equity": round(capital, 2),
                })
                trade_id_counter += 1
                position = None

        # If flat, evaluate entry signal
        if position is None and i < len(df) - 1:
            signal_side = None
            conf_score = 50

            if model is not None and hasattr(model, "predict_proba"):
                try:
                    feat_vec = row[model.feature_cols].values.reshape(1, -1)
                    prob_win = model.predict_proba(feat_vec)
                    if prob_win >= min_confidence:
                        signal_side = "LONG"
                        conf_score = int(prob_win * 100)
                    elif prob_win <= (1.0 - min_confidence):
                        signal_side = "SHORT"
                        conf_score = int((1.0 - prob_win) * 100)
                except Exception:
                    pass

            if signal_side is None:
                # Fallback to confluence score
                direction, score, _ = calculate_confluence_score(row)
                if score >= int(min_confidence * 100):
                    if "LONG" in direction:
                        signal_side = "LONG"
                        conf_score = score
                    elif "SHORT" in direction:
                        signal_side = "SHORT"
                        conf_score = score

            if signal_side:
                # Position sizing based on risk per trade
                risk_cash = capital * (risk_per_trade_pct / 100.0)
                sl_dist = max(atr * 1.5, close * 0.002)

                if signal_side == "LONG":
                    entry_price = close * (1.0 + slippage_pct / 100.0)
                    stop_loss = entry_price - sl_dist
                    take_profit = entry_price + (sl_dist * 2.0)  # 2:1 Reward to Risk
                else:
                    entry_price = close * (1.0 - slippage_pct / 100.0)
                    stop_loss = entry_price + sl_dist
                    take_profit = entry_price - (sl_dist * 2.0)

                position = signal_side
                entry_time = bar_time
                position_size = risk_cash / sl_dist
                risk_amount = risk_cash

        # Track equity & drawdown curve
        if capital > peak_capital:
            peak_capital = capital
        dd_pct = ((peak_capital - capital) / peak_capital) * 100.0

        equity_curve.append({"time": bar_time, "value": round(capital, 2)})
        drawdown_curve.append({"time": bar_time, "value": round(-dd_pct, 2)})

    # Calculate overall metrics
    total_trades = len(trades)
    winning_trades = [t for t in trades if t["pnl"] > 0]
    losing_trades = [t for t in trades if t["pnl"] <= 0]
    win_count = len(winning_trades)
    loss_count = len(losing_trades)
    win_rate = (win_count / total_trades * 100.0) if total_trades > 0 else 0.0

    total_win_pnl = sum(t["pnl"] for t in winning_trades)
    total_loss_pnl = abs(sum(t["pnl"] for t in losing_trades))
    profit_factor = (total_win_pnl / total_loss_pnl) if total_loss_pnl > 0 else (99.0 if total_win_pnl > 0 else 0.0)

    net_pnl = capital - starting_balance
    total_return_pct = (net_pnl / starting_balance) * 100.0
    max_dd = max([abs(d["value"]) for d in drawdown_curve]) if drawdown_curve else 0.0

    # Sharpe ratio calculation on trade returns
    trade_pcts = [t["pnl_pct"] for t in trades]
    if len(trade_pcts) > 1 and np.std(trade_pcts) > 0:
        sharpe = (np.mean(trade_pcts) / np.std(trade_pcts)) * math.sqrt(252)
    else:
        sharpe = 0.0

    avg_trade = (net_pnl / total_trades) if total_trades > 0 else 0.0
    largest_win = max([t["pnl"] for t in trades], default=0.0)
    largest_loss = min([t["pnl"] for t in trades], default=0.0)

    # Trade return distribution buckets (histogram)
    distribution = {"huge_win": 0, "win": 0, "loss": 0, "huge_loss": 0}
    for t in trades:
        p = t["pnl_pct"]
        if p >= 2.0:
            distribution["huge_win"] += 1
        elif p > 0:
            distribution["win"] += 1
        elif p <= -2.0:
            distribution["huge_loss"] += 1
        else:
            distribution["loss"] += 1

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "bars_tested": len(df),
        "starting_balance": starting_balance,
        "final_equity": round(capital, 2),
        "net_pnl": round(net_pnl, 2),
        "return_pct": round(total_return_pct, 2),
        "win_rate": round(win_rate, 1),
        "profit_factor": round(profit_factor, 2),
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "total_trades": total_trades,
        "winning_trades": win_count,
        "losing_trades": loss_count,
        "avg_trade": round(avg_trade, 2),
        "largest_win": round(largest_win, 2),
        "largest_loss": round(largest_loss, 2),
        "equity_curve": equity_curve,
        "drawdown_curve": drawdown_curve,
        "trade_distribution": distribution,
        "recent_trades": trades[-50:],
    }
