"""
MarketFlux – Pydantic Schemas
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ── OHLCV ─────────────────────────────────────────────────────────────────────

class OHLCVBar(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    symbol: str
    market_type: str       # "crypto" | "forex"
    timeframe: str
    data_source: str


# ── Forecast Request ──────────────────────────────────────────────────────────

class ForecastRequest(BaseModel):
    symbol: str = Field(..., example="BTCUSDT")
    market_type: str = Field(..., example="crypto")
    timeframe: str = Field("5m", example="5m")
    exchange: str = Field("binance", example="binance")


# ── Signal Response ───────────────────────────────────────────────────────────

class SMCContext(BaseModel):
    liquidity_sweep: bool
    bos: bool               # Break of Structure
    choch: bool             # Change of Character
    order_block: bool
    fvg: bool               # Fair Value Gap
    displacement: bool
    market_structure: str   # "BULLISH" | "BEARISH" | "NEUTRAL"
    regime: str             # "TRENDING" | "RANGING"
    session: str            # "LONDON" | "NY" | "ASIA" | "NONE"
    trend: str              # "BULLISH" | "BEARISH" | "NEUTRAL"
    volatility: str         # "HIGH" | "MEDIUM" | "LOW"
    active_signals: List[str]


class TradeLevel(BaseModel):
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    risk_reward_ratio: float


class SignalResponse(BaseModel):
    # Identity
    id: Optional[str] = None
    symbol: str
    market_type: str
    timeframe: str
    data_source: str

    # Signal
    signal: str             # "BUY" | "SELL" | "HOLD" | "NO_SIGNAL"
    trend_direction: str    # "STRONG_LONG" | "LONG" | "NEUTRAL" | "SHORT" | "STRONG_SHORT"
    confidence: str         # "HIGH" | "MEDIUM" | "LOW"
    confidence_score: float # 0.0–1.0
    confluence_score: int   # 0–100

    # Price info
    current_price: float
    predicted_price: float
    predicted_return_pct: float
    price_range_low: float
    price_range_high: float

    # Trade levels
    levels: TradeLevel

    # Market context
    smc: SMCContext

    # Meta
    signal_timestamp: datetime
    model_version: str
    disclaimer: str = (
        "This signal is a model-generated estimate and is NOT financial advice. "
        "Past performance does not guarantee future results."
    )


# ── Performance / Analytics ───────────────────────────────────────────────────

class ConditionGroup(BaseModel):
    condition: str
    sample_count: int
    win_rate: float
    avg_pnl: float


class PerformanceStats(BaseModel):
    total_signals: int
    wins: int
    losses: int
    breakevens: int
    win_rate: float
    profit_factor: float
    avg_error_pct: float
    buy_signals: int
    sell_signals: int
    top_conditions: List[ConditionGroup]


# ── Model Version ─────────────────────────────────────────────────────────────

class ModelVersionInfo(BaseModel):
    version: str
    training_date: datetime
    dataset_size: int
    win_rate: float
    profit_factor: float
    max_drawdown: float
    precision: float
    model_path: str
    is_active: bool
