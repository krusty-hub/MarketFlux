# Improve and Refactor AI Trading Forecasting Application

This plan covers the full refactor from a monolithic Flask app into a modern FastAPI + React/Vite architecture, with a structured self-improvement loop via Supabase as the persistent trading memory layer.

---

## User Review Required

> [!WARNING]
> **Timeframe Compatibility:** The current model is hardcoded to 2H/4H/8H/12H horizons. We will start the first version on **Binance 5m** data and use the 2R/1R target labelling approach. Supporting other timeframes will require separate training runs.

> [!IMPORTANT]
> **Retraining Trigger:** The model will NOT auto-retrain after every trade. Retraining is triggered **manually or on a schedule** (e.g. every 500–2000 new trades) and the new model only replaces the old one if it outperforms on out-of-sample data.

---

## Architecture Overview

```
Market Data (Binance 5m / Dukascopy Forex)
    ↓
Feature Engine  [feature_engineering.py]
(SMC/ICT + indicators + market structure)
    ↓
AI Model  [forecasting_engine.py]
    ↓
Trade Decision: BUY / SELL / NO TRADE
    ↓
Signal Logger ─────────────────────────┐
    ↓                                  │
Supabase (trades + model_versions)     │
    ↓                                  │
Trade Outcome (WIN / LOSS / BE)        │
    ↓                                  │
Performance Analyzer                   │
    ↓                                  │
Condition Grouping & Insights          │
    ↓                                  │
Periodic Retraining (new model) ◄──────┘
    ↓
Model Comparison → Deploy if better
```

---

## Database Schema (Supabase / PostgreSQL)

### Table: `trades`
Full reasoning context stored alongside every decision.

| Field | Type | Description |
|-------|------|-------------|
| `id` | uuid | Primary key |
| `timestamp` | timestamptz | Signal generation time |
| `pair` | text | e.g. `BTC/USDT`, `EUR/USD` |
| `timeframe` | text | e.g. `5m`, `1h`, `4h` |
| `market_price` | numeric | Price at decision time |
| `direction` | text | `BUY` / `SELL` / `NO_TRADE` |
| `entry` | numeric | Suggested entry level |
| `stop_loss` | numeric | Stop loss level |
| `take_profit` | numeric | Take profit level |
| `position_size` | numeric | Calculated position size |
| `market_regime` | text | `TRENDING` / `RANGING` |
| `trend` | text | `BULLISH` / `BEARISH` / `NEUTRAL` |
| `volatility` | text | `HIGH` / `MEDIUM` / `LOW` |
| `session` | text | `LONDON` / `NY` / `ASIA` |
| `liquidity_sweep` | boolean | Liquidity sweep detected |
| `bos` | boolean | Break of Structure |
| `choch` | boolean | Change of Character |
| `order_block` | boolean | Order block present |
| `fvg` | boolean | Fair Value Gap present |
| `model_confidence` | numeric | Model confidence score 0–1 |
| `model_version` | text | Model version that made this call |
| `actual_outcome` | text | `WIN` / `LOSS` / `BE` (filled later) |
| `actual_close_price` | numeric | Price when trade closed |
| `pnl` | numeric | Realised P&L |
| `max_drawdown` | numeric | Max adverse excursion |
| `error_type` | text | e.g. `false_liquidity_sweep`, `fvg_missed` |
| `evaluated_at` | timestamptz | When outcome was recorded |

### Table: `model_versions`
Tracks every trained model and its out-of-sample performance.

| Field | Type | Description |
|-------|------|-------------|
| `id` | uuid | Primary key |
| `version` | text | e.g. `v1.0`, `v1.1` |
| `training_date` | timestamptz | When training ran |
| `dataset_size` | integer | Number of samples used |
| `win_rate` | numeric | % wins on OOS test set |
| `profit_factor` | numeric | Gross profit / gross loss |
| `max_drawdown` | numeric | Max drawdown in OOS test |
| `precision` | numeric | Precision score on labels |
| `model_path` | text | Local path to `.joblib` file |
| `is_active` | boolean | Currently deployed model |

---

## The 4-Layer Learning System

### Layer 1 – Prediction
The model outputs a structured signal with confidence:
```
BUY: 72% | SELL: 18% | NO TRADE: 10%
```

### Layer 2 – Execution
The bot logs the full context (all SMC/ICT features, session, regime) to Supabase alongside the decision.

### Layer 3 – Evaluation
After the forecast period elapses, the evaluation service fetches actual price, calculates PnL and error type, then updates the `trades` row.

### Layer 4 – Periodic Retraining
After 500–2000 new trades, the analysis service groups results by condition:

```
London + liquidity_sweep + FVG  → 68% win rate  ✅
NY + no liquidity_sweep         → 43% win rate  ⚠️
Counter-trend CHoCH             → 39% win rate  ❌
```

These insights feed into new training features/rules. The new model is only promoted to `is_active = true` if it beats the current model on **out-of-sample** data.

---

## Proposed Changes

### Backend Refactoring
Migrate from Flask to a modular FastAPI structure.

---

#### [DELETE] `app.py`
#### [MODIFY] → `backend/app/data/crypto_provider.py`
- Extract Binance/Kraken/CCXT OHLCV fetching.
- Confirm endpoint: `https://data-api.binance.vision/api/v3/klines` (no auth required).
- Normalize all data into a standard `OHLCV` internal format.

#### [NEW] `backend/app/data/forex_provider.py`
- Implement Dukascopy provider (historical bid/ask + volume, no API key needed).
- Normalize to the same `OHLCV` format.

