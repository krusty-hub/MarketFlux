"""
MarketFlux Engine  –  Flask Web App
=====================================
Connects directly to Forecasting_Engine.py.

Run:
    pip install flask pandas
    python app.py

Then open:  http://localhost:5000
"""

import os, sys, io, json, threading, time, logging
from pathlib import Path
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")   # must be set BEFORE importing pyplot – no GUI needed

from flask import Flask, jsonify, render_template_string, request

# ── Import the ML engine ──────────────────────────────────────────────────────
try:
    import Forecasting_Engine as FE
    from Forecasting_Engine import run_forecast, HORIZONS, PredictionDatabase, DB_PATH
except ImportError as e:
    sys.exit(
        f"[FATAL] Cannot import Forecasting_Engine: {e}\n"
        "Make sure Forecasting_Engine.py is in the same directory as app.py."
    )

import pandas as pd

log = logging.getLogger("marketflux")

# ══════════════════════════════════════════════════════════════════════════════
# STATE  –  shared between the forecast thread and Flask routes
# ══════════════════════════════════════════════════════════════════════════════

_state = {
    "status":       "idle",          # idle | running | ready | error
    "symbol":       "ETHUSDT",
    "exchange":     "binance",
    "forecasts":    [],              # list of forecast dicts (12h, 24h, 48h)
    "meta": {
        "last_close":   None,
        "regime":       "—",
        "rvol":         None,
        "win_rate":     None,
        "risk_flags":   [],
        "timestamp":    None,
        "perf":         [],          # [{horizon, mae, rmse, dir_acc}]
    },
    "error":        None,
    "history":      [],              # last N prediction records from DB
}
_lock = threading.Lock()

# ══════════════════════════════════════════════════════════════════════════════
# FORECAST RUNNER  – runs in a background thread so Flask stays responsive
# ══════════════════════════════════════════════════════════════════════════════

def _run_forecast_thread(symbol: str, exchange: str):
    """
    Calls run_forecast() from Forecasting_Engine, captures the returned
    forecasts list, and stores everything in _state.
    """
    with _lock:
        _state["status"]  = "running"
        _state["error"]   = None
        _state["symbol"]  = symbol
        _state["exchange"]= exchange

    # Silence matplotlib pop-up and suppress stdout noise from the engine
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    result = None

    try:
        # Patch plt.show() so it doesn't block in server mode
        import matplotlib.pyplot as _plt
        _plt.show = lambda *a, **kw: None

        result = run_forecast(symbol=symbol, exchange=exchange)

    except Exception as exc:
        captured = sys.stdout.getvalue()
        sys.stdout = old_stdout
        log.error(f"Forecast failed: {exc}\nEngine output:\n{captured}")
        with _lock:
            _state["status"] = "error"
            _state["error"]  = str(exc)
        return
    finally:
        sys.stdout = old_stdout

    # ── Extract results ───────────────────────────────────────────────────────
    if not result:
        # Fallback: read the CSV that run_forecast() always saves
        csv = f"{symbol.replace('/','_')}_forecast.csv"
        if Path(csv).exists():
            result = pd.read_csv(csv).to_dict(orient="records")

    if not result:
        with _lock:
            _state["status"] = "error"
            _state["error"]  = "Engine returned no data."
        return

    # ── Derive metadata from first forecast dict ──────────────────────────────
    first = result[0] if result else {}
    last_close   = first.get("last_close")
    regime_str   = first.get("regime", "—")
    rvol         = first.get("rvol")
    risk_flags   = first.get("risk_flags", [])

    # Win rate from the persistent DB
    try:
        db       = PredictionDatabase(DB_PATH)
        win_rate = db.win_rate(symbol)
        history  = db.data.get("predictions", [])[-50:]
    except Exception:
        win_rate = 0.5
        history  = []

    # ── Model performance from CSV (engine prints but doesn't return it) ──────
    # We re-derive directional accuracy from the result data we have.
    perf = []
    for fc in result:
        h = fc.get("horizon", "?")
        # These are not available from the returned list alone –
        # engine logs them to console.  We show conf_score as proxy.
        perf.append({
            "horizon":  h,
            "conf":     round(fc.get("conf_score", 0) * 100, 1),
            "vol":      fc.get("volatility", "—"),
            "no_trade": fc.get("no_trade", False),
        })

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    with _lock:
        _state["status"]        = "ready"
        _state["forecasts"]     = result
        _state["meta"]["last_close"]  = last_close
        _state["meta"]["regime"]      = regime_str
        _state["meta"]["rvol"]        = round(rvol * 100, 3) if rvol else None
        _state["meta"]["win_rate"]    = round(win_rate * 100, 1)
        _state["meta"]["risk_flags"]  = risk_flags
        _state["meta"]["timestamp"]   = ts
        _state["meta"]["perf"]        = perf
        _state["history"]             = history


