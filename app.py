"""
MarketFlux Engine – Real-Time Price Sync
=========================================
Flask web app with LIVE price synchronization.
Uses Forecasting_Engine_RealTime.py for predictions.

NEW:
  - Live price fetched BEFORE each forecast
  - Timeframes: 2H, 4H, 8H, 12H only
  - Price drift detection
  - Returns live_price in every response

Run:
    pip install flask pandas ccxt  (ccxt optional but recommended)
    python app.py
    
Open: http://localhost:5000
"""

import os, sys, io, json, threading, time, logging, traceback
from pathlib import Path
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")

from flask import Flask, jsonify, render_template_string, request

try:
    import Forecasting_Engine as FE_RT
    from Forecasting_Engine import (
        run_forecast_realtime,
        get_live_price_with_retry,
        SUPPORTED_PAIRS,
        HORIZONS
    )
except ImportError as e:
    sys.exit(
        f"[FATAL] Cannot import Forecasting_Engine: {e}\n"
        "Ensure Forecasting_Engine.py is in the same directory."
    )

import pandas as pd

log = logging.getLogger("marketflux_rt")

# ── Auto-detect cloud deployment ──────────────────────────────────────────────
IS_CLOUD = bool(os.environ.get("RENDER") or os.environ.get("DYNO") or
                os.environ.get("RAILWAY_ENVIRONMENT"))
DEFAULT_EXCHANGE = "kraken" if IS_CLOUD else "binance"
log.info(f"Deployment: {'CLOUD' if IS_CLOUD else 'LOCAL'} → default exchange: {DEFAULT_EXCHANGE}")

# ══════════════════════════════════════════════════════════════════════════════
# SHARED STATE
# ══════════════════════════════════════════════════════════════════════════════

_state = {
    "status":        "idle",      # idle | running | ready | error
    "symbol":        "ETHUSDT",
    "exchange":      DEFAULT_EXCHANGE,
    "live_price":    None,
    "price_source":  None,
    "forecasts":     [],
    "meta":          {},
    "error":         None,
    "error_detail":  None,
    "history":       [],
}
_lock = threading.Lock()


# ══════════════════════════════════════════════════════════════════════════════
# BACKGROUND FORECAST RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def _run_forecast_thread(symbol: str, exchange: str):
    """
    Background thread: Run real-time forecast.
    Fetches LIVE price, trains models, generates predictions.
    """
    with _lock:
        _state["status"]   = "running"
        _state["error"]    = None
        _state["symbol"]   = symbol
        _state["exchange"] = exchange

    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    result = None

    try:
        import matplotlib.pyplot as _plt
        _plt.show = lambda *a, **kw: None

        result = run_forecast_realtime(symbol=symbol, exchange=exchange)

    except Exception as exc:
        captured = sys.stdout.getvalue()
        if sys.stdout != old_stdout:
            sys.stdout = old_stdout
        tb = traceback.format_exc()
        log.error(f"Forecast failed: {exc}\nTraceback:\n{tb}\nEngine:\n{captured}")
        with _lock:
            _state["status"]       = "error"
            _state["error"]        = str(exc)
            _state["error_detail"] = tb
        return
    finally:
        if sys.stdout != old_stdout:
            sys.stdout = old_stdout

    if not result or result.get("status") != "success":
        with _lock:
            _state["status"] = "error"
            _state["error"]  = "Engine returned no result"
        return

    # Extract and store results
    with _lock:
        _state["status"]       = "ready"
        _state["live_price"]   = result.get("live_price")
        _state["price_source"] = result.get("price_source")
        _state["forecasts"]    = result.get("forecasts", [])
        _state["meta"]         = result.get("meta", {})
        _state["error"]        = None
        _state["error_detail"] = None


# ══════════════════════════════════════════════════════════════════════════════
# FLASK APP
# ══════════════════════════════════════════════════════════════════════════════

app = Flask(__name__)