---

#### [MODIFY] → `backend/app/models/feature_engineering.py`
Full SMC/ICT feature set preserved from `Forecasting_Engine.py`, plus new additions:
- `liquidity_sweep` (prev high/low breach)
- `displacement` (body > 1.5× 20-period avg body)
- `bullish` bias flag
- Session classification (London / NY / Asia by UTC hour)
- Proper FVG and Order Block detectors

**ML target label:** For each candle, check if the next 20 candles hit a **2R take-profit before a 1R stop-loss**. This produces a binary `target` column (1 = win, 0 = loss/no-trigger).

#### [NEW] `backend/app/models/train.py`
Local-only training script:
1. Download Binance 5m historical data
2. Apply SMC/ICT feature engineering
3. Generate 2R/1R target labels
4. Train ensemble (RF + XGBoost + LightGBM)
5. Evaluate on out-of-sample split
6. Save model + log to `model_versions` table in Supabase

#### [MODIFY] → `backend/app/models/forecasting_engine.py`
(renamed from `Forecasting_Engine.py` — fixing the typo)
- Load the active model version from `model_versions`
- Run inference on latest features
- Return structured signal with all SMC context fields

---

#### [NEW] `backend/app/services/signal_service.py`
- Confluence scoring (preserved from existing engine)
- Trade direction + entry/SL/TP calculation
- Writes full signal to `trades` table in Supabase immediately

#### [NEW] `backend/app/services/evaluation_service.py`
- Scheduled job: for each `trades` row with no `actual_outcome`, check if forecast period has elapsed
- Fetch actual market price
- Determine WIN / LOSS / BE
- Update `actual_close_price`, `pnl`, `error_type`, `evaluated_at`

#### [NEW] `backend/app/services/analysis_service.py`
- Query `trades` table and group by condition combinations
- Calculate win rates per condition group
- Surface insights for the next retraining run

---

#### [NEW] `backend/app/api/routes/`
- `health.py` — `/api/health`
- `market_data.py` — `/api/market/{symbol}?timeframe=5m`
- `forecasts.py` — `/api/forecasts/run`, `/api/forecasts/status`
- `signals.py` — `/api/signals/history`, `/api/signals/performance`

#### [NEW] `backend/app/schemas/`
Pydantic models matching the `trades` and `model_versions` tables.

---

### Frontend (React + Vite + TypeScript)

#### UI Aesthetics — Modal Theme
| Token | Value |
|-------|-------|
| Canvas | `#000000`, `#181818` |
| Text | `#ddffdc`, `#8cab87` |
| Accent (Lime Pulse) | `#7fee64` |
| Border | `#485346` |
| Heading font | Goga (tight negative tracking) |
| Body font | Inter Variable |
| Button radius | 12px |
| Card radius | 8px |
| Pill radius | 9999px |
| Card padding | 32px |

**Implemented with TailwindCSS v4 + custom theme config.**

#### Components
- `Layout` — sticky nav with LIVE status badge
- `MarketSelector` — market type + instrument + timeframe dropdowns
- `SignalCard` — BUY/SELL/NO_TRADE with confidence, entry, SL, TP, SMC signals
- `ForecastChart` — price trajectory (Chart.js)
- `ProbabilityBar` — bull/bear probability visualization
- `PerformancePanel` — win rate, profit factor, top conditions from Supabase
- `ModelInfo` — active model version, training date, dataset size

#### Services
- `api.ts` — typed Axios/fetch client pointing to `VITE_API_BASE_URL`
- `supabaseClient.ts` — Supabase anon key only (never service role)
- `forecastApi.ts` — typed wrappers for forecast and signal endpoints

---

### Environment & Cleanup

#### [NEW] `.env.example`
```env
# Backend
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key   # backend only, never frontend

# Frontend (Vite)
VITE_API_BASE_URL=http://localhost:8000
VITE_SUPABASE_URL=your_supabase_project_url
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
```

> [!CAUTION]
> `SUPABASE_SERVICE_ROLE_KEY` and `SUPABASE_KEY` must **never** be exposed to the browser. Only `VITE_SUPABASE_ANON_KEY` goes to the frontend.

#### [MODIFY] `README.md`
- Remove all Render.com references
- Add local run instructions:
  ```bash
  # Backend
  uvicorn backend.app.main:app --reload --port 8000

  # Training
  python -m backend.app.models.train --symbol BTCUSDT --interval 5m --limit 1000

  # Frontend
  cd frontend && npm install && npm run dev
  ```

#### Remove from `app.py` / config
- `IS_CLOUD` detection (`RENDER`, `DYNO`, `RAILWAY_ENVIRONMENT` env vars)
- Render-specific exchange overrides
- `gunicorn` from `requirements.txt` (replaced with `uvicorn`)

---

## Verification Plan

### Automated Tests
- `backend/tests/test_crypto_provider.py` — mocked Binance responses
- `backend/tests/test_feature_engineering.py` — SMC label correctness
- `backend/tests/test_signal_service.py` — confluence scoring logic
- `backend/tests/test_schemas.py` — Pydantic model validation

### Manual Verification
1. FastAPI starts at `http://localhost:8000`, docs at `/docs`
2. Vite frontend starts at `http://localhost:5173`
3. Run forecast → signal logged to Supabase `trades` table
4. Evaluation service resolves a test trade outcome
5. Performance panel displays aggregated win/loss stats
6. UI matches the Modal theme (dark canvas, lime accent, sharp geometry)