# ══════════════════════════════════════════════════════════════════════════════
# FLASK APP
# ══════════════════════════════════════════════════════════════════════════════

app = Flask(__name__)

# ── Supported tokens (symbol → display label) ─────────────────────────────────
TOKENS = {
    "ETHUSDT":  "ETH / USDT",
    "BTCUSDT":  "BTC / USDT",
    "SOLUSDT":  "SOL / USDT",
    "BNBUSDT":  "BNB / USDT",
    "ADAUSDT":  "ADA / USDT",
    "XRPUSDT":  "XRP / USDT",
    "DOGEUSDT": "DOGE / USDT",
    "LINKUSDT": "LINK / USDT",
    "AVAXUSDT": "AVAX / USDT",
    "MATICUSDT":"MATIC / USDT",
}

EXCHANGES = ["binance", "bybit", "kraken", "coingecko"]

# ══════════════════════════════════════════════════════════════════════════════
# HTML / CSS / JS  – single-file UI
# ══════════════════════════════════════════════════════════════════════════════

UI = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>MarketFlux Engine</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet"/>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'Inter', sans-serif;
    background: #060d1a;
    color: #e2e8f0;
    min-height: 100vh;
  }

  /* ── Animated starfield background ── */
  body::before {
    content: '';
    position: fixed; inset: 0; z-index: -1;
    background:
      radial-gradient(ellipse 80% 60% at 50% -10%, rgba(0,229,255,0.08) 0%, transparent 70%),
      radial-gradient(ellipse 60% 40% at 80% 100%, rgba(99,102,241,0.07) 0%, transparent 70%),
      #060d1a;
  }

  /* ── Glass panels ── */
  .glass {
    background: rgba(255,255,255,0.035);
    backdrop-filter: blur(18px);
    border: 1px solid rgba(255,255,255,0.07);
  }
  .glass-strong {
    background: rgba(255,255,255,0.06);
    backdrop-filter: blur(24px);
    border: 1px solid rgba(0,229,255,0.12);
  }

  /* ── Glow variants ── */
  .glow-cyan  { box-shadow: 0 0 28px rgba(0,229,255,0.18),  inset 0 1px 0 rgba(0,229,255,0.08); }
  .glow-green { box-shadow: 0 0 28px rgba(34,197,94,0.22),  inset 0 1px 0 rgba(34,197,94,0.08); }
  .glow-red   { box-shadow: 0 0 28px rgba(239,68,68,0.22),  inset 0 1px 0 rgba(239,68,68,0.08); }
  .glow-amber { box-shadow: 0 0 28px rgba(245,158,11,0.22), inset 0 1px 0 rgba(245,158,11,0.08); }

  /* ── Animated gradient border on cards ── */
  .card-border {
    position: relative;
    border-radius: 1rem;
    overflow: hidden;
  }
  .card-border::before {
    content: '';
    position: absolute; inset: -1px;
    border-radius: inherit;
    padding: 1px;
    background: linear-gradient(135deg, rgba(0,229,255,0.3), rgba(99,102,241,0.2), rgba(0,229,255,0.1));
    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    -webkit-mask-composite: destination-out;
    mask-composite: exclude;
    pointer-events: none;
  }

  /* ── Animations ── */
  @keyframes fadeUp   { from{opacity:0;transform:translateY(16px)} to{opacity:1;transform:translateY(0)} }
  @keyframes pulse2   { 0%,100%{opacity:1} 50%{opacity:0.4} }
  @keyframes spin     { to{transform:rotate(360deg)} }
  @keyframes shimmer  {
    0%   { background-position: -400px 0; }
    100% { background-position:  400px 0; }
  }

  .fade-up  { animation: fadeUp 0.5s ease both; }
  .spin     { animation: spin 1s linear infinite; }

  .skeleton {
    background: linear-gradient(90deg, rgba(255,255,255,0.04) 25%,
                rgba(255,255,255,0.09) 50%, rgba(255,255,255,0.04) 75%);
    background-size: 400px 100%;
    animation: shimmer 1.4s infinite;
    border-radius: 6px;
  }

  /* ── Progress bar ── */
  .bar-track { background: rgba(255,255,255,0.08); border-radius: 999px; height: 6px; }
  .bar-fill  { height: 6px; border-radius: 999px; transition: width 0.8s cubic-bezier(.4,0,.2,1); }

  /* ── Scrollbar ── */
  ::-webkit-scrollbar { width: 5px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: rgba(0,229,255,0.2); border-radius: 999px; }

  /* ── Status badge ── */
  .badge {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 3px 10px; border-radius: 999px; font-size: 11px; font-weight: 600;
  }
  .dot { width:7px; height:7px; border-radius:50%; }

  /* ── Select ── */
  select {
    appearance: none;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.1);
    color: #e2e8f0;
    border-radius: 8px;
    padding: 6px 32px 6px 10px;
    font-size: 13px;
    cursor: pointer;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='%2394a3b8' viewBox='0 0 16 16'%3E%3Cpath d='M2 5l6 6 6-6'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 8px center;
    background-size: 14px;
  }
  select option { background: #0f1929; }

  /* ── Run button ── */
  #btn-run {
    background: linear-gradient(135deg, #0ea5e9, #6366f1);
    border: none; border-radius: 10px;
    color: white; font-weight: 700; font-size: 14px;
    padding: 9px 22px; cursor: pointer;
    transition: opacity .2s, transform .1s;
    white-space: nowrap;
  }
  #btn-run:hover  { opacity: .88; }
  #btn-run:active { transform: scale(.97); }
  #btn-run:disabled { opacity: .4; cursor: not-allowed; }

  /* ── Risk flag chip ── */
  .flag-chip {
    display: inline-flex; align-items: center; gap: 5px;
    background: rgba(239,68,68,0.12);
    border: 1px solid rgba(239,68,68,0.3);
    color: #fca5a5; border-radius: 6px;
    padding: 3px 9px; font-size: 11px; font-weight: 500;
  }

  /* ── Table ── */
  .hist-table { width: 100%; border-collapse: collapse; font-size: 12px; }
  .hist-table th { color: #64748b; font-weight: 500; padding: 6px 8px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.05); }
  .hist-table td { padding: 6px 8px; border-bottom: 1px solid rgba(255,255,255,0.04); }

  /* ── No-trade banner ── */
  .no-trade-banner {
    background: rgba(239,68,68,0.1);
    border: 1px solid rgba(239,68,68,0.3);
    border-radius: 8px; padding: 6px 10px;
    color: #fca5a5; font-size: 12px; font-weight: 600;
    display: flex; align-items: center; gap: 6px;
  }
</style>
</head>

<body>

<!-- ══════════════════════════════════ NAVBAR ═══════════════════════════════ -->
<header class="flex items-center justify-between px-6 py-3 border-b border-white/[0.06] glass sticky top-0 z-50">
  <div class="flex items-center gap-3">
    <span class="text-xl font-bold tracking-tight" style="background:linear-gradient(135deg,#00e5ff,#818cf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent">
      ⚡ MarketFlux
    </span>
    <span class="text-xs text-slate-500 font-medium">AI Forecasting Engine</span>
  </div>

  <!-- Controls -->
  <div class="flex items-center gap-3 flex-wrap">
    <select id="sel-symbol" title="Token">
      {{ token_options | safe }}
    </select>
    <select id="sel-exchange" title="Exchange">
      {{ exchange_options | safe }}
    </select>
    <button id="btn-run" onclick="runForecast()">▶ Run Forecast</button>
    <div id="status-badge" class="badge" style="background:rgba(100,116,139,0.15);border:1px solid rgba(100,116,139,0.25)">
      <div class="dot" style="background:#64748b"></div>
      <span id="status-text" style="color:#94a3b8">IDLE</span>
    </div>
  </div>
</header>

<!-- ══════════════════════════════ MAIN LAYOUT ══════════════════════════════ -->
<main class="p-5 grid grid-cols-1 lg:grid-cols-12 gap-5 max-w-[1600px] mx-auto">

  <!-- ── LEFT SIDEBAR ── -->
  <aside class="lg:col-span-3 space-y-4">

    <!-- Market Summary -->
    <div class="glass card-border rounded-2xl p-5 fade-up">
      <p class="text-[11px] text-slate-500 uppercase tracking-widest mb-4">Market Summary</p>

      <div class="space-y-4 text-sm">
        <div class="flex justify-between items-center">
          <span class="text-slate-400">Last Price</span>
          <span id="meta-price" class="font-semibold text-white">—</span>
        </div>
        <div class="flex justify-between items-center">
          <span class="text-slate-400">Market Regime</span>
          <span id="meta-regime" class="font-semibold">—</span>
        </div>
        <div class="flex justify-between items-center">
          <span class="text-slate-400">Volatility (14d)</span>
          <span id="meta-rvol" class="font-semibold">—</span>
        </div>
        <div class="flex justify-between items-center">
          <span class="text-slate-400">Win Rate</span>
          <span id="meta-winrate" class="font-semibold">—</span>
        </div>
        <div class="flex justify-between items-center">
          <span class="text-slate-400">Last Updated</span>
          <span id="meta-ts" class="text-[11px] text-slate-500">—</span>
        </div>
      </div>
    </div>

    <!-- Risk Flags -->
    <div class="glass card-border rounded-2xl p-5 fade-up" style="animation-delay:.05s">
      <p class="text-[11px] text-slate-500 uppercase tracking-widest mb-3">⚡ Active Risk Flags</p>
      <div id="risk-flags" class="space-y-2 text-sm text-slate-500">No flags detected.</div>
    </div>

    <!-- Model Confidence per horizon -->
    <div class="glass card-border rounded-2xl p-5 fade-up" style="animation-delay:.1s">
      <p class="text-[11px] text-slate-500 uppercase tracking-widest mb-4">Model Confidence</p>
      <div id="perf-table" class="space-y-3 text-sm text-slate-500">Run a forecast to see results.</div>
    </div>

  </aside>

  <!-- ── CENTER: FORECAST CARDS + CHART ── -->
  <section class="lg:col-span-6 space-y-5">

    <!-- 3 forecast cards -->
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <div id="card-12"  class="card-border glass rounded-2xl p-5 fade-up" style="animation-delay:.08s">
        <p class="text-[11px] text-slate-500 uppercase tracking-widest">12H Forecast</p>
        <div id="card-12-body"  class="mt-3"><div class="skeleton h-5 w-24 mb-3"></div><div class="skeleton h-3 w-full mb-2"></div><div class="skeleton h-3 w-3/4"></div></div>
      </div>
      <div id="card-24"  class="card-border glass rounded-2xl p-5 fade-up" style="animation-delay:.13s">
        <p class="text-[11px] text-slate-500 uppercase tracking-widest">24H Forecast</p>
        <div id="card-24-body"  class="mt-3"><div class="skeleton h-5 w-24 mb-3"></div><div class="skeleton h-3 w-full mb-2"></div><div class="skeleton h-3 w-3/4"></div></div>
      </div>
      <div id="card-48"  class="card-border glass rounded-2xl p-5 fade-up" style="animation-delay:.18s">
        <p class="text-[11px] text-slate-500 uppercase tracking-widest">48H Forecast</p>
        <div id="card-48-body"  class="mt-3"><div class="skeleton h-5 w-24 mb-3"></div><div class="skeleton h-3 w-full mb-2"></div><div class="skeleton h-3 w-3/4"></div></div>
      </div>
    </div>

    <!-- Price forecast chart -->
    <div class="glass card-border rounded-2xl p-5 fade-up" style="animation-delay:.2s">
      <p class="text-[11px] text-slate-500 uppercase tracking-widest mb-4">Predicted Price Trajectory</p>
      <canvas id="chart-forecast" height="160"></canvas>
    </div>

    <!-- Bull/Bear probability chart -->
    <div class="glass card-border rounded-2xl p-5 fade-up" style="animation-delay:.25s">
      <p class="text-[11px] text-slate-500 uppercase tracking-widest mb-4">Directional Probability by Horizon</p>
      <canvas id="chart-prob" height="120"></canvas>
    </div>

  </section>

  <!-- ── RIGHT SIDEBAR ── -->
  <aside class="lg:col-span-3 space-y-4">

    <!-- AI Signal strength -->
    <div class="glass card-border rounded-2xl p-5 fade-up" style="animation-delay:.1s">
      <p class="text-[11px] text-slate-500 uppercase tracking-widest mb-4">AI Signal Strength</p>
      <div id="signal-panel" class="space-y-4 text-sm text-slate-500">Run forecast to see signals.</div>
    </div>

    <!-- Range bands -->
    <div class="glass card-border rounded-2xl p-5 fade-up" style="animation-delay:.15s">
      <p class="text-[11px] text-slate-500 uppercase tracking-widest mb-4">Expected Price Ranges</p>
      <div id="range-panel" class="space-y-3 text-sm text-slate-500">—</div>
    </div>

    <!-- Prediction history -->
    <div class="glass card-border rounded-2xl p-5 fade-up" style="animation-delay:.2s">
      <p class="text-[11px] text-slate-500 uppercase tracking-widest mb-3">Prediction History</p>
      <div id="history-panel" style="max-height:220px;overflow-y:auto">
        <p class="text-xs text-slate-600">No history yet.</p>
      </div>
    </div>

  </aside>

</main>

<!-- ══════════════════════════════ LOADING OVERLAY ══════════════════════════ -->
<div id="overlay" class="hidden fixed inset-0 z-50 flex items-center justify-center"
     style="background:rgba(6,13,26,0.75);backdrop-filter:blur(6px)">
  <div class="text-center">
    <div class="spin inline-block w-12 h-12 border-4 border-cyan-400/30 border-t-cyan-400 rounded-full mb-4"></div>
    <p class="text-cyan-300 font-semibold text-sm">Running ML Forecast…</p>
    <p class="text-slate-500 text-xs mt-1">Fetching data · Engineering features · Training ensemble</p>
    <p id="overlay-sub" class="text-slate-600 text-xs mt-2"></p>
  </div>
</div>

<!-- ══════════════════════════════════ SCRIPT ════════════════════════════════ -->
<script>
// ── Chart instances (kept outside so we can destroy & rebuild) ─────────────
let chartForecast = null;
let chartProb     = null;

// ── Colour helpers ──────────────────────────────────────────────────────────
function confColor(label) {
  return label === 'HIGH'   ? '#22c55e'
       : label === 'MEDIUM' ? '#f59e0b'
       :                      '#ef4444';
}
function glowClass(label) {
  return label === 'HIGH'   ? 'glow-green'
       : label === 'MEDIUM' ? 'glow-amber'
       :                      'glow-red';
}
function fmtPrice(v) {
  if (v == null) return '—';
  return '$' + Number(v).toLocaleString('en-US', {minimumFractionDigits:2,maximumFractionDigits:2});
}
function fmtPct(v) {
  if (v == null) return '—';
  const s = Number(v) >= 0 ? '+' : '';
  return s + Number(v).toFixed(2) + '%';
}

// ── Status badge ─────────────────────────────────────────────────────────────
function setStatus(status) {
  const badge = document.getElementById('status-badge');
  const dot   = badge.querySelector('.dot');
  const text  = document.getElementById('status-text');

  const map = {
    idle:    ['#64748b','#94a3b8','rgba(100,116,139,0.15)','rgba(100,116,139,0.25)', 'IDLE'],
    running: ['#0ea5e9','#38bdf8','rgba(14,165,233,0.12)','rgba(14,165,233,0.3)',   'RUNNING'],
    ready:   ['#22c55e','#86efac','rgba(34,197,94,0.12)', 'rgba(34,197,94,0.3)',    'LIVE'],
    error:   ['#ef4444','#fca5a5','rgba(239,68,68,0.12)', 'rgba(239,68,68,0.3)',    'ERROR'],
  };
  const [dc, tc, bg, bc, label] = map[status] || map.idle;
  dot.style.background   = dc;
  text.style.color       = tc;
  text.textContent       = label;
  badge.style.background = bg;
  badge.style.border     = `1px solid ${bc}`;
  if (status === 'running') dot.style.animation = 'pulse2 1s ease infinite';
  else dot.style.animation = '';
}

// ── Main run handler ─────────────────────────────────────────────────────────
let pollTimer = null;

async function runForecast() {
  const symbol   = document.getElementById('sel-symbol').value;
  const exchange = document.getElementById('sel-exchange').value;

  // Disable button, show overlay
  document.getElementById('btn-run').disabled = true;
  document.getElementById('overlay').classList.remove('hidden');
  setStatus('running');

  // Kick off background forecast
  try {
    await fetch(`/forecast/run?symbol=${symbol}&exchange=${exchange}`);
  } catch(e) { /* fire-and-forget */ }

  // Poll /forecast/status every 2 s until done
  let elapsed = 0;
  const subs = ['Connecting to exchange…','Fetching OHLCV data…','Engineering 80+ features…','Training XGBoost / LightGBM / RF…','Building ensemble…','Generating forecasts…'];
  pollTimer = setInterval(async () => {
    elapsed++;
    document.getElementById('overlay-sub').textContent = subs[Math.min(elapsed-1, subs.length-1)];
    try {
      const res  = await fetch('/forecast/status');
      const data = await res.json();

      if (data.status === 'ready') {
        clearInterval(pollTimer);
        document.getElementById('overlay').classList.add('hidden');
        document.getElementById('btn-run').disabled = false;
        setStatus('ready');
        renderAll(data);
      } else if (data.status === 'error') {
        clearInterval(pollTimer);
        document.getElementById('overlay').classList.add('hidden');
        document.getElementById('btn-run').disabled = false;
        setStatus('error');
        alert('Forecast error: ' + (data.error || 'unknown'));
      }
    } catch(e) { /* network hiccup, keep polling */ }
  }, 2000);
}

// ── Render everything ────────────────────────────────────────────────────────
function renderAll(data) {
  const { forecasts, meta, history } = data;
  if (!forecasts || !forecasts.length) return;

  renderMeta(meta);
  renderCards(forecasts);
  renderForecastChart(forecasts, meta.last_close);
  renderProbChart(forecasts);
  renderSignal(forecasts);
  renderRanges(forecasts);
  renderPerf(meta.perf);
  renderRiskFlags(meta.risk_flags);
  renderHistory(history);
}

// ── Meta panel ───────────────────────────────────────────────────────────────
function renderMeta(meta) {
  document.getElementById('meta-price').textContent    = fmtPrice(meta.last_close);
  document.getElementById('meta-ts').textContent      = meta.timestamp || '—';
  document.getElementById('meta-winrate').textContent = meta.win_rate != null ? meta.win_rate + '%' : '—';

  const re = document.getElementById('meta-regime');
  re.textContent  = meta.regime || '—';
  re.style.color  = meta.regime === 'TRENDING' ? '#22c55e' : '#f59e0b';

  const rv = document.getElementById('meta-rvol');
  rv.textContent = meta.rvol != null ? meta.rvol + '%' : '—';
  rv.style.color = meta.rvol > 2.5 ? '#ef4444' : meta.rvol > 1.2 ? '#f59e0b' : '#22c55e';
}

// ── Forecast cards ───────────────────────────────────────────────────────────
function renderCards(forecasts) {
  forecasts.forEach(fc => {
    const body = document.getElementById(`card-${fc.horizon}-body`);
    if (!body) return;
    const card = document.getElementById(`card-${fc.horizon}`);

    // Update glow
    card.classList.remove('glow-green','glow-amber','glow-red','glow-cyan');
    card.classList.add(glowClass(fc.confidence));

    const dir      = fc.bull_prob_pct >= 50 ? '▲' : '▼';
    const dirColor = fc.bull_prob_pct >= 50 ? '#22c55e' : '#ef4444';
    const bullW    = Math.round(fc.bull_prob_pct);
    const cc       = confColor(fc.confidence);

    const noTradeBanner = fc.no_trade
      ? `<div class="no-trade-banner mt-2">⛔ NO TRADE – ${fc.confidence} CONFIDENCE</div>`
      : '';

    body.innerHTML = `
      <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:4px">
        <span style="font-size:20px;font-weight:700;color:white">${fmtPrice(fc.pred_price)}</span>
        <span style="font-size:12px;font-weight:600;color:${dirColor}">${dir} ${fmtPct(fc.pred_ret_pct)}</span>
      </div>

      <div style="margin:10px 0 4px;font-size:11px;color:#64748b;display:flex;justify-content:space-between">
        <span>Bear ${(100-bullW)}%</span><span>Bull ${bullW}%</span>
      </div>
      <div class="bar-track">
        <div class="bar-fill" style="width:${bullW}%;background:linear-gradient(90deg,#ef4444,${dirColor})"></div>
      </div>

      <div style="margin-top:10px;font-size:11px;display:flex;justify-content:space-between;align-items:center">
        <span style="color:${cc};font-weight:600">${fc.confidence} (${Math.round(fc.conf_score*100)}%)</span>
        <span style="color:#64748b">${fc.volatility} vol</span>
      </div>
      ${noTradeBanner}
    `;
  });
}

// ── Price trajectory chart ───────────────────────────────────────────────────
function renderForecastChart(forecasts, lastClose) {
  const labels = ['Now', '12H', '24H', '48H'];
  const prices = [lastClose, ...forecasts.map(f => f.pred_price)];
  const los    = [lastClose, ...forecasts.map(f => f.range_lo)];
  const his    = [lastClose, ...forecasts.map(f => f.range_hi)];
  const trend  = prices[prices.length-1] >= prices[0];

  const lineColor = trend ? '#22c55e' : '#ef4444';
  const fillColor = trend ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)';

  if (chartForecast) chartForecast.destroy();
  const ctx = document.getElementById('chart-forecast').getContext('2d');
  chartForecast = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Predicted Price',
          data: prices,
          borderColor: lineColor,
          backgroundColor: fillColor,
          tension: 0.45, fill: true, pointRadius: 5,
          pointBackgroundColor: lineColor, borderWidth: 2,
        },
        {
          label: 'Range High',
          data: his,
          borderColor: 'rgba(99,102,241,0.4)',
          borderDash: [4,4], borderWidth: 1,
          pointRadius: 0, fill: false,
        },
        {
          label: 'Range Low',
          data: los,
          borderColor: 'rgba(99,102,241,0.4)',
          borderDash: [4,4], borderWidth: 1,
          pointRadius: 0, fill: '-1',
          backgroundColor: 'rgba(99,102,241,0.06)',
        },
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: true,
      plugins: {
        legend: { labels: { color: '#64748b', font: { size: 11 } } },
        tooltip: {
          callbacks: { label: ctx => `  ${ctx.dataset.label}: ${fmtPrice(ctx.raw)}` }
        }
      },
      scales: {
        x: { ticks: { color: '#64748b' }, grid: { color: 'rgba(255,255,255,0.04)' } },
        y: { ticks: { color: '#64748b', callback: v => fmtPrice(v) },
             grid: { color: 'rgba(255,255,255,0.04)' } }
      }
    }
  });
}

