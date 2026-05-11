Adaptive Crypto Forecasting Engine

A machine learning-based crypto forecasting system built for short-term market prediction and volatility analysis.

The engine uses an ensemble of ML models combined with technical, volatility, momentum, and market structure features to generate adaptive forecasts for crypto assets.

Currently optimized for:

- ETH/USDT
- BTC/USDT
- SOL/USDT

Supports both Binance and Bybit market data.

---

Features

- Short-term forecasting (12H / 24H / 48H)
- Ensemble ML architecture:
  - XGBoost
  - LightGBM
  - Random Forest
- Dynamic model weighting based on validation performance
- Multi-timeframe analysis ("5m", "15m", "1h", "4h")
- Volatility and market regime detection
- Risk filtering and confidence scoring
- Forecast visualization dashboard
- Prediction history tracking

---

Forecast Output

For each forecast cycle, the engine generates:

- Predicted price direction
- Bullish/Bearish probability
- Expected price range
- Volatility level
- Confidence score
- Risk signals

---

Data Sources

- Binance REST API
- Bybit REST API
- Alpha Vantage (optional fallback)

---

Installation

pip install pandas numpy matplotlib scikit-learn xgboost lightgbm requests joblib

---

Usage

# Default (ETHUSDT)
python crypto_forecast_engine.py

# BTC forecast
python crypto_forecast_engine.py --symbol BTCUSDT

# SOL forecast using Bybit
python crypto_forecast_engine.py --symbol SOLUSDT --exchange bybit

---

Dashboard

The engine generates a visualization dashboard containing:

- Price action & Bollinger Bands
- RSI & MACD analysis
- Volume activity
- Market regime detection
- Forecast comparison
- Feature importance ranking

---

Project Goal

This project was built to explore machine learning applications in financial forecasting, with a focus on:

- directional prediction
- volatility estimation
- adaptive ensemble systems
- market regime awareness
