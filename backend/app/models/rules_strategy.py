import numpy as np
import pandas as pd
from typing import Dict, Union

class TradingRulesStrategy:
    def __init__(self, rsi_period=14, ema_fast=12, ema_slow=26, atr_period=14, atr_ma_period=20, breakout_period=10):
        self.rsi_period = rsi_period
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.atr_period = atr_period
        self.atr_ma_period = atr_ma_period
        self.breakout_period = breakout_period

    def calculate_technical_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculates Technical Indicators (EMA, RSI, ATR, Breakout levels) deterministically."""
        df = df.copy()

        # 1. ATR Calculation (14-period)
        prev_close = df["close"].shift(1)
        tr = np.maximum(
            df["high"] - df["low"],
            np.maximum(
                (df["high"] - prev_close).abs(),
                (prev_close - df["low"]).abs(),
            ),
        )
        df["atr_14"] = tr.rolling(self.atr_period).mean()
        df["atr_ma"] = df["atr_14"].rolling(self.atr_ma_period).mean()

        # 2. EMA Calculation
        df["ema_fast"] = df["close"].ewm(span=self.ema_fast, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=self.ema_slow, adjust=False).mean()

        # 3. RSI Calculation
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / (loss + 1e-9)
        df["rsi_14"] = 100 - (100 / (1 + rs))

        # 4. Breakout Support / Resistance
        df["support_1"] = df["low"].rolling(self.breakout_period).min().shift(1)
        df["resistance_1"] = df["high"].rolling(self.breakout_period).max().shift(1)

        return df

    def evaluate_signals(self, df: pd.DataFrame, news_sentiment: float, is_high_impact_news_window: bool) -> Dict[str, Union[str, float, None]]:
        """
        Combines technicals and news metadata to output structured action signals.
        Returns dictionary with: 'signal' (BUY/SELL/HOLD), 'stop_loss', 'take_profit'.
        """
        current_row = df.iloc[-1]
        close_price = float(current_row["close"])
        
        result = {
            "signal": "HOLD",
            "stop_loss": None,
            "take_profit": None
        }

        # Rule 1: High-impact economic news filter
        if is_high_impact_news_window:
            return result  # Pause trading during unpredictable volatility spikes

        atr = float(current_row.get("atr_14", 0))
        atr_ma = float(current_row.get("atr_ma", 0))
        rsi = float(current_row.get("rsi_14", 50))
        ema_fast = float(current_row.get("ema_fast", close_price))
        ema_slow = float(current_row.get("ema_slow", close_price))
        support = float(current_row.get("support_1", close_price))
        resistance = float(current_row.get("resistance_1", close_price))

        # Volatility check
        is_high_volatility = atr > atr_ma
        
        # Trend check
        bullish_ema = ema_fast > ema_slow
        bearish_ema = ema_fast < ema_slow

        # Breakout logic
        breakout_up = close_price > resistance
        breakout_down = close_price < support

        # Sentiment alignment (-1.0 to +1.0)
        sentiment_bullish = news_sentiment > 0.1
        sentiment_bearish = news_sentiment < -0.1
        is_neutral_news = -0.2 <= news_sentiment <= 0.2

        # ---------------------------------------------------------
        # Strategy Execution
        # ---------------------------------------------------------

        # Rule 4: Breakout & Trailing Volatility (Highest priority during high vol)
        if is_high_volatility:
            if breakout_up and not sentiment_bearish:
                result["signal"] = "BUY"
                result["stop_loss"] = close_price - (1.5 * atr)
                result["take_profit"] = close_price + (3.0 * atr)
                return result
            elif breakout_down and not sentiment_bullish:
                result["signal"] = "SELL"
                result["stop_loss"] = close_price + (1.5 * atr)
                result["take_profit"] = close_price - (3.0 * atr)
                return result

        # Rule 3: Mean Reversion (RSI) - only during range-bound/neutral news
        if not is_high_volatility and is_neutral_news:
            if rsi < 30:
                result["signal"] = "BUY"
                result["stop_loss"] = close_price - (1.5 * atr)
                result["take_profit"] = close_price + (2.0 * atr)
                return result
            elif rsi > 70:
                result["signal"] = "SELL"
                result["stop_loss"] = close_price + (1.5 * atr)
                result["take_profit"] = close_price - (2.0 * atr)
                return result

        # Rule 2: EMA Crossover + Volatility Filter
        if is_high_volatility:
            if bullish_ema and sentiment_bullish and rsi < 70:
                result["signal"] = "BUY"
                result["stop_loss"] = close_price - (1.5 * atr)
                result["take_profit"] = close_price + (2.5 * atr)
                return result
            elif bearish_ema and sentiment_bearish and rsi > 30:
                result["signal"] = "SELL"
                result["stop_loss"] = close_price + (1.5 * atr)
                result["take_profit"] = close_price - (2.5 * atr)
                return result

        return result
