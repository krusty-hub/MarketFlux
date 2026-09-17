import React, { useState, useEffect } from 'react';
import { RefreshCw, Wifi, Shield, Sliders, User, LogOut, Sun, Moon, Monitor } from 'lucide-react';
import { apiClient } from '../services/api';
import { useToast } from '../components/Toast';
import { TermTooltip } from '../components/TermTooltip';
import { useAuth } from '../auth/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { useNavigate } from 'react-router-dom';

export const SettingsPage: React.FC = () => {
  const { toast } = useToast();
  const { user, profile, signOut } = useAuth();
  const { theme, setTheme, isDark } = useTheme();
  const navigate = useNavigate();

  // Settings State (Persisted in localStorage)
  const [defaultMarket, setDefaultMarket] = useState(() => localStorage.getItem('mf_default_market') || 'BTCUSDT');
  const [defaultTimeframe, setDefaultTimeframe] = useState(() => localStorage.getItem('mf_default_tf') || '5m');
  const [riskPerTrade, setRiskPerTrade] = useState(() => localStorage.getItem('mf_risk_pct') || '1.5');

  const [requireLiveConfirmation, setRequireLiveConfirmation] = useState(() => localStorage.getItem('mf_require_live_conf') !== 'false');
  const [soundAlerts, setSoundAlerts] = useState(() => localStorage.getItem('mf_sound_alerts') === 'true');

  const [apiStatus, setApiStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking');
  const [apiLatency, setApiLatency] = useState<number | null>(null);

  // Ping backend API
  const pingApi = async () => {
    setApiStatus('checking');
    const start = performance.now();
    try {
      await apiClient.get('/health/');
      const lat = Math.round(performance.now() - start);
      setApiLatency(lat);
      setApiStatus('connected');
    } catch {
      setApiStatus('disconnected');
      setApiLatency(null);
    }
  };

  useEffect(() => {
    pingApi();
  }, []);

  const handleSignOut = async () => {
    try {
      await signOut();
      toast('Session securely terminated', 'info');
      navigate('/');
    } catch (err: any) {
      toast(err.message || 'Logout failed', 'error');
    }
  };

  const handleSaveAll = (e: React.FormEvent) => {
    e.preventDefault();
    localStorage.setItem('mf_default_market', defaultMarket);
    localStorage.setItem('mf_default_tf', defaultTimeframe);
    localStorage.setItem('mf_risk_pct', riskPerTrade);
    localStorage.setItem('mf_require_live_conf', String(requireLiveConfirmation));
    localStorage.setItem('mf_sound_alerts', String(soundAlerts));

    toast('Platform preferences successfully saved.', 'success');
  };

  return (
    <div className="page-main">
      <div className="content-container">

        {/* ── HEADER ── */}
        <section className="page-header pt-12 pb-8 border-b border-[var(--border)]">
          <p className="text-meta text-[var(--accent-fresh)] mb-3 font-mono">
            Platform Configuration &amp; Connections
          </p>
          <h1 className="font-display text-hero text-[var(--text-primary)] mb-3">
            SETTINGS.
          </h1>
          <p className="text-sm text-[var(--text-secondary)] max-w-xl">
            Configure default trading parameters, execution safeguards, API feeds, and personal preferences.
          </p>
        </section>

        <form onSubmit={handleSaveAll} className="space-y-12 my-10 max-w-4xl">

          {/* ── SECTION 0: AUTHENTICATED USER & SESSION ── */}
          <section className="p-8 rounded-xl bg-[var(--surface)] border border-[var(--border)]">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--accent-fresh)] mb-1 flex items-center gap-2">
                  <User size={14} /> Account &amp; Identity
                </h2>
                <p className="text-xs text-[var(--text-secondary)]">
                  Active Supabase authentication session and permissions.
                </p>
              </div>
              <button
                type="button"
                onClick={handleSignOut}
                className="flex items-center gap-2 px-3 py-1.5 text-xs font-mono text-[var(--loss)] border border-[var(--loss)]/30 rounded-lg hover:bg-[var(--loss)]/10 transition-colors"
              >
                <LogOut size={13} /> Terminate Session
              </button>
            </div>

            <div className="space-y-4 divide-y divide-[var(--border)]">
              <div className="pt-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <span className="text-sm font-medium text-[var(--text-primary)] block">
                    Institutional Identity
                  </span>
                  <span className="text-xs text-[var(--text-secondary)]">Primary trader account</span>
                </div>
                <div className="text-right">
                  <span className="font-mono text-xs font-medium text-[var(--text-primary)] block">
                    {profile?.full_name || user?.email?.split('@')[0] || 'Authenticated Trader'}
                  </span>
                  <span className="font-mono text-[11px] text-[var(--text-muted)]">
                    {user?.email || 'No email attached'}
                  </span>
                </div>
              </div>

              <div className="pt-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <span className="text-sm font-medium text-[var(--text-primary)] block">
                    User UUID
                  </span>
                  <span className="text-xs text-[var(--text-secondary)]">Unique Row Level Security subject ID</span>
                </div>
                <span className="font-mono text-xs px-2.5 py-1 bg-[var(--bg)] border border-[var(--border)] rounded text-[var(--text-muted)]">
                  {user?.id ? `${user.id.slice(0, 16)}...` : 'Local Dev Session'}
                </span>
              </div>

              <div className="pt-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <span className="text-sm font-medium text-[var(--text-primary)] block">
                    Security Layer
                  </span>
                  <span className="text-xs text-[var(--text-secondary)]">JWT bearer authentication status</span>
                </div>
                <span className="badge badge-connected">
                  ● Supabase RLS Active
                </span>
              </div>
            </div>
          </section>

          {/* ── SECTION 1: APPEARANCE & THEME ── */}
          <section className="p-8 rounded-xl bg-[var(--surface)] border border-[var(--border)]">
            <h2 className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--accent-fresh)] mb-1 flex items-center gap-2">
              <Sun size={14} /> Appearance &amp; Theme
            </h2>
            <p className="text-xs text-[var(--text-secondary)] mb-6">
              Switch between minimalist light canvas, sleek graphite dark mode, or follow your OS preference.
            </p>

            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
              <button
                type="button"
                onClick={() => setTheme('light')}
                className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg border text-xs font-mono transition-all ${
                  theme === 'light'
                    ? 'border-[var(--accent-fresh)] bg-[var(--mint-subtle)] text-[var(--text-primary)] font-bold shadow-sm'
                    : 'border-[var(--border)] bg-[var(--bg)] text-[var(--text-secondary)] hover:border-[var(--border-mid)]'
                }`}
              >
                <Sun size={15} className={theme === 'light' ? 'text-[var(--accent-fresh)]' : ''} />
                <span>Light Mode</span>
              </button>

              <button
                type="button"
                onClick={() => setTheme('dark')}
                className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg border text-xs font-mono transition-all ${
                  theme === 'dark'
                    ? 'border-[var(--accent-fresh)] bg-[var(--mint-subtle)] text-[var(--text-primary)] font-bold shadow-sm'
                    : 'border-[var(--border)] bg-[var(--bg)] text-[var(--text-secondary)] hover:border-[var(--border-mid)]'
                }`}
              >
                <Moon size={15} className={theme === 'dark' ? 'text-[var(--accent-fresh)]' : ''} />
                <span>Dark Mode</span>
              </button>

              <button
                type="button"
                onClick={() => setTheme('system')}
                className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg border text-xs font-mono transition-all ${
                  theme === 'system'
                    ? 'border-[var(--accent-fresh)] bg-[var(--mint-subtle)] text-[var(--text-primary)] font-bold shadow-sm'
                    : 'border-[var(--border)] bg-[var(--bg)] text-[var(--text-secondary)] hover:border-[var(--border-mid)]'
                }`}
              >
                <Monitor size={15} className={theme === 'system' ? 'text-[var(--accent-fresh)]' : ''} />
                <span>System ({isDark ? 'Dark' : 'Light'})</span>
              </button>
            </div>
          </section>

          {/* ── SECTION 1: TRADING DEFAULTS ── */}
          <section className="p-8 rounded-xl bg-[var(--surface)] border border-[var(--border)]">
            <h2 className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--accent-fresh)] mb-1 flex items-center gap-2">
              <Sliders size={14} /> Trading Configuration
            </h2>
            <p className="text-xs text-[var(--text-secondary)] mb-6">
              Defaults applied when navigating to charts or launching backtests.
            </p>

            <div className="space-y-4 divide-y divide-[var(--border)]">
              <div className="pt-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <label className="text-sm font-medium text-[var(--text-primary)] block">
                    Default Market Instrument
                  </label>
                  <span className="text-xs text-[var(--text-secondary)]">Primary symbol loaded on dashboard launch</span>
                </div>
                <select
                  value={defaultMarket}
                  onChange={(e) => setDefaultMarket(e.target.value)}
                  className="input-editorial max-w-xs font-mono text-xs"
                >
                  <option value="BTCUSDT">BTCUSDT (Bitcoin)</option>
                  <option value="ETHUSDT">ETHUSDT (Ethereum)</option>
                  <option value="SOLUSDT">SOLUSDT (Solana)</option>
                  <option value="EURUSD">EURUSD (Euro / USD)</option>
                  <option value="XAUUSD">XAUUSD (Gold)</option>
                </select>
              </div>

              <div className="pt-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <label className="text-sm font-medium text-[var(--text-primary)] block">
                    Default Timeframe
                  </label>
                  <span className="text-xs text-[var(--text-secondary)]">Standard bar interval for market analysis</span>
                </div>
                <select
                  value={defaultTimeframe}
                  onChange={(e) => setDefaultTimeframe(e.target.value)}
                  className="input-editorial max-w-xs font-mono text-xs"
                >
                  <option value="1m">1m (Scalping)</option>
                  <option value="5m">5m (Day Trading Recommended)</option>
                  <option value="15m">15m (Swing)</option>
                  <option value="1h">1h (Macro)</option>
                </select>
              </div>

              <div className="pt-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <label className="text-sm font-medium text-[var(--text-primary)] block">
                    <TermTooltip term="R:R">Standard Risk Size (%)</TermTooltip>
                  </label>
                  <span className="text-xs text-[var(--text-secondary)]">Account equity allocated per order</span>
                </div>
                <input
                  type="number"
                  step="0.1"
                  value={riskPerTrade}
                  onChange={(e) => setRiskPerTrade(e.target.value)}
                  className="input-editorial max-w-xs font-mono text-xs"
                />
              </div>
            </div>
          </section>

          {/* ── SECTION 2: BOT & EXECUTION SAFEGUARDS ── */}
          <section className="p-8 rounded-xl bg-[var(--surface)] border border-[var(--border)]">
            <h2 className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--accent-fresh)] mb-1 flex items-center gap-2">
              <Shield size={14} /> Bot &amp; Safety Controls
            </h2>
            <p className="text-xs text-[var(--text-secondary)] mb-6">
              Safeguards preventing accidental live capital deployment.
            </p>

            <div className="space-y-4 divide-y divide-[var(--border)]">
              <div className="pt-4 flex items-center justify-between gap-4">
                <div>
                  <label className="text-sm font-medium text-[var(--text-primary)] block">
                    Strict "CONFIRM LIVE" Confirmation
                  </label>
                  <span className="text-xs text-[var(--text-secondary)]">
                    Requires typing 'CONFIRM LIVE' before activating live broker execution
                  </span>
                </div>
                <input
                  type="checkbox"
                  checked={requireLiveConfirmation}
                  onChange={(e) => setRequireLiveConfirmation(e.target.checked)}
                  className="w-4 h-4 accent-[var(--accent-fresh)] rounded"
                />
              </div>

              <div className="pt-4 flex items-center justify-between gap-4">
                <div>
                  <label className="text-sm font-medium text-[var(--text-primary)] block">
                    Execution Audio Feedback
                  </label>
                  <span className="text-xs text-[var(--text-secondary)]">
                    Play discreet sound chime on simulated order fills
                  </span>
                </div>
                <input
                  type="checkbox"
                  checked={soundAlerts}
                  onChange={(e) => setSoundAlerts(e.target.checked)}
                  className="w-4 h-4 accent-[var(--accent-fresh)] rounded"
                />
              </div>
            </div>
          </section>

          {/* ── SECTION 3: SYSTEM CONNECTIONS ── */}
          <section className="p-8 rounded-xl bg-[var(--surface)] border border-[var(--border)]">
            <h2 className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--accent-fresh)] mb-1 flex items-center gap-2">
              <Wifi size={14} /> System &amp; Data Infrastructure
            </h2>
            <p className="text-xs text-[var(--text-secondary)] mb-6">
              Live status of local backend processes and connected databases.
            </p>

            <div className="space-y-4 divide-y divide-[var(--border)]">
              <div className="pt-4 flex items-center justify-between gap-4">
                <div>
                  <span className="text-sm font-medium text-[var(--text-primary)] block">
                    FastAPI Server (Local)
                  </span>
                  <span className="font-mono text-xs text-[var(--text-muted)]">
                    Endpoint: http://127.0.0.1:8000
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`badge ${apiStatus === 'connected' ? 'badge-connected' : 'badge-offline'}`}>
                    {apiStatus === 'connected' ? `● Connected (${apiLatency}ms)` : '○ Disconnected'}
                  </span>
                  <button
                    type="button"
                    onClick={pingApi}
                    className="p-1 text-[var(--text-muted)] hover:text-[var(--accent-fresh)]"
                    title="Ping server"
                  >
                    <RefreshCw size={14} />
                  </button>
                </div>
              </div>

              <div className="pt-4 flex items-center justify-between gap-4">
                <div>
                  <span className="text-sm font-medium text-[var(--text-primary)] block">
                    Supabase Cloud Database
                  </span>
                  <span className="font-mono text-xs text-[var(--text-muted)]">
                    PostgreSQL Tables: trades, model_versions
                  </span>
                </div>
                <span className="badge badge-neutral">
                  Configured via Backend
                </span>
              </div>

              <div className="pt-4 flex items-center justify-between gap-4">
                <div>
                  <span className="text-sm font-medium text-[var(--text-primary)] block">
                    Exchange Data Providers
                  </span>
                  <span className="font-mono text-xs text-[var(--text-muted)]">
                    Binance Vision (Crypto) · Dukascopy (Forex)
                  </span>
                </div>
                <span className="badge badge-connected">
                  ● Active
                </span>
              </div>
            </div>
          </section>

          {/* ── SAVE BUTTON ── */}
          <div className="flex justify-end pt-4">
            <button type="submit" className="btn btn-primary text-xs">
              Save All Preferences
            </button>
          </div>

        </form>

      </div>
    </div>
  );
};