// ── Directional probability chart ────────────────────────────────────────────
function renderProbChart(forecasts) {
  const labels = forecasts.map(f => f.horizon + 'H');
  const bulls  = forecasts.map(f => f.bull_prob_pct.toFixed(1));
  const bears  = forecasts.map(f => f.bear_prob_pct.toFixed(1));

  if (chartProb) chartProb.destroy();
  const ctx = document.getElementById('chart-prob').getContext('2d');
  chartProb = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        { label: 'Bull %', data: bulls, backgroundColor: 'rgba(34,197,94,0.7)',  borderRadius: 5, borderSkipped: false },
        { label: 'Bear %', data: bears, backgroundColor: 'rgba(239,68,68,0.7)', borderRadius: 5, borderSkipped: false },
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: true,
      plugins: { legend: { labels: { color: '#64748b', font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: '#94a3b8' }, grid: { display: false } },
        y: {
          min: 0, max: 100,
          ticks: { color: '#64748b', callback: v => v + '%' },
          grid: { color: 'rgba(255,255,255,0.04)' }
        }
      }
    }
  });
}

// ── AI Signal strength panel ─────────────────────────────────────────────────
function renderSignal(forecasts) {
  const panel = document.getElementById('signal-panel');
  let html = '';

  forecasts.forEach(fc => {
    const strength = Math.round(fc.trend_strength * 100);
    const bullBias = fc.bull_prob_pct >= 50;
    const biasLabel = bullBias ? '▲ Buy Bias' : '▼ Sell Bias';
    const biasColor = bullBias ? '#22c55e' : '#ef4444';
    const cc        = confColor(fc.confidence);

    html += `
      <div style="border-bottom:1px solid rgba(255,255,255,0.05);padding-bottom:12px;margin-bottom:12px">
        <div style="display:flex;justify-content:space-between;margin-bottom:6px">
          <span style="color:#94a3b8">${fc.horizon}H Signal</span>
          <span style="color:${biasColor};font-weight:600;font-size:12px">${biasLabel}</span>
        </div>
        <div style="font-size:11px;color:#64748b;margin-bottom:4px">Trend Strength</div>
        <div class="bar-track" style="margin-bottom:4px">
          <div class="bar-fill" style="width:${strength}%;background:linear-gradient(90deg,#6366f1,#00e5ff)"></div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:11px">
          <span style="color:${cc}">${fc.confidence} conf.</span>
          <span style="color:#64748b">${fc.regime}</span>
        </div>
      </div>
    `;
  });
  panel.innerHTML = html;
}

