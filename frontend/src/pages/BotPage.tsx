import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Play,
  Pause,
  Square,
  AlertOctagon,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  X,
  Wifi,
  WifiOff,
  RotateCcw,
  ArrowUpRight,
  ArrowDownRight,
  Activity,
} from 'lucide-react';
import { botApi, type BotStatusData, type WsMessage, type ExecuteTradeParams } from '../services/api';
import { LiveConfirmationModal } from '../components/LiveConfirmationModal';
import { useToast } from '../components/Toast';
import { TermTooltip } from '../components/TermTooltip';
import { OfflineState } from '../components/StatusStates';
import { supabase } from '../lib/supabase';

interface BotPageProps {
  setBotMode?: (mode: 'paper' | 'live') => void;
}

export const BotPage: React.FC<BotPageProps> = ({ setBotMode }) => {
  const { toast } = useToast();

  const [statusData, setStatusData] = useState<BotStatusData | null>(null);
  const [loading, setLoading] = useState(false);
  const [offline, setOffline] = useState(false);
  const [showLiveModal, setShowLiveModal] = useState(false);
  const [showTradeForm, setShowTradeForm] = useState(false);
  const [closingPositionId, setClosingPositionId] = useState<string | null>(null);
  const [dbOpenPositions, setDbOpenPositions] = useState<any[]>([]);

  // WebSocket state
  const wsRef = useRef<WebSocket | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [livePrices, setLivePrices] = useState<Record<string, number>>({});

  // Trade form state
  const [tradeForm, setTradeForm] = useState<ExecuteTradeParams>({
    symbol: 'BTC/USDT',
    direction: 'LONG',
    notional_usd: 500,
    stop_loss: undefined,
    take_profit: undefined,
  });

  const [riskForm, setRiskForm] = useState({
    max_daily_loss_pct: 4.0,
    max_drawdown_pct: 6.0,
    risk_per_trade_pct: 1.5,
    max_open_positions: 3,
    max_position_size_usd: 2500.0,
    stop_loss_atr: 1.5,
    take_profit_rr: 2.0,
    trading_session: 'ANY',
    consecutive_loss_limit: 3,
  });

  // ── Load Bot Status ──────────────────────────────────────────────────────
  const loadBotStatus = useCallback(async () => {
    try {
      setLoading(true);
      const data = await botApi.getStatus();
      setStatusData(data);
      setOffline(false);
      if (data.risk_config) {
        setRiskForm((prev) => ({ ...prev, ...data.risk_config }));
      }
      setBotMode?.(data.mode);
    } catch {
      setStatusData(null);
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, [setBotMode]);

  useEffect(() => {
    loadBotStatus();
    const interval = setInterval(loadBotStatus, 8000);
    return () => clearInterval(interval);
  }, [loadBotStatus]);

  // ── WebSocket Connection ──────────────────────────────────────────────────
  useEffect(() => {
    const connectWs = () => {
      try {
        const ws = botApi.connectWebSocket(
          undefined, // user_id handled by auth
          (data: WsMessage) => {
            if (data.prices) {
              setLivePrices(data.prices);
            }
            // Update portfolio in real-time from WS
            if (data.portfolio && statusData) {
              setStatusData((prev) =>
                prev
                  ? {
                      ...prev,
                      balance: data.portfolio!.paper_balance,
                      equity: data.portfolio!.equity,
                      today_pnl: data.portfolio!.today_pnl,
                    }
                  : prev
              );
            }
          },
          () => {
            setWsConnected(false);
          },
          () => {
            setWsConnected(false);
            // Auto-reconnect after 5s
            setTimeout(connectWs, 5000);
          }
        );
        ws.onopen = () => setWsConnected(true);
        wsRef.current = ws;
      } catch {
        // WebSocket not available
      }
    };

    connectWs();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Supabase Realtime Open Positions ──────────────────────────────────────
  useEffect(() => {
    const fetchPositions = async () => {
      if (!supabase) return;
      const { data } = await supabase
        .from('paper_trades')
        .select('*')
        .eq('status', 'OPEN');
      if (data) setDbOpenPositions(data);
    };

    fetchPositions();

    if (!supabase) return;
    const channel = supabase
      .channel('custom-open-positions')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'paper_trades', filter: "status=eq.OPEN" },
        (_payload) => {
          fetchPositions();
        }
      )
      .subscribe();

    return () => {
      if (supabase) {
        supabase.removeChannel(channel);
      }
    };
  }, []);

  // ── Bot Controls ──────────────────────────────────────────────────────────
  const handleControl = async (action: 'START' | 'PAUSE' | 'STOP' | 'EMERGENCY_KILL') => {
    try {
      setLoading(true);
      const updated = await botApi.setControl(action);
      setStatusData(updated);
      if (action === 'EMERGENCY_KILL') toast('Emergency halt activated! All activity paused.', 'error');
      if (action === 'START')  toast('Trading bot started successfully.', 'success');
      if (action === 'PAUSE')  toast('Trading bot paused.', 'info');
      if (action === 'STOP')   toast('Trading bot stopped.', 'info');
    } catch (err: any) {
      toast(err?.response?.data?.detail || err?.message || 'Control action failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleModeToggle = (targetMode: 'paper' | 'live') => {
    if (targetMode === 'live') {
      setShowLiveModal(true);
    } else {
      botApi.setMode('paper').then((d: any) => {
        setStatusData(d);
        setBotMode?.('paper');
        toast('Switched to Paper Trading (Simulation).', 'info');
      }).catch((err: any) => toast(err?.message || 'Mode switch failed', 'error'));
    }
  };

  const handleConfirmLive = async (code: string) => {
    try {
      const updated = await botApi.setMode('live', code);
      setStatusData(updated);
      setBotMode?.('live');
      toast('Live trading mode activated.', 'success');
    } catch (err: any) {
      toast(err?.response?.data?.detail || err?.message || 'Live mode activation rejected', 'error');
    }
  };

  const handleSaveRisk = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setLoading(true);
      const updated = await botApi.updateRisk(riskForm);
      setStatusData(updated);
      toast('Risk parameters updated successfully.', 'success');
    } catch (err: any) {
      toast(err?.message || 'Failed to save risk parameters', 'error');
    } finally {
      setLoading(false);
    }
  };

  // ── Trade Execution ───────────────────────────────────────────────────────
  const handleExecuteTrade = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setLoading(true);
      const result = await botApi.executeTrade(tradeForm);
      if (result.executed) {
        toast(`Trade executed! ${tradeForm.direction} ${tradeForm.symbol}`, 'success');
        setShowTradeForm(false);
        loadBotStatus();
      } else {
        toast(result.reason || 'Trade rejected by risk engine.', 'error');
      }
    } catch (err: any) {
      toast(err?.response?.data?.detail || err?.message || 'Trade execution failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  // ── Close Position ────────────────────────────────────────────────────────
  const handleClosePosition = async (fullId: string) => {
    try {
      setClosingPositionId(fullId);
      const result = await botApi.closePosition(fullId);
      if (result.closed) {
        const pnl = result.realized_pnl ?? 0;
        toast(
          `Position closed. P&L: $${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}`,
          pnl >= 0 ? 'success' : 'error'
        );
        loadBotStatus();
      }
    } catch (err: any) {
      toast(err?.response?.data?.detail || err?.message || 'Failed to close position', 'error');
    } finally {
      setClosingPositionId(null);
    }
  };

  // ── Reset Portfolio ───────────────────────────────────────────────────────
  const handleResetPortfolio = async () => {
    if (!confirm('Reset paper balance to $10,000? This will close all open positions.')) return;
    try {
      await botApi.resetPortfolio();
      toast('Paper balance reset to $10,000.00', 'success');
      loadBotStatus();
    } catch (err: any) {
      toast(err?.response?.data?.detail || err?.message || 'Reset failed', 'error');
    }
  };

  const isLive = statusData?.mode === 'live';
  const isOnline = statusData?.status === 'ONLINE';
  const isPaused = statusData?.status === 'PAUSED';
  const isHalted = statusData?.status === 'EMERGENCY_HALTED' || statusData?.is_halted;
  
  // Combine dbOpenPositions from Supabase and any mock ones from statusData if needed.
  // Merge both arrays so that regular bot trades and AI trades both show up simultaneously.
  const openPositions = [...(statusData?.open_positions || []), ...dbOpenPositions];

  // Format BTC price for the trade form placeholder
  const btcPrice = livePrices['BTCUSDT'] || statusData?.live_prices?.BTCUSDT;

  return (
    <div className="page-main">
      <div className="content-container">

        {/* ── HEADER ── */}
        <section className="page-header pt-12 pb-8 border-b border-[var(--border)]">
          <p className="text-meta text-[var(--accent-fresh)] mb-3 font-mono">
            Algorithmic Execution Engine
          </p>
          <h1 className="font-display text-hero text-[var(--text-primary)] mb-3">
            TRADING BOT.
          </h1>
          <p className="text-sm text-[var(--text-secondary)] max-w-xl">
            Simulate or execute automated orders using institutional Smart Money and ML probability triggers.
          </p>
        </section>

        {offline && (
          <OfflineState
            title="Trading Engine Offline"
            message="The trading engine isn't connected. No simulated or live trades are currently being executed."
            onRetry={loadBotStatus}
          />
        )}

        {/* ── BOT STATUS BANNER ── */}
        <section className="my-8 p-6 md:p-8 rounded-xl bg-[var(--surface)] border border-[var(--border)]">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 pb-6 border-b border-[var(--border)]">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <span className="font-mono text-xs uppercase text-[var(--text-muted)]">
                  Mode:
                </span>
                <span className={`badge ${isLive ? 'badge-warning' : 'badge-connected'}`}>
                  ● {isLive ? 'Live Trading' : 'Paper Mode'}
                </span>
                <span className={`badge ${isOnline ? 'badge-connected' : isPaused ? 'badge-warning' : isHalted ? 'badge-offline' : 'badge-neutral'}`}>
                  {statusData?.status || 'OFFLINE'}
                </span>
                {/* WebSocket indicator */}
                <span className={`flex items-center gap-1 text-[10px] font-mono ${wsConnected ? 'text-[var(--accent-fresh)]' : 'text-[var(--text-muted)]'}`}>
                  {wsConnected ? <Wifi size={10} /> : <WifiOff size={10} />}
                  {wsConnected ? 'LIVE' : 'WS OFF'}
                </span>
              </div>

              <h2 className="font-display text-3xl text-[var(--text-primary)]">
                {isLive ? 'Live Trading Active' : 'Paper Trading (Simulation)'}
              </h2>

              <p className="text-sm text-[var(--text-secondary)] mt-1 max-w-xl leading-relaxed">
                {isLive
                  ? 'Real orders are enabled. Trades will be executed with live exchange capital.'
                  : 'The bot is currently simulating trades with virtual funds. No real money is being used.'}
              </p>
            </div>

            {/* Mode Switcher */}
            <div className="flex items-center gap-2 bg-[var(--bg)] p-1.5 rounded-lg border border-[var(--border)]">
              <button
                onClick={() => handleModeToggle('paper')}
                className={`px-3 py-1.5 rounded text-xs font-mono font-medium transition-all ${
                  !isLive
                    ? 'bg-[var(--accent-fresh)] text-[var(--btn-text)] font-semibold shadow-sm'
                    : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                }`}
              >
                Paper Mode
              </button>
              <button
                onClick={() => handleModeToggle('live')}
                className={`px-3 py-1.5 rounded text-xs font-mono font-medium transition-all ${
                  isLive
                    ? 'bg-[var(--amber)] text-white dark:text-[#07110D] font-semibold shadow-sm'
                    : 'text-[var(--text-muted)] hover:text-[var(--red)]'
                }`}
              >
                Live Mode
              </button>
            </div>
          </div>

          {/* Controls Strip */}
          <div className="pt-6 flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap items-center gap-3">
              {!isOnline ? (
                <button
                  onClick={() => handleControl('START')}
                  disabled={loading || offline}
                  className="btn btn-primary text-xs"
                >
                  <Play size={13} /> Start Trading Bot
                </button>
              ) : (
                <button
                  onClick={() => handleControl('PAUSE')}
                  disabled={loading || offline}
                  className="btn btn-secondary text-xs"
                >
                  <Pause size={13} /> Pause Bot
                </button>
              )}

              <button
                onClick={() => handleControl('STOP')}
                disabled={loading || offline}
                className="btn btn-secondary text-xs"
              >
                <Square size={13} /> Stop Bot
              </button>

              <button
                onClick={() => handleControl('EMERGENCY_KILL')}
                disabled={loading || offline}
                className="btn btn-danger text-xs"
                title="Immediately halt all execution and open orders"
              >
                <AlertOctagon size={13} /> Emergency Halt
              </button>
            </div>

            <div className="flex items-center gap-4">
              <button
                onClick={handleResetPortfolio}
                className="text-xs font-mono text-[var(--text-muted)] hover:text-[var(--amber)] flex items-center gap-1.5"
                title="Reset paper balance to $10,000"
              >
                <RotateCcw size={12} /> Reset Balance
              </button>
              <button
                onClick={loadBotStatus}
                className="text-xs font-mono text-[var(--text-muted)] hover:text-[var(--accent-fresh)] flex items-center gap-1.5"
              >
                <RefreshCw size={12} /> Sync Status
              </button>
            </div>
          </div>
        </section>

        {/* ── LIVE PRICES BAR ── */}
        {Object.keys(livePrices).length > 0 && (
          <section className="my-4 px-6 py-3 rounded-xl bg-[var(--surface)] border border-[var(--border)] flex flex-wrap items-center gap-6">
            <span className="text-[10px] font-mono text-[var(--text-muted)] uppercase flex items-center gap-1.5">
              <Activity size={10} className="text-[var(--accent-fresh)]" /> Live Prices
            </span>
            {Object.entries(livePrices).map(([symbol, price]) => (
              <div key={symbol} className="flex items-center gap-2">
                <span className="font-mono text-xs text-[var(--text-secondary)]">{symbol}</span>
                <span className="font-mono text-xs font-semibold text-[var(--text-primary)]">
                  ${price.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </span>
              </div>
            ))}
          </section>
        )}

        {/* ── BOT PERFORMANCE STAT STRIP ── */}
        {statusData && (
          <section className="stat-strip my-8">
            <div className="stat-strip-item">
              <span className="text-meta text-[var(--text-muted)] block mb-1">
                Portfolio Balance
              </span>
              <p className="font-mono text-2xl font-semibold text-[var(--text-primary)]">
                ${statusData.balance?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </p>
              <p className="text-xs text-[var(--text-secondary)] font-mono mt-1">
                Equity: ${statusData.equity?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </p>
            </div>

            <div className="stat-strip-item">
              <span className="text-meta text-[var(--text-muted)] block mb-1">
                <TermTooltip term="PnL">Today's P&amp;L</TermTooltip>
              </span>
              <p className={`font-mono text-2xl font-semibold ${(statusData.today_pnl ?? 0) >= 0 ? 'text-[var(--accent-fresh)]' : 'text-[var(--red)]'}`}>
                {(statusData.today_pnl ?? 0) >= 0 ? '+' : ''}${statusData.today_pnl?.toFixed(2)}
              </p>
              <p className="text-xs text-[var(--text-secondary)] font-mono mt-1">
                {(statusData.today_pnl_pct ?? 0) >= 0 ? '+' : ''}{statusData.today_pnl_pct}% today
              </p>
            </div>

            <div className="stat-strip-item">
              <span className="text-meta text-[var(--text-muted)] block mb-1">
                <TermTooltip term="Win Rate">Win Rate</TermTooltip>
              </span>
              <p className="font-mono text-2xl font-semibold text-[var(--accent-fresh)]">
                {statusData.win_rate}%
              </p>
              <p className="text-xs text-[var(--text-secondary)] font-mono mt-1">
                {statusData.trades_today} executions total
              </p>
            </div>

            <div className="stat-strip-item">
              <span className="text-meta text-[var(--text-muted)] block mb-1">
                <TermTooltip term="Drawdown">Max Drawdown</TermTooltip>
              </span>
              <p className="font-mono text-2xl font-semibold text-[var(--text-secondary)]">
                {statusData.drawdown}%
              </p>
              <p className="text-xs text-[var(--text-muted)] font-mono mt-1">
                Risk boundary: {riskForm.max_drawdown_pct}%
              </p>
            </div>
          </section>
        )}

        {/* ── EXECUTE TRADE BUTTON + FORM ── */}
        <section className="my-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-display text-2xl text-[var(--text-primary)]">
              Active Market Positions
            </h3>
            <button
              onClick={() => setShowTradeForm(!showTradeForm)}
              disabled={loading || offline || isHalted}
              className="btn btn-primary text-xs"
            >
              {showTradeForm ? <X size={13} /> : <TrendingUp size={13} />}
              {showTradeForm ? 'Cancel' : 'New Paper Trade'}
            </button>
          </div>

          {/* Trade execution form */}
          {showTradeForm && (
            <form
              onSubmit={handleExecuteTrade}
              className="p-6 mb-6 rounded-xl bg-[var(--surface)] border border-[var(--accent-fresh)] border-opacity-30 space-y-4"
            >
              <p className="text-meta text-[var(--accent-fresh)] font-mono mb-2">
                Execute Paper Trade
              </p>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-meta text-[var(--text-muted)] font-mono mb-1">Symbol</label>
                  <select
                    value={tradeForm.symbol}
                    onChange={(e) => setTradeForm({ ...tradeForm, symbol: e.target.value })}
                    className="input-editorial font-mono w-full"
                  >
                    <option value="BTC/USDT">BTC/USDT</option>
                    <option value="ETH/USDT">ETH/USDT</option>
                    <option value="BNB/USDT">BNB/USDT</option>
                    <option value="SOL/USDT">SOL/USDT</option>
                    <option value="ADA/USDT">ADA/USDT</option>
                    <option value="XRP/USDT">XRP/USDT</option>
                    <option value="DOGE/USDT">DOGE/USDT</option>
                    <option value="LINK/USDT">LINK/USDT</option>
                  </select>
                </div>

                <div>
                  <label className="block text-meta text-[var(--text-muted)] font-mono mb-1">Direction</label>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setTradeForm({ ...tradeForm, direction: 'LONG' })}
                      className={`flex-1 py-2 rounded text-xs font-mono font-semibold transition-all flex items-center justify-center gap-1.5 ${
                        tradeForm.direction === 'LONG'
                          ? 'bg-[var(--accent-fresh)] text-[var(--btn-text)] shadow-sm'
                          : 'bg-[var(--bg)] text-[var(--text-muted)] border border-[var(--border)]'
                      }`}
                    >
                      <ArrowUpRight size={12} /> LONG
                    </button>
                    <button
                      type="button"
                      onClick={() => setTradeForm({ ...tradeForm, direction: 'SHORT' })}
                      className={`flex-1 py-2 rounded text-xs font-mono font-semibold transition-all flex items-center justify-center gap-1.5 ${
                        tradeForm.direction === 'SHORT'
                          ? 'bg-[var(--red)] text-white shadow-sm'
                          : 'bg-[var(--bg)] text-[var(--text-muted)] border border-[var(--border)]'
                      }`}
                    >
                      <ArrowDownRight size={12} /> SHORT
                    </button>
                  </div>
                </div>

                <div>
                  <label className="block text-meta text-[var(--text-muted)] font-mono mb-1">
                    Position Size (USD)
                  </label>
                  <input
                    type="number"
                    step="50"
                    value={tradeForm.notional_usd || ''}
                    onChange={(e) => setTradeForm({ ...tradeForm, notional_usd: parseFloat(e.target.value) || undefined })}
                    placeholder="e.g. 500"
                    className="input-editorial font-mono"
                  />
                </div>

                <div>
                  <label className="block text-meta text-[var(--text-muted)] font-mono mb-1">
                    Stop Loss Price
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={tradeForm.stop_loss || ''}
                    onChange={(e) => setTradeForm({ ...tradeForm, stop_loss: parseFloat(e.target.value) || undefined })}
                    placeholder={btcPrice ? `e.g. ${(btcPrice * 0.985).toFixed(0)}` : 'Optional'}
                    className="input-editorial font-mono"
                  />
                </div>

                <div>
                  <label className="block text-meta text-[var(--text-muted)] font-mono mb-1">
                    Take Profit Price
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={tradeForm.take_profit || ''}
                    onChange={(e) => setTradeForm({ ...tradeForm, take_profit: parseFloat(e.target.value) || undefined })}
                    placeholder={btcPrice ? `e.g. ${(btcPrice * 1.03).toFixed(0)}` : 'Optional'}
                    className="input-editorial font-mono"
                  />
                </div>

                <div className="flex items-end">
                  <button
                    type="submit"
                    disabled={loading || !tradeForm.notional_usd}
                    className={`btn w-full text-xs font-semibold ${
                      tradeForm.direction === 'LONG' ? 'btn-primary' : 'btn-danger'
                    }`}
                  >
                    {tradeForm.direction === 'LONG' ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
                    Execute {tradeForm.direction} {tradeForm.symbol}
                  </button>
                </div>
              </div>

              {btcPrice && (
                <p className="text-[11px] text-[var(--text-muted)] font-mono">
                  Current {tradeForm.symbol.replace('/', '')} price: ${btcPrice.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                  {' '}(entry at market price)
                </p>
              )}
            </form>
          )}

          {/* ── POSITIONS TABLE ── */}
          {openPositions.length === 0 ? (
            <div className="p-8 text-center rounded-xl border border-[var(--border)] bg-[var(--surface)]">
              <p className="font-mono text-sm text-[var(--text-secondary)] mb-1">
                POSITION: No active positions open.
              </p>
              <p className="text-xs text-[var(--text-muted)]">
                {isOnline
                  ? 'Use the "New Paper Trade" button above, or wait for the bot to detect a high-probability setup.'
                  : 'The bot is monitoring market structure for high-probability setups.'}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--surface)]">
              <table className="table-editorial">
                <thead>
                  <tr>
                    <th>Position ID</th>
                    <th>Market</th>
                    <th>Direction</th>
                    <th>Entry Price</th>
                    <th>Current Price</th>
                    <th><TermTooltip term="SL">Stop Loss</TermTooltip></th>
                    <th><TermTooltip term="TP">Take Profit</TermTooltip></th>
                    <th>Unrealized P&amp;L</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {openPositions.map((pos: any) => {
                    const symbolKey = pos.symbol?.replace('/', '');
                    const currentPrice = livePrices[symbolKey] || pos.current_price || pos.entry_price;
                    const direction = (pos.side || pos.direction || 'LONG').toUpperCase();
                    const size = pos.size || pos.position_size || 0;
                    
                    let computedPnl = pos.unrealized_pnl;
                    let computedPnlPct = pos.unrealized_pnl_pct;
                    
                    if (computedPnl === undefined) {
                        if (direction === 'LONG' || direction === 'BUY') {
                            computedPnl = (currentPrice - pos.entry_price) * size;
                        } else {
                            computedPnl = (pos.entry_price - currentPrice) * size;
                        }
                        const notional = pos.entry_price * size;
                        computedPnlPct = notional > 0 ? (computedPnl / notional) * 100 : 0;
                    }
                    
                    const isWin = (computedPnl ?? 0) >= 0;

                    return (
                      <tr key={pos.id || pos.full_id}>
                        <td className="font-mono text-xs font-semibold text-[var(--text-primary)]">
                          {pos.id}
                        </td>
                        <td className="font-mono font-medium">
                          {pos.symbol}
                        </td>
                        <td className="font-mono text-xs">
                          <span className={`px-2 py-0.5 rounded font-semibold ${
                            (pos.side || pos.direction) === 'LONG' ? 'bg-[var(--green-subtle)] text-[var(--accent-fresh)]' : 'bg-[var(--red-subtle)] text-[var(--red)]'
                          }`}>
                            {pos.side || pos.direction}
                          </span>
                        </td>
                        <td className="font-mono text-xs">${pos.entry_price?.toLocaleString()}</td>
                        <td className="font-mono text-xs">
                          ${currentPrice?.toLocaleString()}
                        </td>
                        <td className="font-mono text-xs text-[var(--red)]">
                          {pos.stop_loss ? `$${pos.stop_loss?.toLocaleString()}` : '—'}
                        </td>
                        <td className="font-mono text-xs text-[var(--accent-fresh)]">
                          {pos.take_profit ? `$${pos.take_profit?.toLocaleString()}` : '—'}
                        </td>
                        <td className={`font-mono text-xs font-semibold ${isWin ? 'text-[var(--accent-fresh)]' : 'text-[var(--red)]'}`}>
                          {isWin ? '+' : ''}${computedPnl?.toFixed(2)} ({computedPnlPct?.toFixed(2)}%)
                        </td>
                        <td>
                          <button
                            onClick={() => handleClosePosition(pos.full_id || pos.id)}
                            disabled={closingPositionId === (pos.full_id || pos.id)}
                            className="btn btn-secondary text-[10px] py-1 px-2"
                            title="Close this position at market price"
                          >
                            <X size={10} /> Close
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* ── RISK SETTINGS ROW ── */}
        <section className="my-12 p-8 rounded-xl bg-[var(--surface)] border border-[var(--border)]">
          <h3 className="font-display text-2xl text-[var(--text-primary)] mb-2">
            Risk &amp; Execution Safeguards
          </h3>
          <p className="text-sm text-[var(--text-secondary)] mb-6 leading-relaxed max-w-xl">
            Configure how the bot protects your account. Clear risk caps prevent unexpected losses.
          </p>

          <form onSubmit={handleSaveRisk} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <label className="block text-meta text-[var(--text-muted)] font-mono mb-2">
                  <TermTooltip term="R:R">Risk Per Trade (%)</TermTooltip>
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={riskForm.risk_per_trade_pct}
                  onChange={(e) => setRiskForm({ ...riskForm, risk_per_trade_pct: parseFloat(e.target.value) })}
                  className="input-editorial font-mono"
                />
                <p className="text-[11px] text-[var(--text-secondary)] mt-1.5">
                  Percentage of account equity risked on each trade.
                </p>
              </div>

              <div>
                <label className="block text-meta text-[var(--text-muted)] font-mono mb-2">
                  Max Daily Loss Cap (%)
                </label>
                <input
                  type="number"
                  step="0.5"
                  value={riskForm.max_daily_loss_pct}
                  onChange={(e) => setRiskForm({ ...riskForm, max_daily_loss_pct: parseFloat(e.target.value) })}
                  className="input-editorial font-mono"
                />
                <p className="text-[11px] text-[var(--text-secondary)] mt-1.5">
                  Automatically halts trading if today's loss reaches this threshold.
                </p>
              </div>

              <div>
                <label className="block text-meta text-[var(--text-muted)] font-mono mb-2">
                  <TermTooltip term="Drawdown">Max Drawdown Limit (%)</TermTooltip>
                </label>
                <input
                  type="number"
                  step="0.5"
                  value={riskForm.max_drawdown_pct}
                  onChange={(e) => setRiskForm({ ...riskForm, max_drawdown_pct: parseFloat(e.target.value) })}
                  className="input-editorial font-mono"
                />
                <p className="text-[11px] text-[var(--text-secondary)] mt-1.5">
                  Maximum cumulative portfolio drop allowed before permanent shutdown.
                </p>
              </div>

              <div>
                <label className="block text-meta text-[var(--text-muted)] font-mono mb-2">
                  <TermTooltip term="TP">Target Risk / Reward</TermTooltip>
                </label>
                <input
                  type="number"
                  step="0.5"
                  value={riskForm.take_profit_rr}
                  onChange={(e) => setRiskForm({ ...riskForm, take_profit_rr: parseFloat(e.target.value) })}
                  className="input-editorial font-mono"
                />
                <p className="text-[11px] text-[var(--text-secondary)] mt-1.5">
                  Target 2.0x reward for every 1.0x risked.
                </p>
              </div>

              <div>
                <label className="block text-meta text-[var(--text-muted)] font-mono mb-2">
                  <TermTooltip term="ATR">Stop Loss ATR Multiple</TermTooltip>
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={riskForm.stop_loss_atr}
                  onChange={(e) => setRiskForm({ ...riskForm, stop_loss_atr: parseFloat(e.target.value) })}
                  className="input-editorial font-mono"
                />
                <p className="text-[11px] text-[var(--text-secondary)] mt-1.5">
                  Dynamic stop distance adjusted to market volatility.
                </p>
              </div>

              <div>
                <label className="block text-meta text-[var(--text-muted)] font-mono mb-2">
                  Max Open Concurrent Positions
                </label>
                <input
                  type="number"
                  step="1"
                  value={riskForm.max_open_positions}
                  onChange={(e) => setRiskForm({ ...riskForm, max_open_positions: parseInt(e.target.value) })}
                  className="input-editorial font-mono"
                />
                <p className="text-[11px] text-[var(--text-secondary)] mt-1.5">
                  Caps total active exposure across all symbols.
                </p>
              </div>
            </div>

            <div className="pt-4 border-t border-[var(--border)] flex justify-end">
              <button
                type="submit"
                disabled={loading || offline}
                className="btn btn-primary text-xs"
              >
                Save Risk Parameters
              </button>
            </div>
          </form>
        </section>

        {/* ── RECENT BOT LOGS ── */}
        <section className="mb-16">
          <p className="text-meta text-[var(--text-muted)] font-mono mb-3">
            Trading Engine Activity Feed
          </p>
          <div className="h-44 overflow-y-auto bg-[var(--bg)] p-4 rounded-xl border border-[var(--border)] font-mono text-xs space-y-1.5">
            {(statusData?.recent_logs || []).length === 0 ? (
              <div className="text-[var(--text-muted)] text-center py-4">
                No activity yet. Start the bot or execute a trade to see logs here.
              </div>
            ) : (
              (statusData?.recent_logs || []).map((log: any, idx: number) => (
                <div key={idx} className="flex items-start gap-3">
                  <span className="text-[var(--text-muted)] select-none">[{log.time}]</span>
                  <span
                    className={
                      log.level === 'SUCCESS'
                        ? 'text-[var(--accent-fresh)] font-semibold'
                        : log.level === 'WARN'
                        ? 'text-[var(--amber)]'
                        : log.level === 'ERROR'
                        ? 'text-[var(--red)] font-semibold'
                        : 'text-[var(--text-primary)]'
                    }
                  >
                    {log.text || log.message}
                  </span>
                </div>
              ))
            )}
          </div>
        </section>

        {/* Live confirmation modal */}
        <LiveConfirmationModal
          isOpen={showLiveModal}
          onClose={() => setShowLiveModal(false)}
          onConfirm={handleConfirmLive}
        />

      </div>
    </div>
  );
};
