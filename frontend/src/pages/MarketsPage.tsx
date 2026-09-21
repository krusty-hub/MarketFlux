import React, { useState, useEffect, useCallback } from 'react';
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
import { Line } from 'react-chartjs-2';
import { ArrowUpRight, ArrowDownRight, RefreshCw, Activity } from 'lucide-react';
import { marketApi } from '../services/api';
import { TermTooltip } from '../components/TermTooltip';
import { useTheme } from '../context/ThemeContext';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Filler
);

interface SymbolInfo {
  symbol: string;
  name: string;
  type: 'crypto' | 'forex';
}

const SUPPORTED_INSTRUMENTS: SymbolInfo[] = [
  { symbol: 'BTCUSDT', name: 'Bitcoin', type: 'crypto' },
  { symbol: 'ETHUSDT', name: 'Ethereum', type: 'crypto' },
  { symbol: 'SOLUSDT', name: 'Solana', type: 'crypto' },
  { symbol: 'BNBUSDT', name: 'BNB', type: 'crypto' },
  { symbol: 'XRPUSDT', name: 'XRP', type: 'crypto' },
  { symbol: 'ADAUSDT', name: 'Cardano', type: 'crypto' },
  { symbol: 'DOGEUSDT', name: 'Dogecoin', type: 'crypto' },
  { symbol: 'LINKUSDT', name: 'Chainlink', type: 'crypto' },
  { symbol: 'AVAXUSDT', name: 'Avalanche', type: 'crypto' },
  { symbol: 'DOTUSDT',  name: 'Polkadot', type: 'crypto' },
  { symbol: 'EURUSD',   name: 'Euro / US Dollar', type: 'forex' },
  { symbol: 'XAUUSD',   name: 'Gold (Ounce)', type: 'forex' },
  { symbol: 'USDCAD',   name: 'USD / CAD', type: 'forex' },
  { symbol: 'USDCHF',   name: 'USD / Swiss Franc', type: 'forex' },
];

const TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1d'];

