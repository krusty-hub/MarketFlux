import os
from flask import Flask, jsonify, render_template_string, request
from Forecasting_Engine import run_forecast   # existing function
import json

app = Flask(__name__)

UI_TEMPLATE = """... (keep your existing template) ..."""

@app.route("/")
def home():
    return render_template_string(UI_TEMPLATE)

@app.route("/health")
def health():
    return "OK", 200

@app.route("/forecast")
def forecast():
    try:
        symbol = request.args.get("symbol", "ETHUSDT")
        # run_forecast normally prints and saves files – we capture its forecasts
        # However, run_forecast returns None. We need to modify it to return data.
        # Simpler: call get_latest_forecast if available, otherwise fallback.
        # For full independence, we can re-implement a minimal version here.
        # To avoid duplication, Option 1 is cleaner.
        from Forecasting_Engine import get_latest_forecast
        data = get_latest_forecast(symbol=symbol, exchange="binance", headless=True)
        return jsonify(data)
    except ImportError:
        return jsonify({"error": "get_latest_forecast not found in Forecasting_Engine.py"}), 500
    except Exception as e:
        return jsonify({"error": "Forecast failed", "details": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