// ── Price range panel ────────────────────────────────────────────────────────
function renderRanges(forecasts) {
  const panel = document.getElementById('range-panel');
  let html = '';
  forecasts.forEach(fc => {
    const spread = ((fc.range_hi - fc.range_lo) / fc.last_close * 100).toFixed(2);
    html += `
      <div style="background:rgba(255,255,255,0.03);border-radius:8px;padding:10px">
        <div style="display:flex;justify-content:space-between;margin-bottom:4px">
          <span style="color:#64748b;font-size:11px">${fc.horizon}H Range</span>
          <span style="color:#818cf8;font-size:11px">±${spread}%</span>
        </div>
        <div style="display:flex;justify-content:space-between">
          <span style="color:#ef4444;font-size:12px;font-weight:600">${fmtPrice(fc.range_lo)}</span>
          <span style="color:#64748b;font-size:11px">↔</span>
          <span style="color:#22c55e;font-size:12px;font-weight:600">${fmtPrice(fc.range_hi)}</span>
        </div>
      </div>
    `;
  });
  panel.innerHTML = html;
}

// ── Model confidence per horizon ─────────────────────────────────────────────
function renderPerf(perf) {
  if (!perf || !perf.length) return;
  const panel = document.getElementById('perf-table');
  let html = '';
  perf.forEach(p => {
    const cc = confColor(p.no_trade ? 'LOW' : p.conf >= 65 ? 'HIGH' : p.conf >= 45 ? 'MEDIUM' : 'LOW');
    html += `
      <div style="display:flex;justify-content:space-between;align-items:center">
        <span style="color:#64748b">${p.horizon}H</span>
        <div class="bar-track" style="flex:1;margin:0 10px">
          <div class="bar-fill" style="width:${p.conf}%;background:${cc}"></div>
        </div>
        <span style="font-size:12px;font-weight:600;color:${cc}">${p.conf}%</span>
      </div>
    `;
  });
  panel.innerHTML = html;
}