export const MarketsPage: React.FC = () => {
  const { isDark } = useTheme();
  const [selectedSymbol, setSelectedSymbol] = useState('BTCUSDT');
  const [timeframe, setTimeframe] = useState('5m');
  const [filterType, setFilterType] = useState<'all' | 'crypto' | 'forex'>('all');
  
  // Real Market Data State
  const [currentPrice, setCurrentPrice] = useState<number | null>(null);
  const [priceSource, setPriceSource] = useState<string>('');
  const [priceLoading, setPriceLoading] = useState(false);
  const [priceError, setPriceError] = useState<string | null>(null);

  // Candles State for Large Chart
  const [candles, setCandles] = useState<any[]>([]);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError, setChartError] = useState<string | null>(null);

  // Symbol summary prices
  const [marketPrices, setMarketPrices] = useState<Record<string, number | null>>({});

  const selectedInfo = SUPPORTED_INSTRUMENTS.find((s) => s.symbol === selectedSymbol) || SUPPORTED_INSTRUMENTS[0];

  // Fetch Current Selected Price
  const fetchSelectedPrice = useCallback(async () => {
    setPriceLoading(true);
    setPriceError(null);
    try {
      if (selectedInfo.type === 'crypto') {
        const data = await marketApi.getPrice(selectedSymbol, 'crypto');
        setCurrentPrice(data?.price ?? null);
        setPriceSource(data?.source ?? 'Binance');
      } else {
        const ohlcv = await marketApi.getOhlcv(selectedSymbol, timeframe, 'forex', 2);
        const list = ohlcv?.candles || [];
        if (list.length > 0) {
          setCurrentPrice(list[list.length - 1].close);
          setPriceSource('Dukascopy');
        } else {
          setCurrentPrice(null);
        }
      }
    } catch (err: any) {
      setPriceError(err?.message || 'Price feed unavailable');
      setCurrentPrice(null);
    } finally {
      setPriceLoading(false);
    }
  }, [selectedSymbol, selectedInfo.type, timeframe]);

  // Fetch Real OHLCV Candles for Chart
  const fetchCandles = useCallback(async () => {
    setChartLoading(true);
    setChartError(null);
    try {
      const data = await marketApi.getOhlcv(selectedSymbol, timeframe, selectedInfo.type, 100);
      const list = data?.candles || [];
      setCandles(list);
    } catch (err: any) {
      setChartError(err?.message || 'Could not fetch historical candles');
      setCandles([]);
    } finally {
      setChartLoading(false);
    }
  }, [selectedSymbol, timeframe, selectedInfo.type]);

  // Initial load on symbol / timeframe change
  useEffect(() => {
    fetchSelectedPrice();
    fetchCandles();
  }, [fetchSelectedPrice, fetchCandles]);

  // Fetch summary price for other symbols
  useEffect(() => {
    const fetchSummaries = async () => {
      for (const inst of SUPPORTED_INSTRUMENTS.slice(0, 8)) {
        try {
          if (inst.type === 'crypto') {
            const d = await marketApi.getPrice(inst.symbol, 'crypto');
            if (d?.price) {
              setMarketPrices((p) => ({ ...p, [inst.symbol]: d.price }));
            }
          }
        } catch {
          // ignore background errors
        }
      }
    };
    fetchSummaries();
  }, []);

  // Calculate 24h / range metrics from real candles
  const highPrice = candles.length > 0 ? Math.max(...candles.map((c) => c.high)) : null;
  const lowPrice = candles.length > 0 ? Math.min(...candles.map((c) => c.low)) : null;
  const firstClose = candles.length > 0 ? candles[0].close : null;
  const lastClose = currentPrice ?? (candles.length > 0 ? candles[candles.length - 1].close : null);
  const priceChangePct = firstClose && lastClose ? Number((((lastClose - firstClose) / firstClose) * 100).toFixed(2)) : null;

  // Chart Data Configuration with Light / Dark mode responsiveness
  const chartData = {
    labels: candles.map((c) => {
      const d = new Date(c.timestamp);
      return isNaN(d.getTime()) ? c.timestamp.slice(-8) : d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }),
    datasets: [
      {
        label: `${selectedSymbol} Price`,
        data: candles.map((c) => c.close),
        borderColor: '#10b981',
        backgroundColor: isDark ? 'rgba(16, 185, 129, 0.08)' : 'rgba(16, 185, 129, 0.06)',
        borderWidth: 2,
        fill: true,
        tension: 0.15,
        pointRadius: 0,
        pointHoverRadius: 4,
        pointHoverBackgroundColor: '#10b981',
      },
    ],
  };

  const chartOptions: any = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        mode: 'index',
        intersect: false,
        backgroundColor: isDark ? 'rgba(20, 20, 22, 0.95)' : 'rgba(255, 255, 255, 0.98)',
        titleColor: isDark ? '#f8fafc' : '#0f172a',
        bodyColor: isDark ? '#f8fafc' : '#0f172a',
        borderColor: isDark ? 'rgba(38, 38, 44, 0.9)' : 'rgba(226, 232, 240, 0.9)',
        borderWidth: 1,
        bodyFont: { family: 'JetBrains Mono' },
        callbacks: {
          label: (context: any) => ` Price: $${context.raw?.toLocaleString()}`,
        },
      },
    },
    scales: {
      x: {
        grid: { color: isDark ? 'rgba(255, 255, 255, 0.06)' : 'rgba(0, 0, 0, 0.04)' },
        ticks: { color: isDark ? '#94a3b8' : '#64748b', maxTicksLimit: 8, font: { family: 'JetBrains Mono', size: 11 } },
      },
      y: {
        position: 'right',
        grid: { color: isDark ? 'rgba(255, 255, 255, 0.06)' : 'rgba(0, 0, 0, 0.04)' },
        ticks: {
          color: isDark ? '#94a3b8' : '#64748b',
          font: { family: 'JetBrains Mono', size: 11 },
          callback: (value: any) => `$${value < 10 ? value.toFixed(4) : value.toLocaleString()}`,
        },
      },
    },
  };

  const filteredInstruments = SUPPORTED_INSTRUMENTS.filter((i) => {
    if (filterType === 'all') return true;
    return i.type === filterType;
  });

  return (
    <div className="page-main">
      <div className="content-container">

        {/* ── HEADER ── */}
        <section className="page-header pt-12 pb-8 border-b border-[var(--border)]">
          <p className="text-meta text-[var(--accent-fresh)] mb-3 font-mono">
            Research &amp; Liquidity Workspace
          </p>
          <h1 className="font-display text-hero text-[var(--text-primary)] mb-3">
            MARKETS.
          </h1>
          <p className="text-sm text-[var(--text-secondary)] max-w-xl">
            Live institutional candlestick feeds, algorithmic structure regimes, and multi-asset price action.
          </p>
        </section>

        {/* ── INSTRUMENT SWITCHER STRIP ── */}
        <div className="flex flex-wrap items-center justify-between gap-4 my-6 pb-4 border-b border-[var(--border)]">
          {/* Market Type Filter */}
          <div className="flex items-center gap-2">
            {(['all', 'crypto', 'forex'] as const).map((t) => (
              <button
                key={t}
                onClick={() => setFilterType(t)}
                className={`px-3 py-1 text-xs uppercase font-mono font-semibold rounded transition-colors ${
                  filterType === t
                    ? 'bg-[var(--surface-hover)] text-[var(--accent-fresh)] border border-[var(--border-mid)]'
                    : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          {/* Quick Instrument Chips */}
          <div className="flex items-center gap-2 overflow-x-auto max-w-full pb-1">
            {filteredInstruments.map((inst) => {
              const active = inst.symbol === selectedSymbol;
              return (
                <button
                  key={inst.symbol}
                  onClick={() => setSelectedSymbol(inst.symbol)}
                  className={`px-3 py-1.5 rounded text-xs font-mono font-medium transition-all whitespace-nowrap ${
                    active
                      ? 'bg-[var(--accent)] text-[var(--btn-text)] font-semibold shadow-sm'
                      : 'bg-[var(--surface)] text-[var(--text-secondary)] border border-[var(--border)] hover:border-[var(--border-mid)]'
                  }`}
                >
                  {inst.symbol}
                </button>
              );
            })}
          </div>
        </div>

        {/* ── DOMINANT SELECTED MARKET DISPLAY ── */}
        <section className="mb-8">
          <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-6 mb-6">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <h2 className="text-xl font-bold font-mono text-[var(--text-primary)]">
                  {selectedInfo.symbol}
                </h2>
                <span className="text-xs text-[var(--text-muted)] uppercase font-mono">
                  {selectedInfo.name} · {selectedInfo.type}
                </span>
                {priceSource && (
                  <span className="text-[10px] px-2 py-0.5 rounded bg-[var(--mint-subtle)] text-[var(--text-muted)] font-mono">
                    Feed: {priceSource}
                  </span>
                )}
              </div>

              {priceLoading ? (
                <div className="h-12 flex items-center font-mono text-sm text-[var(--text-muted)] animate-pulse">
                  Updating live price...
                </div>
              ) : currentPrice !== null ? (
                <div className="flex items-baseline gap-4">
                  <span className="font-mono text-4xl md:text-5xl font-semibold text-[var(--text-primary)] tracking-tight">
                    ${currentPrice < 10 ? currentPrice.toFixed(4) : currentPrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>
                  {priceChangePct !== null && (
                    <span
                      className={`font-mono text-base font-semibold flex items-center gap-1 ${
                        priceChangePct >= 0 ? 'text-[var(--accent-fresh)]' : 'text-[var(--red)]'
                      }`}
                    >
                      {priceChangePct >= 0 ? <ArrowUpRight size={18} /> : <ArrowDownRight size={18} />}
                      {priceChangePct >= 0 ? '+' : ''}{priceChangePct}%
                    </span>
                  )}
                </div>
              ) : (
                <div className="font-mono text-sm text-[var(--red)]">
                  {priceError || `Live price feed unavailable for ${selectedSymbol}`}
                </div>
              )}
            </div>

            {/* Timeframe selector */}
            <div className="flex items-center gap-1 bg-[var(--surface)] p-1 rounded-lg border border-[var(--border)]">
              {TIMEFRAMES.map((tf) => (
                <button
                  key={tf}
                  onClick={() => setTimeframe(tf)}
                  className={`px-3 py-1 rounded text-xs font-mono font-medium transition-all ${
                    timeframe === tf
                      ? 'bg-[var(--surface-hover)] text-[var(--accent-fresh)] font-semibold shadow-sm'
                      : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  {tf.toUpperCase()}
                </button>
              ))}
              <button
                onClick={() => {
                  fetchSelectedPrice();
                  fetchCandles();
                }}
                className="p-1.5 text-[var(--text-muted)] hover:text-[var(--accent-fresh)] ml-1"
                title="Refresh market data"
              >
                <RefreshCw size={13} />
              </button>
            </div>
          </div>

          {/* ── LARGE UNCLUTTERED CHART ── */}
          <div className="p-4 md:p-6 rounded-xl bg-[var(--surface)] border border-[var(--border)] mb-8">
            <div className="h-[360px] md:h-[440px] w-full relative">
              {chartLoading ? (
                <div className="absolute inset-0 flex items-center justify-center bg-[var(--surface)]/80 z-10">
                  <div className="text-center font-mono text-xs text-[var(--text-muted)]">
                    <Activity size={24} className="animate-spin text-[var(--accent-fresh)] mx-auto mb-2" />
                    Fetching real market candles from exchange...
                  </div>
                </div>
              ) : chartError ? (
                <div className="h-full flex items-center justify-center text-center p-6">
                  <div>
                    <p className="font-mono text-sm text-[var(--text-secondary)] mb-3">{chartError}</p>
                    <button onClick={fetchCandles} className="btn btn-secondary text-xs">
                      Retry Loading Chart
                    </button>
                  </div>
                </div>
              ) : candles.length === 0 ? (
                <div className="h-full flex items-center justify-center font-mono text-xs text-[var(--text-muted)]">
                  No historical candle data returned for this timeframe.
                </div>
              ) : (
                <Line data={chartData} options={chartOptions} />
              )}
            </div>

            {/* Metric Footer */}
            {candles.length > 0 && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6 pt-4 border-t border-[var(--border)] font-mono text-xs">
                <div>
                  <span className="text-[var(--text-muted)] block mb-1">Period High</span>
                  <span className="text-[var(--text-primary)] font-medium">
                    ${highPrice ? (highPrice < 10 ? highPrice.toFixed(4) : highPrice.toLocaleString()) : '—'}
                  </span>
                </div>
                <div>
                  <span className="text-[var(--text-muted)] block mb-1">Period Low</span>
                  <span className="text-[var(--text-primary)] font-medium">
                    ${lowPrice ? (lowPrice < 10 ? lowPrice.toFixed(4) : lowPrice.toLocaleString()) : '—'}
                  </span>
                </div>
                <div>
                  <span className="text-[var(--text-muted)] block mb-1">Candles Sampled</span>
                  <span className="text-[var(--text-primary)] font-medium">
                    {candles.length} bars ({timeframe})
                  </span>
                </div>
                <div>
                  <span className="text-[var(--text-muted)] block mb-1">
                    <TermTooltip term="R:R">Risk / Reward Rule</TermTooltip>
                  </span>
                  <span className="text-[var(--accent-fresh)] font-medium">
                    2 : 1 Strategy Target
                  </span>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* ── SUPPORTED INSTRUMENTS TABLE (REAL ONLY) ── */}
        <section className="mb-16">
          <h3 className="font-display text-2xl text-[var(--text-primary)] mb-4">
            Supported Instruments
          </h3>
          <div className="overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--surface)]">
            <table className="table-editorial">
              <thead>
                <tr>
                  <th>Market</th>
                  <th>Asset Type</th>
                  <th>Execution Feed</th>
                  <th>Live Price</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredInstruments.map((inst) => {
                  const p = marketPrices[inst.symbol];
                  return (
                    <tr
                      key={inst.symbol}
                      onClick={() => setSelectedSymbol(inst.symbol)}
                      className="cursor-pointer"
                    >
                      <td className="font-mono font-medium text-[var(--text-primary)]">
                        {inst.symbol}
                        <span className="block text-xs font-normal text-[var(--text-muted)] font-sans">
                          {inst.name}
                        </span>
                      </td>
                      <td className="uppercase font-mono text-xs text-[var(--text-secondary)]">
                        {inst.type}
                      </td>
                      <td className="font-mono text-xs text-[var(--text-muted)]">
                        {inst.type === 'crypto' ? 'Binance Klines' : 'Dukascopy FX'}
                      </td>
                      <td className="font-mono font-medium">
                        {p !== undefined && p !== null ? (
                          `$${p < 10 ? p.toFixed(4) : p.toLocaleString(undefined, { minimumFractionDigits: 2 })}`
                        ) : inst.symbol === selectedSymbol && currentPrice !== null ? (
                          `$${currentPrice < 10 ? currentPrice.toFixed(4) : currentPrice.toLocaleString(undefined, { minimumFractionDigits: 2 })}`
                        ) : (
                          <span className="text-xs text-[var(--text-muted)]">Click to fetch</span>
                        )}
                      </td>
                      <td>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedSymbol(inst.symbol);
                          }}
                          className="text-xs font-mono text-[var(--accent-fresh)] hover:underline"
                        >
                          Select Chart →
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

      </div>
    </div>
  );
};
