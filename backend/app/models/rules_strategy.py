import numpy as np
import pandas as pd

class TradingRulesStrategy:
    def __init__(self, rsi_period=14, ema_fast=12, ema_slow=26, news_threshold=0.6):
        self.rsi_period = rsi_period
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.news_threshold = news_threshold  # Range -1.0 (bearish) to +1.0 (bullish)

    def calculate_technical_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculates Technical Indicators (EMA, RSI, ATR)."""
        # EMA Crossover
        df['ema_fast'] = df['close'].ewm(span=self.ema_fast, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=self.ema_slow, adjust=False).mean()

        # RSI calculation
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / (loss + 1e-9)
        df['rsi'] = 100 - (100 / (1 + rs))

        # ATR calculation for risk/volatility filter
        high_low = df['high'] - df['low']
        high_cp = np.abs(df['high'] - df['close'].shift())
        low_cp = np.abs(df['low'] - df['close'].shift())
        df['atr'] = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1).rolling(14).mean()

        return df

    def evaluate_rules(self, current_row: pd.Series, news_sentiment: float, is_high_impact_news_window: bool) -> str:
        """
        Combines technicals and news metadata to output: 'BUY', 'SELL', or 'HOLD'.
        """
        # Rule 1: High-impact economic news filter
        if is_high_impact_news_window:
            return "HOLD"  # Pause trading during unpredictable volatility spikes

        # Rule 2: Trend & Sentiment alignment
        bullish_technical = (current_row['ema_fast'] > current_row['ema_slow']) and (current_row['rsi'] < 70)
        bearish_technical = (current_row['ema_fast'] < current_row['ema_slow']) and (current_row['rsi'] > 30)

        # Combine news sentiment with technical strategy
        if bullish_technical and news_sentiment >= self.news_threshold:
            return "BUY"
        elif bearish_technical and news_sentiment <= -self.news_threshold:
            return "SELL"
        
        # Rule 3: Mean Reversion / Oversold bounce under neutral news
        elif current_row['rsi'] < 25 and news_sentiment > -0.2:
            return "BUY"
        elif current_row['rsi'] > 75 and news_sentiment < 0.2:
            return "SELL"

        return "HOLD"
