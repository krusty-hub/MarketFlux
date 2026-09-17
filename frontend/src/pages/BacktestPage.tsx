import React, { useState, useEffect } from 'react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Filler,
} from 'chart.js';
import { Play, Activity, Info } from 'lucide-react';
import {
  backtestApi,
  modelsApi,
  type BacktestConfig,
  type BacktestResult,
  type ModelItem,
} from '../services/api';
import { TermTooltip } from '../components/TermTooltip';

import { useTheme } from '../context/ThemeContext';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Filler);

const SUPPORTED_PAIRS = [
  { symbol: 'BTCUSDT', name: 'Bitcoin / USDT' },
  { symbol: 'ETHUSDT', name: 'Ethereum / USDT' },
  { symbol: 'SOLUSDT', name: 'Solana / USDT' },
  { symbol: 'EURUSD',  name: 'Euro / US Dollar' },
  { symbol: 'XAUUSD',  name: 'Gold (Ounce)' },
];

export const BacktestPage: React.FC = () => {
  const { isDark } = useTheme();
  const [config, setConfig] = useState<BacktestConfig>({
    symbol: 'BTCUSDT',
    timeframe: '5m',
    limit: 1000,
    starting_balance: 10000.0,
    risk_per_trade_pct: 1.5,
    spread: 1.0,
    commission: 1.5,
    slippage_pct: 0.02,
    min_confidence: 0.60,
  });

  const [models, setModels] = useState<ModelItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<BacktestResult | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    modelsApi.list().then((res: any) => {
      setModels(res.models || []);
      if (res.models && res.models.length > 0) {
        setConfig((prev: any) => ({ ...prev, model_id: res.models[0].id }));
      }
    }).catch(() => {});
  }, []);

  const handleRun = async () => {
    try {
      setLoading(true);
      setError('');
      const data = await backtestApi.run(config);
      setResults(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Backtest simulation failed');
    } finally {
      setLoading(false);
    }
  };

  const equityData = {
    labels: results?.equity_curve?.map((_: any, i: number) => `T${i + 1}`) || [],
    datasets: [
      {
        label: 'Portfolio Equity ($)',
        data: results?.equity_curve?.map((p: any) => p.value ?? p.equity ?? p) || [],
        borderColor: '#10b981',
        backgroundColor: isDark ? 'rgba(16, 185, 129, 0.08)' : 'rgba(16, 185, 129, 0.05)',
        fill: true,
        tension: 0.15,
        pointRadius: 0,
        pointHoverRadius: 4,
        pointHoverBackgroundColor: '#10b981',
        borderWidth: 2,
      },
    ],
  };

  const ddData = {
    labels: results?.drawdown_curve?.map((_: any, i: number) => `T${i + 1}`) || [],
    datasets: [
      {
        label: 'Drawdown (%)',
        data: results?.drawdown_curve?.map((p: any) => p.value ?? p.drawdown ?? p) || [],
        borderColor: '#ef4444',
        backgroundColor: isDark ? 'rgba(239, 68, 68, 0.08)' : 'rgba(239, 68, 68, 0.05)',
        fill: true,
        tension: 0.15,
        pointRadius: 0,
        pointHoverRadius: 4,
        pointHoverBackgroundColor: '#ef4444',
        borderWidth: 1.5,
      },
    ],
  };

  const chartOptions: any = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: isDark ? 'rgba(20, 20, 22, 0.95)' : 'rgba(255, 255, 255, 0.98)',
        titleColor: isDark ? '#f8fafc' : '#0f172a',
        bodyColor: isDark ? '#f8fafc' : '#0f172a',
        borderColor: isDark ? 'rgba(38, 38, 44, 0.9)' : 'rgba(226, 232, 240, 0.9)',
        borderWidth: 1,
        bodyFont: { family: 'JetBrains Mono' },
      },
    },
    scales: {
      x: {
        grid: { color: isDark ? 'rgba(255, 255, 255, 0.06)' : 'rgba(0, 0, 0, 0.04)' },
        ticks: { color: isDark ? '#94a3b8' : '#64748b', font: { family: 'JetBrains Mono', size: 10 }, maxTicksLimit: 10 },
      },
      y: {
        position: 'right',
        grid: { color: isDark ? 'rgba(255, 255, 255, 0.06)' : 'rgba(0, 0, 0, 0.04)' },
        ticks: {
          color: isDark ? '#94a3b8' : '#64748b',
          font: { family: 'JetBrains Mono', size: 10 },
          callback: (val: any) => `$${val?.toLocaleString()}`,
        },
      },
    },
  };

  const isReturnPositive = (results?.return_pct ?? 0) >= 0;

  return (
    <div className="page-main">
      <div className="content-container">

        {/* ── HEADER ── */}
        <section className="page-header pt-12 pb-8 border-b border-[var(--border)]">
          <p className="text-meta text-[var(--accent-fresh)] mb-3 font-mono">
            Historical Strategy Research &amp; Stress Testing
          </p>
          <h1 className="font-display text-hero text-[var(--text-primary)] mb-3">
            BACKTEST THE STRATEGY.
          </h1>
          <p className="text-sm text-[var(--text-secondary)] max-w-xl">
            "What would this strategy have done historically?" Simulate model signals against verified historical candle bars.
          </p>
        </section>

        {/* ── DISCLAIMER BANNER ── */}
        <div className="my-6 p-4 rounded-lg bg-[var(--surface)] border border-[var(--border)] flex items-start gap-3 text-xs text-[var(--text-secondary)] leading-relaxed">
          <Info size={16} className="text-[var(--accent-fresh)] shrink-0 mt-0.5" />
          <p>
            <strong>Research Notice</strong>: Backtests use historical market data and do not guarantee future performance.
            Live market conditions may exhibit differences in slippage, execution timing, and spread.
          </p>
        </div>

        {/* ── WORKFLOW CONTROLS ── */}
        <section className="my-8 p-6 md:p-8 rounded-xl bg-[var(--surface)] border border-[var(--border)]">
          <h2 className="font-display text-2xl text-[var(--text-primary)] mb-6">
            Configure Backtest Parameters
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {/* Step 1: Select Market */}
            <div>
              <label className="block text-meta text-[var(--text-muted)] font-mono mb-2">
                1. Select Market
              </label>
              <select
                value={config.symbol}
                onChange={(e) => setConfig({ ...config, symbol: e.target.value })}
                className="input-editorial font-mono"
              >
                {SUPPORTED_PAIRS.map((p) => (
                  <option key={p.symbol} value={p.symbol}>
                    {p.symbol} ({p.name})
                  </option>
                ))}
              </select>
            </div>

            {/* Step 2: Select Period */}
            <div>
              <label className="block text-meta text-[var(--text-muted)] font-mono mb-2">
                2. Historical Period
              </label>
              <select
                value={config.limit}
                onChange={(e) => setConfig({ ...config, limit: parseInt(e.target.value) })}
                className="input-editorial font-mono"
              >
                <option value={500}>500 Bars (~2 weeks)</option>
                <option value={1000}>1,000 Bars (~1 month)</option>
                <option value={2500}>2,500 Bars (~3 months)</option>
                <option value={5000}>5,000 Bars (~6 months)</option>
              </select>
            </div>

            {/* Step 3: Select Strategy Model */}
            <div>
              <label className="block text-meta text-[var(--text-muted)] font-mono mb-2">
                3. Strategy Model
              </label>
              <select
                value={config.model_id || ''}
                onChange={(e) => setConfig({ ...config, model_id: e.target.value })}
                className="input-editorial font-mono"
              >
                <option value="">Active Production Model</option>
                {models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.id} {m.is_active ? '(Active)' : ''}
                  </option>
                ))}
              </select>
            </div>

            {/* Step 4: Starting Capital */}
            <div>
              <label className="block text-meta text-[var(--text-muted)] font-mono mb-2">
                Starting Balance ($)
              </label>
              <input
                type="number"
                value={config.starting_balance}
                onChange={(e) => setConfig({ ...config, starting_balance: parseFloat(e.target.value) })}
                className="input-editorial font-mono"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mt-6 pt-6 border-t border-[var(--border)]">
            <div>
              <label className="block text-meta text-[var(--text-muted)] font-mono mb-2">
                <TermTooltip term="R:R">Risk Per Trade (%)</TermTooltip>
              </label>
              <input
                type="number"
                step="0.1"
                value={config.risk_per_trade_pct}
                onChange={(e) => setConfig({ ...config, risk_per_trade_pct: parseFloat(e.target.value) })}
                className="input-editorial font-mono"
              />
            </div>

            <div>
              <label className="block text-meta text-[var(--text-muted)] font-mono mb-2">
                Simulated Slippage (%)
              </label>
              <input
                type="number"
                step="0.01"
                value={config.slippage_pct}
                onChange={(e) => setConfig({ ...config, slippage_pct: parseFloat(e.target.value) })}
                className="input-editorial font-mono"
              />
            </div>

            <div>
              <label className="block text-meta text-[var(--text-muted)] font-mono mb-2">
                Min AI Confidence
              </label>
              <input
                type="number"
                step="0.05"
                min="0.5"
                max="0.95"
                value={config.min_confidence}
                onChange={(e) => setConfig({ ...config, min_confidence: parseFloat(e.target.value) })}
                className="input-editorial font-mono"
              />
            </div>
          </div>

          {error && (
            <div className="mt-4 p-3 rounded bg-[var(--red-subtle)] text-[var(--red)] font-mono text-xs">
              {error}
            </div>
          )}

          <div className="mt-8 pt-6 border-t border-[var(--border)] flex justify-end">
            <button
              onClick={handleRun}
              disabled={loading}
              className="btn btn-primary text-xs"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <Activity size={14} className="animate-spin" />
                  Simulating Trades on Historical Bars...
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <Play size={14} />
                  Run Backtest Simulation
                </span>
              )}
            </button>
          </div>
        </section>

        {/* ── RESULTS DISPLAY (ONLY REAL RETURNED METRICS) ── */}
        {results && (
          <section className="my-10 space-y-8">
            {/* Stat Strip */}
            <div className="stat-strip">
              <div className="stat-strip-item">
                <span className="text-meta text-[var(--text-muted)] block mb-1">
                  Starting Balance
                </span>
                <p className="font-mono text-2xl font-semibold text-[var(--text-primary)]">
                  ${results.starting_balance?.toLocaleString()}
                </p>
                <p className="text-xs text-[var(--text-muted)] font-mono mt-1">
                  Initial deposit
                </p>
              </div>

              <div className="stat-strip-item">
                <span className="text-meta text-[var(--text-muted)] block mb-1">
                  Ending Balance
                </span>
                <p className="font-mono text-2xl font-semibold text-[var(--text-primary)]">
                  ${results.final_equity?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </p>
                <p className={`text-xs font-mono mt-1 ${isReturnPositive ? 'text-[var(--accent-fresh)]' : 'text-[var(--red)]'}`}>
                  Net: {isReturnPositive ? '+' : ''}${results.net_pnl?.toFixed(2)}
                </p>
              </div>

              <div className="stat-strip-item">
                <span className="text-meta text-[var(--text-muted)] block mb-1">
                  Total Net Return
                </span>
                <p className={`font-mono text-2xl font-semibold ${isReturnPositive ? 'text-[var(--accent-fresh)]' : 'text-[var(--red)]'}`}>
                  {isReturnPositive ? '+' : ''}{results.return_pct}%
                </p>
                <p className="text-xs text-[var(--text-muted)] font-mono mt-1">
                  Over {results.bars_tested} bars
                </p>
              </div>

              <div className="stat-strip-item">
                <span className="text-meta text-[var(--text-muted)] block mb-1">
                  <TermTooltip term="Win Rate">Win Rate</TermTooltip>
                </span>
                <p className="font-mono text-2xl font-semibold text-[var(--accent-fresh)]">
                  {results.win_rate}%
                </p>
                <p className="text-xs text-[var(--text-secondary)] font-mono mt-1">
                  {results.winning_trades} wins / {results.losing_trades} losses
                </p>
              </div>

              <div className="stat-strip-item">
                <span className="text-meta text-[var(--text-muted)] block mb-1">
                  Profit Factor
                </span>
                <p className="font-mono text-2xl font-semibold text-[var(--text-primary)]">
                  {results.profit_factor?.toFixed(2)}
                </p>
                <p className="text-xs text-[var(--text-muted)] font-mono mt-1">
                  Gross profit / Gross loss
                </p>
              </div>

              <div className="stat-strip-item">
                <span className="text-meta text-[var(--text-muted)] block mb-1">
                  <TermTooltip term="Drawdown">Max Drawdown</TermTooltip>
                </span>
                <p className="font-mono text-2xl font-semibold text-[var(--red)]">
                  {results.max_drawdown_pct}%
                </p>
                <p className="text-xs text-[var(--text-muted)] font-mono mt-1">
                  Peak-to-trough decline
                </p>
              </div>
            </div>

            {/* Equity Curve Chart */}
            <div className="p-6 rounded-xl bg-[var(--surface)] border border-[var(--border)]">
              <h3 className="font-display text-xl text-[var(--text-primary)] mb-4">
                Simulated Equity Growth Curve
              </h3>
              <div className="h-72 w-full">
                <Line data={equityData} options={chartOptions} />
              </div>
            </div>

            {/* Drawdown Curve */}
            <div className="p-6 rounded-xl bg-[var(--surface)] border border-[var(--border)]">
              <h3 className="font-display text-xl text-[var(--text-primary)] mb-4">
                Drawdown Distribution Curve
              </h3>
              <div className="h-48 w-full">
                <Line data={ddData} options={chartOptions} />
              </div>
            </div>
          </section>
        )}

      </div>
    </div>
  );
};
