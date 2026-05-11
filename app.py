import os
from flask import Flask, jsonify, render_template_string
# Import the real forecasting logic
from Forecasting_Engine import get_latest_forecast

app = Flask(__name__)

# (UI_TEMPLATE remains exactly as you provided)

@app.route("/")
def home():
    return render_template_string(UI_TEMPLATE)

@app.route("/health")
def health():
    return "OK", 200

@app.route("/forecast")
def forecast():
    try:
        # Use default ETHUSDT; you can also pass a query parameter e.g. ?symbol=BTCUSDT
        symbol = request.args.get("symbol", "ETHUSDT")
        data = get_latest_forecast(symbol=symbol, exchange="binance", headless=True)
        return jsonify(data)
    except Exception as e:
        return jsonify({
            "error": "Could not retrieve forecast",
            "details": str(e)
        }), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
