import os
from flask import Flask, jsonify, render_template_string, request
from Forecasting_Engine import get_latest_forecast

app = Flask(__name__)

# Original professional UI template – DO NOT change
UI_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>

<title>MarketFlux Engine</title>

<!-- Tailwind CDN -->
<script src="https://cdn.tailwindcss.com"></script>

<!-- Chart.js -->
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<!-- Font -->
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">

<style>
  body {
    font-family: 'Inter', sans-serif;
    background: radial-gradient(circle at top, #0f172a, #020617);
    color: white;
  }

  .glass {
    background: rgba(255, 255, 255, 0.06);
    backdrop-filter: blur(14px);
    border: 1px solid rgba(255, 255, 255, 0.08);
  }

  .glow-green { box-shadow: 0 0 20px rgba(34,197,94,0.3); }
  .glow-red { box-shadow: 0 0 20px rgba(239,68,68,0.3); }
  .glow-yellow { box-shadow: 0 0 20px rgba(234,179,8,0.3); }

  .fade-in {
    animation: fadeIn 0.6s ease-in-out;
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }
</style>
</head>

<body class="min-h-screen">

<!-- NAVBAR -->
<header class="flex items-center justify-between px-6 py-4 border-b border-white/10 glass">
  <div class="text-xl font-semibold tracking-wide">
    ⚡ MarketFlux Engine
  </div>

  <div class="flex items-center gap-3">
    <div class="w-2 h-2 rounded-full bg-green-400 animate-pulse"></div>
    <span class="text-sm text-green-300">LIVE / CONNECTED</span>
  </div>
</header>

<!-- MAIN GRID -->
<main class="p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">

  <!-- LEFT PANEL -->
  <section class="lg:col-span-3 glass rounded-2xl p-4 fade-in">
    <h2 class="text-sm text-gray-400 mb-3">Market Summary</h2>

    <div class="space-y-4 text-sm">
      <div>
        Market Regime:
        <span class="text-green-400 font-semibold">Trending</span>
      </div>

      <div>
        Volatility:
        <span class="text-yellow-400 font-semibold">Medium</span>
      </div>

      <div>
        Sentiment:
        <span class="text-green-300 font-semibold">Bullish Bias</span>
      </div>

      <div>
        Active Risk Flags:
        <span class="text-red-400 font-semibold">Low Liquidity Zone</span>
      </div>
    </div>
  </section>

  <!-- CENTER FORECAST CARDS -->
  <section class="lg:col-span-6 grid grid-cols-1 md:grid-cols-3 gap-4">

    <!-- CARD TEMPLATE -->
    <div class="glass rounded-2xl p-4 hover:scale-105 transition fade-in glow-green">
      <h3 class="text-sm text-gray-400">12H Forecast</h3>
      <p class="text-xl font-semibold mt-2">$42,800</p>

      <div class="mt-3">
        <div class="text-xs mb-1">Bull vs Bear</div>
        <div class="w-full bg-white/10 rounded-full h-2">
          <div class="bg-green-400 h-2 rounded-full" style="width: 72%"></div>
        </div>
      </div>

      <p class="text-xs mt-3 text-green-300">Confidence: HIGH (87%)</p>
    </div>

    <div class="glass rounded-2xl p-4 hover:scale-105 transition fade-in glow-yellow">
      <h3 class="text-sm text-gray-400">24H Forecast</h3>
      <p class="text-xl font-semibold mt-2">$43,120</p>

      <div class="mt-3">
        <div class="text-xs mb-1">Bull vs Bear</div>
        <div class="w-full bg-white/10 rounded-full h-2">
          <div class="bg-yellow-400 h-2 rounded-full" style="width: 55%"></div>
        </div>
      </div>

      <p class="text-xs mt-3 text-yellow-300">Confidence: MEDIUM (62%)</p>
    </div>

    <div class="glass rounded-2xl p-4 hover:scale-105 transition fade-in glow-red">
      <h3 class="text-sm text-gray-400">48H Forecast</h3>
      <p class="text-xl font-semibold mt-2">$41,950</p>

      <div class="mt-3">
        <div class="text-xs mb-1">Bull vs Bear</div>
        <div class="w-full bg-white/10 rounded-full h-2">
          <div class="bg-red-400 h-2 rounded-full" style="width: 38%"></div>
        </div>
      </div>

      <p class="text-xs mt-3 text-red-300">Confidence: LOW (41%)</p>
    </div>

  </section>

  <!-- RIGHT PANEL -->
  <section class="lg:col-span-3 glass rounded-2xl p-4 fade-in">
    <h2 class="text-sm text-gray-400 mb-3">Risk & Intelligence</h2>

    <div class="space-y-4 text-sm">

      <div>
        Confidence Score:
        <div class="text-green-400 font-bold text-lg">78%</div>
      </div>

      <div>
        Market Stress Index:
        <div class="text-yellow-400 font-bold text-lg">Moderate</div>
      </div>

      <div>
        AI Signal Strength:
        <div class="text-green-300 font-bold text-lg">Strong Buy Bias</div>
      </div>

      <button onclick="refreshData()"
        class="mt-4 w-full py-2 rounded-xl bg-white/10 hover:bg-white/20 transition">
        Refresh Forecast
      </button>
    </div>
  </section>

</main>

<!-- CHART SECTION -->
<section class="px-6 pb-10">
  <div class="glass rounded-2xl p-6 fade-in">
    <h2 class="text-sm text-gray-400 mb-4">Market Forecast Chart (Demo)</h2>
    <canvas id="chart"></canvas>
  </div>
</section>

<script>
  // Simple demo chart
  const ctx = document.getElementById('chart');

  new Chart(ctx, {
    type: 'line',
    data: {
      labels: ['Now', '12H', '24H', '48H'],
      datasets: [{
        label: 'Predicted Price',
        data: [42000, 42800, 43120, 41950],
        borderColor: '#22c55e',
        tension: 0.4,
        fill: true,
        backgroundColor: 'rgba(34,197,94,0.1)'
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false }
      },
      scales: {
        x: { ticks: { color: '#94a3b8' } },
        y: { ticks: { color: '#94a3b8' } }
      }
    }
  });

  // Simulated refresh function (connect to Flask /forecast later)
  function refreshData() {
    alert("Fetching latest AI forecast from backend...");
    // fetch('/forecast').then(...)
  }
</script>

</body>
</html>
"""

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
        # Call the ML forecasting engine (with headless=True to avoid matplotlib GUIs)
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
