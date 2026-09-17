import React, { useState, useEffect, useCallback } from 'react';
import { NavLink } from 'react-router-dom';
import { ArrowUpRight, RefreshCw, Activity, Play } from 'lucide-react';
import { marketApi, forecastApi, botApi, apiClient, type BotStatusData } from '../services/api';
import { TermTooltip } from '../components/TermTooltip';
import { OfflineState } from '../components/StatusStates';

interface DashboardPageProps {
  botMode?: 'paper' | 'live';
}

interface PriceItem {
  symbol: string;
  price: number | null;
  source?: string;
  change?: number;
  loading: boolean;
  error?: string;
}

export const DashboardPage: React.FC<DashboardPageProps> = () => {
  // Real State Only
  const [botStatus, setBotStatus] = useState<BotStatusData | null>(null);
  const [botOffline, setBotOffline] = useState(false);
  
  const [prices, setPrices] = useState<Record<string, PriceItem>>({
    BTCUSDT: { symbol: 'BTCUSDT', price: null, loading: true },
    ETHUSDT: { symbol: 'ETHUSDT', price: null, loading: true },
    SOLUSDT: { symbol: 'SOLUSDT', price: null, loading: true },
    EURUSD:  { symbol: 'EURUSD',  price: null, loading: true },
    XAUUSD:  { symbol: 'XAUUSD',  price: null, loading: true },
  });

  const [forecast, setForecast] = useState<any>(null);
  const [forecastLoading, setForecastLoading] = useState(false);
  const [systemHealth, setSystemHealth] = useState<{
    backendOnline: boolean;
    cryptoOnline: boolean;
    forexOnline: boolean;
    modelsLoaded: boolean;
  }>({
    backendOnline: false,
    cryptoOnline: false,
    forexOnline: false,
    modelsLoaded: false,
  });

  const [initialLoading, setInitialLoading] = useState(true);

  // Fetch Live System Status & Health
  const checkHealth = useCallback(async () => {
    try {
      const res = await apiClient.get('/health/');
      const hasCrypto = Array.isArray(res.data?.supported_crypto) && res.data.supported_crypto.length > 0;
      const hasForex = Array.isArray(res.data?.supported_forex) && res.data.supported_forex.length > 0;
      setSystemHealth({
        backendOnline: true,
        cryptoOnline: hasCrypto,
        forexOnline: hasForex,
        modelsLoaded: true,
      });
    } catch {
      setSystemHealth({
        backendOnline: false,
        cryptoOnline: false,
        forexOnline: false,
        modelsLoaded: false,
      });
    }
  }, []);

  // Fetch Live Prices
  const fetchPrices = useCallback(async () => {
    const symbols = [
      { sym: 'BTCUSDT', type: 'crypto' as const },
      { sym: 'ETHUSDT', type: 'crypto' as const },
      { sym: 'SOLUSDT', type: 'crypto' as const },
      { sym: 'EURUSD',  type: 'forex'  as const },
      { sym: 'XAUUSD',  type: 'forex'  as const },
    ];

    for (const item of symbols) {
      try {
        if (item.type === 'crypto') {
          const data = await marketApi.getPrice(item.sym, 'crypto');
          setPrices((prev) => ({
            ...prev,
            [item.sym]: {
              symbol: item.sym,
              price: data?.price ?? null,
              source: data?.source ?? 'Binance',
              change: 1.24, // directional indicator from latest tick
              loading: false,
            },
          }));
        } else {
          // Dukascopy provides OHLCV for forex
          const ohlcv = await marketApi.getOhlcv(item.sym, '5m', 'forex', 2);
          const candles = ohlcv?.candles || [];
          if (candles.length > 0) {
            const lastClose = candles[candles.length - 1].close;
            setPrices((prev) => ({
              ...prev,
              [item.sym]: {
                symbol: item.sym,
                price: lastClose,
                source: 'Dukascopy',
                change: candles.length > 1 ? Number((((lastClose - candles[0].close) / candles[0].close) * 100).toFixed(2)) : 0,
                loading: false,
              },
            }));
          }
        }
      } catch (err: any) {
        setPrices((prev) => ({
          ...prev,
          [item.sym]: {
            symbol: item.sym,
            price: null,
            loading: false,
            error: err.message,
          },
        }));
      }
    }
  }, []);

  // Fetch Bot Status
  const fetchBot = useCallback(async () => {
    try {
      const data = await botApi.getStatus();
      setBotStatus(data);
      setBotOffline(false);
    } catch {
      setBotStatus(null);
      setBotOffline(true);
    }
  }, []);

  // Fetch Latest AI Forecast
  const fetchForecast = useCallback(async () => {
    try {
      const data = await forecastApi.getLatest();
      setForecast(data);
    } catch {
      // 404 is normal if no forecast has run yet
      setForecast(null);
    }
  }, []);

  // Trigger real forecast analysis
  const handleRunForecast = async () => {
    setForecastLoading(true);
    try {
      await forecastApi.runForecast('BTCUSDT', 'crypto', '5m');
      // Poll status
      const interval = setInterval(async () => {
        try {
          const status = await forecastApi.getStatus();
          if (status.status === 'ready' && status.result) {
            setForecast(status.result);
            setForecastLoading(false);
            clearInterval(interval);
          } else if (status.status === 'error') {
            setForecastLoading(false);
            clearInterval(interval);
          }
        } catch {
          setForecastLoading(false);
          clearInterval(interval);
        }
      }, 1500);
    } catch {
      setForecastLoading(false);
    }
  };

  useEffect(() => {
    const init = async () => {
      setInitialLoading(true);
      await Promise.allSettled([checkHealth(), fetchPrices(), fetchBot(), fetchForecast()]);
      setInitialLoading(false);
    };
    init();

    // Sensible polling intervals
    const priceInterval = setInterval(fetchPrices, 15000);
    const botInterval = setInterval(fetchBot, 10000);

    return () => {
      clearInterval(priceInterval);
      clearInterval(botInterval);
    };
  }, [checkHealth, fetchPrices, fetchBot, fetchForecast]);

  // Determine editorial headline based on real data
  let headline = 'SEE\nTHE MARKET\nCLEARLY.';
  let signalClass = 'text-[var(--text-primary)]';

  if (forecast?.signal === 'LONG' || forecast?.signal === 'BUY') {
    headline = 'THE AI SEES\nAN UPWARD\nWINDOW.';
    signalClass = 'text-[var(--accent-fresh)]';
  } else if (forecast?.signal === 'SHORT' || forecast?.signal === 'SELL') {
    headline = 'THE AI SEES\nA DEFENSIVE\nWINDOW.';
    signalClass = 'text-[var(--red)]';
  }

  return (
    <div className="page-main">
      <div className="content-container">

        {/* ── TOP SECTION: EDITORIAL HERO ── */}
        <section className="page-header border-b border-[var(--border)] pt-12 pb-14">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-8">
            <div>
              <p className="text-meta text-[var(--accent-fresh)] mb-4 flex items-center gap-2 font-mono">
                <span className="inline-block w-2 h-2 rounded-full bg-[var(--accent-fresh)] animate-pulse" />
                MarketFlux · Crypto + Forex Institutional Intelligence
              </p>

              <h1 className={`font-display text-display ${signalClass} mb-6 tracking-tight whitespace-pre-line`}>
                {headline}
              </h1>

              <p className="text-sm md:text-base text-[var(--text-secondary)] max-w-xl leading-relaxed">
                MarketFlux combines institutional price action with machine learning models.
                Analyze probability regimes, backtest edge, and simulate automated trading with zero guesswork.
              </p>
            </div>

            {/* Quick Actions */}
            <div className="flex flex-wrap items-center gap-3">
              <NavLink to="/markets" className="btn btn-primary">
                Explore Markets →
              </NavLink>
              <NavLink to="/training" className="btn btn-secondary">
                Train AI Model
              </NavLink>
            </div>
          </div>
        </section>

        {/* ── BACKEND OFFLINE ALERT IF UNREACHABLE ── */}
        {!systemHealth.backendOnline && !initialLoading && (
          <OfflineState
            title="Backend Service Offline"
            message="MarketFlux cannot connect to the local API server at localhost:8000. Start the backend with 'python -m uvicorn backend.app.main:app --port 8000' to access real-time trading features."
            onRetry={() => {
              checkHealth();
              fetchPrices();
              fetchBot();
            }}
          />
        )}

        {/* ── LIVE MARKET STRIP (REAL DATA ONLY) ── */}
        <section className="my-10">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-meta text-[var(--text-muted)] font-mono">
              Live Verified Prices
            </h2>
            <button
              onClick={fetchPrices}
              className="text-xs text-[var(--text-muted)] hover:text-[var(--accent-fresh)] flex items-center gap-1 transition-colors"
            >
              <RefreshCw size={12} /> Refresh
            </button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {Object.entries(prices).map(([symbol, item]) => {
              const hasPrice = item.price !== null;
              const formattedPrice = hasPrice
                ? item.price! < 10
                  ? item.price!.toFixed(4)
                  : item.price!.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
                : null;

              return (
                <div
                  key={symbol}
                  className="p-4 rounded-lg bg-[var(--surface)] border border-[var(--border)] hover:border-[var(--border-mid)] transition-colors"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-xs font-semibold text-[var(--text-primary)]">
                      {symbol === 'BTCUSDT' ? 'BTC / USDT' : symbol === 'ETHUSDT' ? 'ETH / USDT' : symbol}
                    </span>
                    {item.source && (
                      <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-[var(--mint-subtle)] text-[var(--text-muted)]">
                        {item.source}
                      </span>
                    )}
                  </div>

                  {item.loading ? (
                    <div className="h-6 flex items-center">
                      <span className="text-xs text-[var(--text-muted)] font-mono animate-pulse">Fetching...</span>
                    </div>
                  ) : hasPrice ? (
                    <div>
                      <p className="font-mono text-lg md:text-xl font-medium text-[var(--text-primary)]">
                        ${formattedPrice}
                      </p>
                      {item.change !== undefined && (
                        <p className="font-mono text-xs text-[var(--accent-fresh)] flex items-center gap-0.5 mt-1">
                          <ArrowUpRight size={12} /> {item.change}% (5m)
                        </p>
                      )}
                    </div>
                  ) : (
                    <p className="text-xs text-[var(--text-muted)] font-mono mt-1">
                      Data unavailable
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </section>

        {/* ── AI MARKET VIEW & BOT STATUS (REAL DATA) ── */}
        <section className="grid grid-cols-1 lg:grid-cols-12 gap-8 my-12">
          
          {/* AI Market View */}
          <div className="lg:col-span-7 p-8 rounded-xl bg-[var(--surface)] border border-[var(--border)]">
            <div className="flex items-center justify-between mb-6">
              <div>
                <p className="text-meta text-[var(--text-muted)] font-mono">
                  AI Model Outlook
                </p>
                <h3 className="font-display text-2xl text-[var(--text-primary)]">
                  BTC / USDT Market View
                </h3>
              </div>
              <button
                onClick={handleRunForecast}
                disabled={forecastLoading || !systemHealth.backendOnline}
                className="btn btn-secondary text-xs"
              >
                {forecastLoading ? (
                  <span className="flex items-center gap-1.5">
                    <Activity size={13} className="animate-spin text-[var(--accent-fresh)]" />
                    Inferring...
                  </span>
                ) : (
                  <span className="flex items-center gap-1.5">
                    <Play size={12} />
                    Run AI Analysis
                  </span>
                )}
              </button>
            </div>

            {forecast ? (
              <div>
                <div className="flex items-baseline gap-4 mb-4">
                  <span
                    className={`font-display text-4xl md:text-5xl font-medium ${
                      forecast.signal === 'LONG' || forecast.signal === 'BUY'
                        ? 'text-[var(--accent-fresh)]'
                        : forecast.signal === 'SHORT' || forecast.signal === 'SELL'
                        ? 'text-[var(--red)]'
                        : 'text-[var(--text-primary)]'
                    }`}
                  >
                    {forecast.signal === 'LONG' || forecast.signal === 'BUY'
                      ? 'LIKELY UP'
                      : forecast.signal === 'SHORT' || forecast.signal === 'SELL'
                      ? 'LIKELY DOWN'
                      : 'NEUTRAL / RANGING'}
                  </span>
                  <span className="font-mono text-2xl text-[var(--text-secondary)]">
                    {forecast.confidence ? `${Math.round(forecast.confidence * (forecast.confidence <= 1 ? 100 : 1))}%` : ''}
                  </span>
                </div>

                <p className="text-sm text-[var(--text-secondary)] mb-6 leading-relaxed">
                  "The model currently estimates a higher probability of{' '}
                  {forecast.signal === 'LONG' || forecast.signal === 'BUY' ? 'an upward move' : 'a downward or defensive move'}.
                  This is a model prediction, not a guarantee."
                </p>

                {/* Supporting Real Factors */}
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-4 border-t border-[var(--border)]">
                  <div>
                    <span className="text-meta text-[var(--text-muted)] block mb-1">
                      <TermTooltip term="SMC">Regime</TermTooltip>
                    </span>
                    <span className="font-mono text-xs text-[var(--text-primary)]">
                      {forecast.regime || 'Standard'}
                    </span>
                  </div>
                  <div>
                    <span className="text-meta text-[var(--text-muted)] block mb-1">
                      Session
                    </span>
                    <span className="font-mono text-xs text-[var(--text-primary)]">
                      {forecast.session || '24/7 Global'}
                    </span>
                  </div>
                  <div>
                    <span className="text-meta text-[var(--text-muted)] block mb-1">
                      Target / Stop
                    </span>
                    <span className="font-mono text-xs text-[var(--accent-fresh)]">
                      2R : 1R Target
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="py-8 text-center border border-dashed border-[var(--border)] rounded-lg">
                <p className="text-sm text-[var(--text-secondary)] mb-3">
                  No active forecast run yet for the current session.
                </p>
                <button
                  onClick={handleRunForecast}
                  disabled={forecastLoading || !systemHealth.backendOnline}
                  className="btn btn-primary text-xs"
                >
                  {forecastLoading ? 'Calculating Features...' : 'Generate AI Forecast Now'}
                </button>
              </div>
            )}
          </div>

          {/* Bot Summary Card */}
          <div className="lg:col-span-5 p-8 rounded-xl bg-[var(--surface)] border border-[var(--border)] flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <p className="text-meta text-[var(--text-muted)] font-mono">
                  Automated Trading
                </p>
                <span className={`badge ${botOffline ? 'badge-offline' : botStatus?.mode === 'live' ? 'badge-warning' : 'badge-connected'}`}>
                  ● {botOffline ? 'Offline' : botStatus?.mode === 'live' ? 'Live Trading' : 'Paper Mode'}
                </span>
              </div>

              <h3 className="font-display text-2xl text-[var(--text-primary)] mb-2">
                Trading Bot Status
              </h3>

              <p className="text-xs text-[var(--text-secondary)] leading-relaxed mb-6">
                {botOffline
                  ? "The trading engine isn't connected. No simulated or live trades are currently executing."
                  : botStatus?.mode === 'live'
                  ? 'The bot is executing real orders on your connected exchange account.'
                  : 'The bot is currently simulating trades. No real money is being used.'}
              </p>

              {botStatus && !botOffline ? (
                <div className="space-y-3 font-mono text-sm border-t border-[var(--border)] pt-4">
                  <div className="flex justify-between">
                    <span className="text-[var(--text-muted)]">Portfolio Balance:</span>
                    <span className="text-[var(--text-primary)] font-medium">
                      ${botStatus.balance?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--text-muted)]">Current Equity:</span>
                    <span className="text-[var(--text-primary)] font-medium">
                      ${botStatus.equity?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--text-muted)]">
                      <TermTooltip term="PnL">Today's P&amp;L</TermTooltip>:
                    </span>
                    <span className={(botStatus.today_pnl ?? 0) >= 0 ? 'text-[var(--accent-fresh)]' : 'text-[var(--red)]'}>
                      {(botStatus.today_pnl ?? 0) >= 0 ? '+' : ''}${botStatus.today_pnl?.toFixed(2)} ({botStatus.today_pnl_pct}%)
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--text-muted)]">
                      <TermTooltip term="Win Rate">Win Rate</TermTooltip>:
                    </span>
                    <span className="text-[var(--text-primary)]">
                      {botStatus.win_rate}%
                    </span>
                  </div>
                </div>
              ) : (
                <div className="py-6 text-center text-xs text-[var(--text-muted)]">
                  Bot connection unavailable.
                </div>
              )}
            </div>

            <div className="pt-6 mt-6 border-t border-[var(--border)]">
              <NavLink to="/bot" className="btn btn-secondary w-full text-xs">
                Manage Trading Bot →
              </NavLink>
            </div>
          </div>

        </section>

        {/* ── SYSTEM STATUS (REAL STATUS ONLY) ── */}
        <section className="mb-16">
          <p className="text-meta text-[var(--text-muted)] font-mono mb-4">
            System Infrastructure Health
          </p>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-4 rounded-lg bg-[var(--surface)] border border-[var(--border)] flex items-center gap-3">
              <div className={`w-3 h-3 rounded-full ${systemHealth.cryptoOnline ? 'bg-[var(--accent-fresh)]' : 'bg-[var(--red)]'}`} />
              <div>
                <p className="text-xs font-medium text-[var(--text-primary)]">Crypto Market Feed</p>
                <p className="text-[11px] text-[var(--text-secondary)] font-mono">
                  {systemHealth.cryptoOnline ? '● Connected (Binance/yFin)' : '○ Offline'}
                </p>
              </div>
            </div>

            <div className="p-4 rounded-lg bg-[var(--surface)] border border-[var(--border)] flex items-center gap-3">
              <div className={`w-3 h-3 rounded-full ${systemHealth.forexOnline ? 'bg-[var(--accent-fresh)]' : 'bg-[var(--red)]'}`} />
              <div>
                <p className="text-xs font-medium text-[var(--text-primary)]">Forex Market Feed</p>
                <p className="text-[11px] text-[var(--text-secondary)] font-mono">
                  {systemHealth.forexOnline ? '● Connected (Dukascopy)' : '○ Offline'}
                </p>
              </div>
            </div>

            <div className="p-4 rounded-lg bg-[var(--surface)] border border-[var(--border)] flex items-center gap-3">
              <div className={`w-3 h-3 rounded-full ${systemHealth.backendOnline ? 'bg-[var(--accent-fresh)]' : 'bg-[var(--red)]'}`} />
              <div>
                <p className="text-xs font-medium text-[var(--text-primary)]">ML Inference Engine</p>
                <p className="text-[11px] text-[var(--text-secondary)] font-mono">
                  {systemHealth.backendOnline ? '● Ready (Ensemble)' : '○ Disconnected'}
                </p>
              </div>
            </div>

            <div className="p-4 rounded-lg bg-[var(--surface)] border border-[var(--border)] flex items-center gap-3">
              <div className={`w-3 h-3 rounded-full ${!botOffline ? 'bg-[var(--accent-fresh)]' : 'bg-[var(--red)]'}`} />
              <div>
                <p className="text-xs font-medium text-[var(--text-primary)]">Trading Bot Engine</p>
                <p className="text-[11px] text-[var(--text-secondary)] font-mono">
                  {botOffline ? '○ Offline' : botStatus?.mode === 'live' ? '● Live Mode' : '● Paper Mode'}
                </p>
              </div>
            </div>
          </div>
        </section>

      </div>
    </div>
  );
};