# Supported tokens
TOKENS = {
    "ETHUSDT":   "ETH / USDT",
    "BTCUSDT":   "BTC / USDT",
    "SOLUSDT":   "SOL / USDT",
    "BNBUSDT":   "BNB / USDT",
    "ADAUSDT":   "ADA / USDT",
    "XRPUSDT":   "XRP / USDT",
    "DOGEUSDT":  "DOGE / USDT",
    "LINKUSDT":  "LINK / USDT",
    "MATICUSDT": "MATIC / USDT",
    "AVAXUSDT":  "AVAX / USDT",
    "DOTUSDT":   "DOT / USDT",
    "UNIUSDT":   "UNI / USDT",
}

EXCHANGES = ["binance", "kraken", "bybit", "coinbase"]

# ══════════════════════════════════════════════════════════════════════════════
# HTML UI – UPDATED FOR NEW TIMEFRAMES
# ══════════════════════════════════════════════════════════════════════════════

UI = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>MarketFlux – Real-Time Crypto Forecasting</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Inter', sans-serif;
    background: linear-gradient(135deg, #060d1a 0%, #0f1729 100%);
    color: #e2e8f0;
    min-height: 100vh;
  }
  .glass {
    background: rgba(255,255,255,0.04);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(255,255,255,0.08);
  }
  .card { border-radius: 12px; }
  .btn-run {
    background: linear-gradient(135deg, #0ea5e9, #6366f1);
    border: none; color: white; font-weight: 700;
    padding: 10px 24px; border-radius: 10px; cursor: pointer;
    transition: opacity .2s;
  }
  .btn-run:hover { opacity: 0.88; }
  .btn-run:disabled { opacity: 0.4; cursor: not-allowed; }
  
  .badge-live {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(34,197,94,0.15); border: 1px solid #22c55e;
    color: #86efac; padding: 6px 12px; border-radius: 6px;
    font-size: 11px; font-weight: 600;
  }
  .dot { width: 8px; height: 8px; border-radius: 50%; background: #22c55e; animation: pulse 2s infinite; }
  @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
  
  .toast {
    position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
    background: rgba(0,0,0,0.8); color: white; padding: 12px 20px;
    border-radius: 8px; z-index: 9999; font-size: 13px;
  }
  .skeleton { background: linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.09) 50%, rgba(255,255,255,0.04) 75%); background-size: 400px 100%; animation: shimmer 1.5s infinite; border-radius: 6px; }
  @keyframes shimmer { 0% { background-position: -400px 0; } 100% { background-position: 400px 0; } }
</style>
</head>
<body>

<!-- HEADER -->
<header class="flex items-center justify-between px-6 py-4 border-b border-white/10 glass sticky top-0 z-50">
  <div>
    <h1 class="text-2xl font-bold" style="background:linear-gradient(135deg,#00e5ff,#818cf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent">⚡ MarketFlux</h1>
    <p class="text-xs text-slate-500">Real-Time Crypto Price Sync Engine</p>
  </div>
  <div class="flex items-center gap-4 flex-wrap">
    <select id="sel-symbol" class="px-3 py-2 bg-white/5 border border-white/10 text-sm rounded">
      {{ token_options | safe }}
    </select>
    <select id="sel-exchange" class="px-3 py-2 bg-white/5 border border-white/10 text-sm rounded">
      {{ exchange_options | safe }}
    </select>
    <button id="btn-run" class="btn-run" onclick="runForecast()">▶ Run Forecast</button>
    <div class="badge-live">
      <div class="dot"></div>
      <span>LIVE MODE</span>
    </div>
  </div>
</header>

