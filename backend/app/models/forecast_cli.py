"""
MarketFlux – Live Forecast CLI
Runs the forecasting engine on live data and logs the prediction to Supabase.

Usage:
    python -m backend.app.models.forecast_cli --symbol BTCUSDT --interval 15m --sentiment 0.5
"""

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running as a module or directly
sys.path.insert(0, str(Path(__file__).parents[4]))

from backend.app.data.crypto_provider import fetch_ohlcv, get_live_price
from backend.app.models.forecasting_engine import run_forecast

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("marketflux.forecast")

def log_forecast_to_supabase(forecast_result: dict) -> None:
    try:
        from supabase import create_client
        from backend.app.config.settings import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            log.warning("Supabase credentials not set. Skipping log to Supabase.")
            return

        client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        
        # We store outcome_status as PENDING for now.
        payload = {
            "symbol": forecast_result["symbol"],
            "timeframe": forecast_result["timeframe"],
            "forecast_time": forecast_result["signal_timestamp"],
            "ml_signal": forecast_result["ml_signal"],
            "rule_signal": forecast_result["rule_signal"],
            "final_decision": forecast_result["final_signal"],
            "confidence_score": forecast_result["confidence_score"],
            "entry_price": forecast_result["current_price"],
            "predicted_price": forecast_result["predicted_price"],
            "outcome_status": "PENDING"
        }

        response = client.table("live_forecasts").insert(payload).execute()
        log.info(f"Successfully logged forecast to Supabase.")
    except Exception as e:
        log.error(f"Failed to log forecast to Supabase: {e}")

def main():
    parser = argparse.ArgumentParser(description="MarketFlux Forecast CLI")
    parser.add_argument("--symbol", default="BTCUSDT", help="Symbol e.g. BTCUSDT")
    parser.add_argument("--interval", default="15m", help="Timeframe e.g. 15m, 1h")
    parser.add_argument("--sentiment", type=float, default=0.0, help="News sentiment (-1.0 to 1.0)")
    parser.add_argument("--high-impact", action="store_true", help="Flag if currently in high impact news window")
    
    args = parser.parse_args()

    log.info(f"Generating live forecast for {args.symbol} {args.interval} ...")
    
    try:
        # Get live data
        df = fetch_ohlcv(args.symbol, args.interval, limit=150)
        live_price, source = get_live_price(args.symbol)
        
        # Run forecast
        result = run_forecast(
            df_raw=df,
            symbol=args.symbol,
            market_type="crypto",
            timeframe=args.interval,
            live_price=live_price,
            price_source=source,
            news_sentiment=args.sentiment,
            is_high_impact_news_window=args.high_impact
        )
        
        # Display
        print("\n" + "="*50)
        print(f"Forecast for {args.symbol} ({args.interval})")
        print("="*50)
        print(f"Current Price   : ${result['current_price']:.4f}")
        print(f"ML Signal       : {result['ml_signal']} (Conf: {result['confidence_score']:.2f})")
        print(f"Rule Signal     : {result['rule_signal']}")
        print(f"Final Decision  : {result['final_signal']}")
        print(f"Target Price    : ${result['predicted_price']:.4f}")
        print("="*50 + "\n")
        
        # Log to Supabase
        log_forecast_to_supabase(result)

    except Exception as e:
        log.error(f"Forecast failed: {e}", exc_info=True)

if __name__ == "__main__":
    main()
