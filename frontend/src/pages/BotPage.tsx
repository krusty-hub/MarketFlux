import React, { useState, useEffect, useCallback } from 'react';
import {
  Play,
  Pause,
  Square,
  AlertOctagon,
  RefreshCw,
} from 'lucide-react';
import { botApi, type BotStatusData } from '../services/api';
import { LiveConfirmationModal } from '../components/LiveConfirmationModal';
import { useToast } from '../components/Toast';
import { TermTooltip } from '../components/TermTooltip';
import { OfflineState } from '../components/StatusStates';

interface BotPageProps {
  setBotMode?: (mode: 'paper' | 'live') => void;
}

export const BotPage: React.FC<BotPageProps> = ({ setBotMode }) => {
  const { toast } = useToast();

  const [statusData, setStatusData] = useState<BotStatusData | null>(null);
  const [loading, setLoading] = useState(false);
  const [offline, setOffline] = useState(false);
  const [showLiveModal, setShowLiveModal] = useState(false);

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

  const isLive = statusData?.mode === 'live';
  const isOnline = statusData?.status === 'ONLINE';
  const isPaused = statusData?.status === 'PAUSED';
  const isHalted = statusData?.status === 'EMERGENCY_HALTED' || statusData?.is_halted;
  const openPositions = statusData?.open_positions || [];

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

        {/* ── BOT STATUS BANNER (BEGINNER-FIRST MICROCOPY) ── */}
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

            <button
              onClick={loadBotStatus}
              className="text-xs font-mono text-[var(--text-muted)] hover:text-[var(--accent-fresh)] flex items-center gap-1.5"
            >
              <RefreshCw size={12} /> Sync Status
            </button>
          </div>
        </section>

        {/* ── BOT PERFORMANCE STAT STRIP (REAL ONLY) ── */}
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
                {statusData.trades_today} executions today
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

        {/* ── OPEN POSITIONS (REAL ONLY) ── */}
        <section className="my-10">
          <h3 className="font-display text-2xl text-[var(--text-primary)] mb-4">
            Active Market Positions
          </h3>

          {openPositions.length === 0 ? (
            <div className="p-8 text-center rounded-xl border border-[var(--border)] bg-[var(--surface)]">
              <p className="font-mono text-sm text-[var(--text-secondary)] mb-1">
                POSITION: No active positions open.
              </p>
              <p className="text-xs text-[var(--text-muted)]">
                The bot is monitoring market structure for high-probability setups.
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
                  </tr>
                </thead>
                <tbody>
                  {openPositions.map((pos: any) => {
                    const isWin = (pos.unrealized_pnl ?? 0) >= 0;
                    return (
                      <tr key={pos.id}>
                        <td className="font-mono text-xs font-semibold text-[var(--text-primary)]">
                          {pos.id}
                        </td>
                        <td className="font-mono font-medium">
                          {pos.symbol}
                        </td>
                        <td className="font-mono text-xs">
                          <span className={`px-2 py-0.5 rounded font-semibold ${
                            pos.side === 'LONG' ? 'bg-[var(--green-subtle)] text-[var(--accent-fresh)]' : 'bg-[var(--red-subtle)] text-[var(--red)]'
                          }`}>
                            {pos.side}
                          </span>
                        </td>
                        <td className="font-mono text-xs">${pos.entry_price?.toLocaleString()}</td>
                        <td className="font-mono text-xs">${pos.current_price?.toLocaleString()}</td>
                        <td className="font-mono text-xs text-[var(--red)]">${pos.stop_loss?.toLocaleString()}</td>
                        <td className="font-mono text-xs text-[var(--accent-fresh)]">${pos.take_profit?.toLocaleString()}</td>
                        <td className={`font-mono text-xs font-semibold ${isWin ? 'text-[var(--accent-fresh)]' : 'text-[var(--red)]'}`}>
                          {isWin ? '+' : ''}${pos.unrealized_pnl?.toFixed(2)} ({pos.unrealized_pnl_pct}%)
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* ── RISK SETTINGS ROW (EXPLAINED IN PLAIN ENGLISH) ── */}
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

        {/* ── RECENT BOT LOGS (REAL ONLY) ── */}
        <section className="mb-16">
          <p className="text-meta text-[var(--text-muted)] font-mono mb-3">
            Trading Engine Activity Feed
          </p>
          <div className="h-44 overflow-y-auto bg-[var(--bg)] p-4 rounded-xl border border-[var(--border)] font-mono text-xs space-y-1.5">
            {(statusData?.recent_logs || []).map((log: any, idx: number) => (
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
                  {log.text}
                </span>
              </div>
            ))}
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