<!-- MAIN CONTENT -->
<main class="p-6 max-w-[1600px] mx-auto space-y-5">

  <!-- Live Price + Status Row -->
  <div class="grid grid-cols-1 sm:grid-cols-4 gap-4">
    <div class="glass card p-5">
      <p class="text-xs text-slate-500 uppercase mb-2">Live Price</p>
      <p id="live-price" class="text-3xl font-bold">—</p>
      <p id="price-source" class="text-xs text-slate-500 mt-1">—</p>
    </div>
    <div class="glass card p-5">
      <p class="text-xs text-slate-500 uppercase mb-2">Market Regime</p>
      <p id="meta-regime" class="text-2xl font-bold">—</p>
    </div>
    <div class="glass card p-5">
      <p class="text-xs text-slate-500 uppercase mb-2">Volatility (14d)</p>
      <p id="meta-rvol" class="text-2xl font-bold">—%</p>
    </div>
    <div class="glass card p-5">
      <p class="text-xs text-slate-500 uppercase mb-2">Status</p>
      <p id="status-text" class="text-lg font-semibold text-slate-400">IDLE</p>
    </div>
  </div>

  <!-- Forecast Cards – NEW: 2H, 4H, 8H, 12H ONLY -->
  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
    <div id="card-2" class="glass card p-5 border border-white/10">
      <p class="text-sm font-semibold text-slate-300 mb-3">2H Forecast</p>
      <div id="card-2-body" class="space-y-2">
        <div class="skeleton h-4 w-20"></div>
        <div class="skeleton h-3 w-full"></div>
        <div class="skeleton h-3 w-3/4"></div>
      </div>
    </div>
    <div id="card-4" class="glass card p-5 border border-white/10">
      <p class="text-sm font-semibold text-slate-300 mb-3">4H Forecast</p>
      <div id="card-4-body" class="space-y-2">
        <div class="skeleton h-4 w-20"></div>
        <div class="skeleton h-3 w-full"></div>
        <div class="skeleton h-3 w-3/4"></div>
      </div>
    </div>
    <div id="card-8" class="glass card p-5 border border-white/10">
      <p class="text-sm font-semibold text-slate-300 mb-3">8H Forecast</p>
      <div id="card-8-body" class="space-y-2">
        <div class="skeleton h-4 w-20"></div>
        <div class="skeleton h-3 w-full"></div>
        <div class="skeleton h-3 w-3/4"></div>
      </div>
    </div>
    <div id="card-12" class="glass card p-5 border border-white/10">
      <p class="text-sm font-semibold text-slate-300 mb-3">12H Forecast</p>
      <div id="card-12-body" class="space-y-2">
        <div class="skeleton h-4 w-20"></div>
        <div class="skeleton h-3 w-full"></div>
        <div class="skeleton h-3 w-3/4"></div>
      </div>
    </div>
  </div>

  <!-- Price Chart -->
  <div class="glass card p-5">
    <p class="text-sm font-semibold text-slate-300 mb-3">Forecast Price Trajectory</p>
    <canvas id="chart-forecast" height="200"></canvas>
  </div>

  <!-- Bull/Bear Probability -->
  <div class="glass card p-5">
    <p class="text-sm font-semibold text-slate-300 mb-3">Directional Probability (2H/4H/8H/12H)</p>
    <canvas id="chart-prob" height="160"></canvas>
  </div>

</main>

<!-- LOADING OVERLAY -->
<div id="overlay" class="hidden fixed inset-0 z-50 flex items-center justify-center" style="background:rgba(6,13,26,0.85)">
  <div class="text-center">
    <div style="width:48px;height:48px;border:4px solid rgba(14,165,233,0.3);border-top-color:#0ea5e9;border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 16px"></div>
    <p class="text-cyan-300 font-semibold">Running ML Forecast…</p>
    <p class="text-slate-500 text-sm mt-2">Fetching live price · Loading historical data · Training ensemble</p>
  </div>
</div>

<script>
let chartForecast = null, chartProb = null;

function showToast(msg, type) {
  const el = document.createElement('div');
  el.className = 'toast';
  el.style.background = type === 'error' ? 'rgba(239,68,68,0.9)' : 'rgba(34,197,94,0.9)';
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 5000);
}

function setStatus(status) {
  const map = { idle: 'IDLE', running: 'RUNNING', ready: 'LIVE', error: 'ERROR' };
  document.getElementById('status-text').textContent = map[status] || status;
  document.getElementById('status-text').style.color = status === 'ready' ? '#22c55e' : status === 'error' ? '#ef4444' : '#64748b';
}

