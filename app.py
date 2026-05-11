import os
from flask import Flask, jsonify
# Import your forecasting logic from your other file
# Assuming your logic is in 'Forecasting Engine.py' renamed to 'forecasting_engine.py'
# from forecasting_engine import get_latest_forecast 

app = Flask(__name__)

@app.route("/")
def home():
    return {
        "status": "online",
        "message": "MarketFlux Adaptive Crypto Forecasting Engine is live",
        "version": "1.0.0"
    }

@app.route("/health")
def health():
    return "OK", 200

# Example route to see your predictions (you can customize this)
@app.route("/forecast")
def forecast():
    # This is where you would call your ML model functions
    # For now, it returns a placeholder
    return jsonify({
        "asset": "ETH/USDT",
        "prediction": "Bullish",
        "probability": 0.85,
        "timestamp": "2026-05-11"
    })

if __name__ == "__main__":
    # Render provides a 'PORT' environment variable. 
    # If it's not found (like when running locally), it defaults to 5000.
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