// ── Risk flags ────────────────────────────────────────────────────────────────
function renderRiskFlags(flags) {
  const panel = document.getElementById('risk-flags');
  if (!flags || !flags.length) {
    panel.innerHTML = '<span class="text-xs text-slate-600">✓ No active risk flags</span>';
    return;
  }
  panel.innerHTML = flags.map(f =>
    `<div class="flag-chip">⚡ ${f}</div>`
  ).join('');
}

// ── Prediction history table ──────────────────────────────────────────────────
function renderHistory(history) {
  const panel = document.getElementById('history-panel');
  if (!history || !history.length) {
    panel.innerHTML = '<p class="text-xs text-slate-600">No history yet.</p>';
    return;
  }

  // Show last 20, newest first
  const rows = [...history].reverse().slice(0, 20);
  let html = `<table class="hist-table">
    <thead><tr>
      <th>Time</th><th>H</th><th>Pred%</th><th>Conf</th><th>Dir</th>
    </tr></thead><tbody>`;

  rows.forEach(r => {
    const ts = r.timestamp ? r.timestamp.slice(11,16) : '—';
    const dirCell = r.direction_correct == null
      ? '<td style="color:#64748b">?</td>'
      : r.direction_correct
        ? '<td style="color:#22c55e">✓</td>'
        : '<td style="color:#ef4444">✗</td>';
    const cc = confColor(r.confidence || 'LOW');
    html += `<tr>
      <td style="color:#64748b">${ts}</td>
      <td>${r.horizon}H</td>
      <td style="color:${(r.pred_ret||0)>=0?'#22c55e':'#ef4444'}">${fmtPct((r.pred_ret||0)*100)}</td>
      <td style="color:${cc}">${r.confidence||'—'}</td>
      ${dirCell}
    </tr>`;
  });

  html += '</tbody></table>';
  panel.innerHTML = html;
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
    token_opts    = "\n".join(
        f'<option value="{k}"{"selected" if k=="ETHUSDT" else ""}>{v}</option>'
        for k, v in TOKENS.items()
    )
    exchange_opts = "\n".join(
        f'<option value="{e}"{"selected" if e=="binance" else ""}>{e.capitalize()}</option>'
        for e in EXCHANGES
    )
    return render_template_string(
        UI,
        token_options=token_opts,
        exchange_options=exchange_opts
    )


@app.route("/health")
def health():
    return jsonify({"status": "ok", "engine": "Forecasting_Engine", "horizons": HORIZONS})


@app.route("/forecast/run")
def forecast_run():
    """
    Kicks off run_forecast() in a background thread immediately.
    Returns 202 Accepted while work proceeds.
    """
    symbol   = request.args.get("symbol",   "ETHUSDT")
    exchange = request.args.get("exchange", "binance")

    with _lock:
        if _state["status"] == "running":
            return jsonify({"message": "Already running"}), 409

    t = threading.Thread(
        target=_run_forecast_thread,
        args=(symbol, exchange),
        daemon=True
    )
    t.start()
    return jsonify({"message": "started", "symbol": symbol, "exchange": exchange}), 202


@app.route("/forecast/status")
def forecast_status():
    """
    Polled by the frontend every 2 s.
    Returns full state once status == 'ready'.
    """
    with _lock:
        payload = {
            "status":    _state["status"],
            "error":     _state["error"],
            "symbol":    _state["symbol"],
            "exchange":  _state["exchange"],
            "forecasts": _state["forecasts"],
            "meta":      _state["meta"],
            "history":   _state["history"],
        }
    return jsonify(payload)


@app.route("/forecast")
def forecast_legacy():
    """
    Legacy endpoint kept for backwards compatibility.
    Synchronous – blocks until forecast completes (may take 60–120 s).
    """
    symbol   = request.args.get("symbol",   "ETHUSDT")
    exchange = request.args.get("exchange", "binance")

    # Don't run if already running
    with _lock:
        if _state["status"] == "running":
            return jsonify({"error": "Forecast already in progress"}), 409

    _run_forecast_thread(symbol, exchange)

    with _lock:
        if _state["status"] == "error":
            return jsonify({"error": _state["error"]}), 500
        return jsonify({
            "symbol":    _state["symbol"],
            "timestamp": _state["meta"].get("timestamp"),
            "forecasts": _state["forecasts"],
            "meta":      _state["meta"],
        })


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"""
  ┌─────────────────────────────────────────────┐
  │   MarketFlux Engine  –  Starting            │
  │   http://localhost:{port}                      │
  │                                             │
  │   • Open browser and click ▶ Run Forecast   │
  │   • Forecasting_Engine.py must be present   │
  └─────────────────────────────────────────────┘
""")
    app.run(host="0.0.0.0", port=port, debug=False)