async function runForecast() {
  const symbol = document.getElementById('sel-symbol').value;
  const exchange = document.getElementById('sel-exchange').value;
  
  document.getElementById('btn-run').disabled = true;
  document.getElementById('overlay').classList.remove('hidden');
  setStatus('running');

  await fetch(`/forecast/run?symbol=${symbol}&exchange=${exchange}`);

  let maxPolls = 120, poll = 0;
  const pollInterval = setInterval(async () => {
    poll++;
    if (poll > maxPolls) { clearInterval(pollInterval); showToast('Forecast timeout', 'error'); return; }
    
    try {
      const res = await fetch('/forecast/status');
      const data = await res.json();
      
      if (data.status === 'ready') {
        clearInterval(pollInterval);
        document.getElementById('overlay').classList.add('hidden');
        document.getElementById('btn-run').disabled = false;
        setStatus('ready');
        renderAll(data);
      } else if (data.status === 'error') {
        clearInterval(pollInterval);
        document.getElementById('overlay').classList.add('hidden');
        document.getElementById('btn-run').disabled = false;
        setStatus('error');
        const err = data.error || 'Unknown error';
        if (err.includes('geo') || err.includes('451') || err.includes('403')) {
          showToast('⚠️ Geo-blocked, retrying with Kraken...', 'error');
          document.getElementById('sel-exchange').value = 'kraken';
          setTimeout(() => runForecast(), 1500);
        } else {
          showToast('❌ ' + err, 'error');
        }
      }
    } catch (e) {}
  }, 2000);
}

function renderAll(data) {
  const { live_price, price_source, forecasts, meta } = data;
  document.getElementById('live-price').textContent = live_price ? '$' + live_price.toFixed(2) : '—';
  document.getElementById('price-source').textContent = 'via ' + (price_source || '?');
  document.getElementById('meta-regime').textContent = meta.regime || '—';
  document.getElementById('meta-rvol').textContent = meta.rvol != null ? meta.rvol.toFixed(2) : '—';

  if (forecasts && forecasts.length) {
    forecasts.forEach(fc => {
      const h = fc.horizon;
      const body = document.getElementById(`card-${h}-body`);
      if (!body) return;
      
      const dir = fc.bull_prob_pct >= 50 ? '▲' : '▼';
      const dirColor = fc.bull_prob_pct >= 50 ? '#22c55e' : '#ef4444';
      const cc = fc.confidence === 'HIGH' ? '#22c55e' : fc.confidence === 'MEDIUM' ? '#f59e0b' : '#ef4444';
      
      body.innerHTML = `
        <div style="font-size:24px;font-weight:700;color:white;margin-bottom:6px">$${fc.pred_price.toFixed(2)}</div>
        <div style="font-size:14px;font-weight:600;color:${dirColor}>${dir} ${fc.pred_ret_pct.toFixed(2)}%</div>
        <div style="font-size:11px;color:#64748b;margin-top:8px">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px">
            <span>Bull</span><span>${fc.bull_prob_pct.toFixed(0)}%</span>
          </div>
          <div style="height:6px;background:rgba(255,255,255,0.08);border-radius:4px;overflow:hidden">
            <div style="height:100%;width:${fc.bull_prob_pct}%;background:linear-gradient(90deg,#ef4444,${dirColor})"></div>
          </div>
        </div>
        <div style="font-size:11px;color:${cc};font-weight:600;margin-top:6px">${fc.confidence} (${(fc.conf_score*100).toFixed(0)}%)</div>
      `;
    });

    renderForecastChart(forecasts, live_price);
    renderProbChart(forecasts);
  }
}

function renderForecastChart(forecasts, livePrice) {
  const labels = ['Now', '2H', '4H', '8H', '12H'];
  const prices = [livePrice, ...forecasts.map(f => f.pred_price)];
  const trend = prices[prices.length-1] >= prices[0];
  
  if (chartForecast) chartForecast.destroy();
  const ctx = document.getElementById('chart-forecast').getContext('2d');
  chartForecast = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Predicted Price',
        data: prices,
        borderColor: trend ? '#22c55e' : '#ef4444',
        backgroundColor: trend ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)',
        tension: 0.4, fill: true, pointRadius: 5,
        pointBackgroundColor: trend ? '#22c55e' : '#ef4444',
        borderWidth: 2,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: true,
      plugins: { legend: { labels: { color: '#64748b', font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: '#64748b' }, grid: { color: 'rgba(255,255,255,0.04)' } },
        y: { ticks: { color: '#64748b', callback: v => '$' + v.toFixed(0) }, grid: { color: 'rgba(255,255,255,0.04)' } }
      }
    }
  });
}

