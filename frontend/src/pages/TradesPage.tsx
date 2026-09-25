import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw } from 'lucide-react';
import { supabase } from '../lib/supabase';
import { TermTooltip } from '../components/TermTooltip';
import { EmptyState, OfflineState, LoadingState } from '../components/StatusStates';

export const TradesPage: React.FC = () => {
  const [trades, setTrades] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [filterOutcome, setFilterOutcome] = useState<'ALL' | 'WIN' | 'LOSS'>('ALL');

  const loadTrades = useCallback(async () => {
    try {
      setLoading(true);
      setOffline(false);
      
      const { data, error } = await supabase
        .from('paper_trades')
        .select('*')
        .eq('status', 'CLOSED')
        .order('created_at', { ascending: false })
        .limit(100);
        
      if (error) throw error;
      setTrades(data || []);
      
    } catch (err) {
      console.error("Supabase trades error:", err);
      setOffline(true);
      setTrades([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTrades();
  }, [loadTrades]);

  const filteredTrades = trades.filter((t) => {
    const isWin = t.realized_pnl > 0;
    const outcome = isWin ? 'WIN' : t.realized_pnl < 0 ? 'LOSS' : 'ALL';
    if (filterOutcome === 'ALL') return true;
    return outcome === filterOutcome;
  });

  const totalPnl = trades.reduce((sum, t) => sum + (t.realized_pnl || 0), 0);
  const wins = trades.filter((t) => t.realized_pnl > 0).length;
  const losses = trades.filter((t) => t.realized_pnl < 0).length;
  const winRate = trades.length > 0 ? ((wins / trades.length) * 100).toFixed(1) : null;

  return (
    <div className="page-main">
      <div className="content-container">

        {/* ── HEADER ── */}
        <section className="page-header pt-12 pb-8 border-b border-[var(--border)]">
          <p className="text-meta text-[var(--accent-fresh)] mb-3 font-mono">
            Execution Ledger &amp; Verified Audit Log
          </p>
          <h1 className="font-display text-hero text-[var(--text-primary)] mb-3">
            TRADES.
          </h1>
          <p className="text-sm text-[var(--text-secondary)] max-w-xl">
            Verified execution records from automated bot orders and evaluated probability signals.
          </p>
        </section>

        {offline ? (
          <OfflineState
            title="Trade Database Offline"
            message="Supabase trades table is unreachable or not configured. Verify database credentials in the backend environment."
            onRetry={loadTrades}
          />
        ) : loading ? (
          <LoadingState message="Querying execution ledger..." />
        ) : trades.length === 0 ? (
          <EmptyState
            title="No Trade History Recorded"
            message="No verified trades have been executed or logged in the ledger yet. Once the trading bot initiates positions, real results will appear here."
            actionLabel="View Trading Bot →"
            onAction={() => window.location.href = '/bot'}
          />
        ) : (
          <div className="space-y-8 my-8">

            {/* Stat Strip */}
            <div className="stat-strip">
              <div className="stat-strip-item">
                <span className="text-meta text-[var(--text-muted)] block mb-1">
                  Total Executions
                </span>
                <p className="font-mono text-2xl font-semibold text-[var(--text-primary)]">
                  {trades.length}
                </p>
                <p className="text-xs text-[var(--text-muted)] font-mono mt-1">
                  Historical trades
                </p>
              </div>

              <div className="stat-strip-item">
                <span className="text-meta text-[var(--text-muted)] block mb-1">
                  <TermTooltip term="Win Rate">Win Rate</TermTooltip>
                </span>
                <p className="font-mono text-2xl font-semibold text-[var(--accent-fresh)]">
                  {winRate ? `${winRate}%` : '—'}
                </p>
                <p className="text-xs text-[var(--text-muted)] font-mono mt-1">
                  {wins} wins / {losses} losses
                </p>
              </div>

              <div className="stat-strip-item">
                <span className="text-meta text-[var(--text-muted)] block mb-1">
                  <TermTooltip term="PnL">Net P&amp;L</TermTooltip>
                </span>
                <p className={`font-mono text-2xl font-semibold ${totalPnl >= 0 ? 'text-[var(--accent-fresh)]' : 'text-[var(--red)]'}`}>
                  {totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(2)}
                </p>
                <p className="text-xs text-[var(--text-muted)] font-mono mt-1">
                  Realized cumulative profit
                </p>
              </div>
            </div>

            {/* Table Controls */}
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                {(['ALL', 'WIN', 'LOSS'] as const).map((f) => (
                  <button
                    key={f}
                    onClick={() => setFilterOutcome(f)}
                    className={`px-3 py-1 text-xs font-mono font-medium rounded ${
                      filterOutcome === f
                        ? 'bg-[var(--surface-hover)] text-[var(--accent-fresh)] border border-[var(--border-mid)]'
                        : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                    }`}
                  >
                    {f}
                  </button>
                ))}
              </div>

              <button
                onClick={loadTrades}
                className="text-xs text-[var(--text-muted)] hover:text-[var(--accent-fresh)] flex items-center gap-1 font-mono"
              >
                <RefreshCw size={12} /> Sync Ledger
              </button>
            </div>

            {/* Trades Table */}
            <div className="overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--surface)]">
              <table className="table-editorial">
                <thead>
                  <tr>
                    <th>Date / Time</th>
                    <th>Market</th>
                    <th>Direction</th>
                    <th>Entry</th>
                    <th>Exit</th>
                    <th>Result</th>
                    <th><TermTooltip term="PnL">P&amp;L</TermTooltip></th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTrades.map((t, i) => {
                    const isWin = t.realized_pnl > 0;
                    const isLoss = t.realized_pnl < 0;
                    const isLong = t.direction === 'LONG';
                    const pnlVal = t.realized_pnl || 0;
                    const outcome = isWin ? 'WIN' : isLoss ? 'LOSS' : 'BREAK-EVEN';

                    return (
                      <tr key={t.id || i}>
                        <td className="font-mono text-xs text-[var(--text-muted)]">
                          {t.created_at ? new Date(t.created_at).toLocaleString() : 'Recent'}
                        </td>
                        <td className="font-mono font-medium text-[var(--text-primary)]">
                          {t.symbol || 'BTC / USDT'}
                        </td>
                        <td className="font-mono text-xs">
                          <span className={`px-2 py-0.5 rounded font-semibold ${
                            isLong ? 'bg-[var(--green-subtle)] text-[var(--accent-fresh)]' : 'bg-[var(--red-subtle)] text-[var(--red)]'
                          }`}>
                            {isLong ? 'LONG' : 'SHORT'}
                          </span>
                        </td>
                        <td className="font-mono text-xs text-[var(--text-secondary)]">
                          ${t.entry_price || '—'}
                        </td>
                        <td className="font-mono text-xs text-[var(--text-secondary)]">
                          ${t.stop_loss || '—'}
                        </td>
                        <td className="font-mono text-xs font-semibold">
                          <span className={`px-2 py-0.5 rounded ${
                            isWin ? 'text-[var(--accent-fresh)] bg-[var(--green-subtle)]' : isLoss ? 'text-[var(--red)] bg-[var(--red-subtle)]' : 'text-[var(--text-muted)]'
                          }`}>
                            {outcome}
                          </span>
                        </td>
                        <td className={`font-mono text-xs font-semibold ${pnlVal >= 0 ? 'text-[var(--accent-fresh)]' : 'text-[var(--red)]'}`}>
                          {pnlVal >= 0 ? '+' : ''}${pnlVal.toFixed(2)}
                        </td>
                        <td className="font-mono text-xs text-[var(--text-muted)]">
                          {t.status || 'CLOSED'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

          </div>
        )}

      </div>
    </div>
  );
};
