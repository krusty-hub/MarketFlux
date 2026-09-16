# MarketFlux

Institutional-grade AI forecasting application with live data feeds, SMC/ICT liquidity conditions detection, and probabilistic forecasting across Crypto and Forex.

## Architecture

* **Backend**: FastAPI + Python (Pandas, scikit-learn, XGBoost)
* **Frontend**: React + Vite + TypeScript (TailwindCSS v4)
* **Database / Tracking**: Supabase (PostgreSQL)

## Setup and Installation

### 1. Environment Configuration

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

You must provide your Supabase URL and Keys. 

### 2. Backend (FastAPI)

Requires Python 3.9+.

```bash
# Install dependencies
pip install -r requirements.txt

# Start the API server
uvicorn backend.app.main:app --reload --port 8000
```
*API Docs available at http://localhost:8000/docs*

### 3. Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```
*App available at http://localhost:5173*

## Model Training

The application uses an ensemble machine learning model predicting a 2R take-profit vs 1R stop-loss target. You must train the model locally to initialize it.

```bash
# Example: Train model for BTC/USDT on 5m timeframe
python -m backend.app.models.train --symbol BTCUSDT --interval 5m --limit 1000 --supabase
```

The model will be saved in the `models/` directory and logged to Supabase if `--supabase` is provided.

## 4-Layer Learning System

1. **Prediction:** Ensemble model generates a probabilistic forecast.
2. **Execution:** Full market context (SMC conditions, session, trend) is logged to the `trades` table.
3. **Evaluation:** A scheduled job resolves trade outcomes (WIN / LOSS / BE) after the forecast horizon.
4. **Analysis & Retraining:** Performance is grouped by conditions. Models are periodically retrained on out-of-sample data and promoted only if performance improves.