function renderProbChart(forecasts) {
  const labels = forecasts.map(f => f.horizon + 'H');
  const bulls = forecasts.map(f => f.bull_prob_pct);
  const bears = forecasts.map(f => f.bear_prob_pct);
  
  if (chartProb) chartProb.destroy();
  const ctx = document.getElementById('chart-prob').getContext('2d');
  chartProb = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        { label: 'Bull %', data: bulls, backgroundColor: 'rgba(34,197,94,0.7)', borderRadius: 5 },
        { label: 'Bear %', data: bears, backgroundColor: 'rgba(239,68,68,0.7)', borderRadius: 5 }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: true,
      indexAxis: undefined,
      scales: {
        x: { ticks: { color: '#94a3b8' }, grid: { display: false } },
        y: { min: 0, max: 100, ticks: { color: '#64748b', callback: v => v + '%' }, grid: { color: 'rgba(255,255,255,0.04)' } }
      }
    }
  });
}
</script>
</body>
</html>
"""

# ══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def home():
    token_opts = "\n".join(
        f'<option value="{k}"{"selected" if k=="ETHUSDT" else ""}>{v}</option>'
        for k, v in TOKENS.items()
    )
    exch_opts = "\n".join(
        f'<option value="{e}"{"selected" if e==DEFAULT_EXCHANGE else ""}>{e.capitalize()}</option>'
        for e in EXCHANGES
    )
    return render_template_string(UI, token_options=token_opts, exchange_options=exch_opts)


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "engine": "Forecasting_Engine",
        "horizons": HORIZONS,
        "supported_pairs": list(SUPPORTED_PAIRS.keys())
    })


@app.route("/forecast/run")
def forecast_run():
    symbol = request.args.get("symbol", "ETHUSDT")
    exchange = request.args.get("exchange", DEFAULT_EXCHANGE)

    # Override cloud deployments away from geo-blocked exchanges
    if IS_CLOUD and exchange in ("binance", "bybit"):
        exchange = "kraken"

    with _lock:
        if _state["status"] == "running":
            return jsonify({"message": "Already running"}), 409

    t = threading.Thread(target=_run_forecast_thread, args=(symbol, exchange), daemon=True)
    t.start()
    return jsonify({"message": "started", "symbol": symbol, "exchange": exchange}), 202


@app.route("/forecast/status")
def forecast_status():
    with _lock:
        return jsonify({
            "status":       _state["status"],
            "symbol":       _state["symbol"],
            "exchange":     _state["exchange"],
            "live_price":   _state["live_price"],
            "price_source": _state["price_source"],
            "forecasts":    _state["forecasts"],
            "meta":         _state["meta"],
            "error":        _state["error"],
            "error_detail": _state.get("error_detail"),
        })


@app.route("/price/<symbol>")
def get_price(symbol: str):
    """
    Quick endpoint to check live price for any symbol.
    Useful for debugging/testing price fetching independently.
    """
    exchange = request.args.get("exchange", "binance")
    try:
        price, source = get_live_price_with_retry(symbol, exchange)
        return jsonify({"symbol": symbol, "price": price, "source": source, "timestamp": datetime.now(timezone.utc).isoformat()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"""
  ╔────────────────────────────────────────────╗
  │  MarketFlux Real-Time Forecasting Engine   │
  │  http://localhost:{port}                      │
  │                                            │
  │  ✓ Live price sync enabled                 │
  │  ✓ Timeframes: 2H, 4H, 8H, 12H              │
  │  ✓ Multi-exchange fallback ready           │
  ╚────────────────────────────────────────────╝
""")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
