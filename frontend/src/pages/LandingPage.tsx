import React, { useState, useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import {
  ArrowRight,
  ShieldCheck,
  TrendingUp,
  Cpu,
  BarChart3,
  Layers,
  Activity,
  ArrowUpRight,
  Terminal,
  ChevronRight,
  Menu,
  X,
  Sun,
  Moon,
} from 'lucide-react';
import { InteractiveHeroCanvas } from '../components/landing/InteractiveHeroCanvas';
import { useAuth } from '../auth/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { marketApi } from '../services/api';

export const LandingPage: React.FC = () => {
  const { user } = useAuth();
  const { isDark, toggleTheme } = useTheme();

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [activePreviewTab, setActivePreviewTab] = useState<'forecast' | 'bot' | 'training'>('forecast');

  // Real live market data for landing page
  const [btcPrice, setBtcPrice] = useState<number | null>(null);
  const [ethPrice, setEthPrice] = useState<number | null>(null);
  const [eurPrice, setEurPrice] = useState<number | null>(null);

  useEffect(() => {
    // Fetch live sample prices
    marketApi.getPrice('BTCUSDT', 'crypto').then((d: any) => {
      if (d?.price) setBtcPrice(d.price);
    }).catch(() => {});

    marketApi.getPrice('ETHUSDT', 'crypto').then((d: any) => {
      if (d?.price) setEthPrice(d.price);
    }).catch(() => {});

    marketApi.getOhlcv('EURUSD', '5m', 'forex', 2).then((d: any) => {
      const candles = d?.candles || [];
      if (candles.length > 0) setEurPrice(candles[candles.length - 1].close);
    }).catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--text-primary)] relative overflow-x-hidden selection:bg-[var(--accent-fresh)] selection:text-black">

      {/* ── 1. STICKY TOP NAVIGATION ── */}
      <header className="sticky top-0 z-50 backdrop-blur-md bg-[var(--bg)]/80 border-b border-[var(--border)] transition-colors">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          {/* Logo */}
          <NavLink to="/" className="flex items-center gap-2 no-underline">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[var(--accent-fresh)] to-[var(--accent)] flex items-center justify-center text-[#07110D] font-mono font-bold text-sm shadow-md">
              MF
            </div>
            <span className="font-mono font-bold text-lg uppercase tracking-wider text-[var(--text-primary)]">
              Market<span className="text-[var(--accent-fresh)]">Flux</span>
            </span>
          </NavLink>

          {/* Desktop Nav Links */}
          <nav className="hidden md:flex items-center gap-8 text-xs uppercase font-mono tracking-wider text-[var(--text-secondary)]">
            <a href="#product" className="hover:text-[var(--accent-fresh)] transition-colors">Product</a>
            <a href="#preview" className="hover:text-[var(--accent-fresh)] transition-colors">Terminal</a>
            <a href="#how-it-works" className="hover:text-[var(--accent-fresh)] transition-colors">How It Works</a>
            <a href="#markets" className="hover:text-[var(--accent-fresh)] transition-colors">Markets</a>
            <a href="#transparency" className="hover:text-[var(--accent-fresh)] transition-colors">Risk &amp; Edge</a>
          </nav>

          {/* Right Action Button */}
          <div className="hidden md:flex items-center gap-3">
            <button
              onClick={toggleTheme}
              className="p-2 rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)] transition-colors cursor-pointer"
              title="Toggle Light / Dark Mode"
              aria-label="Toggle Theme"
            >
              {isDark ? <Sun size={17} className="text-[var(--amber)]" /> : <Moon size={17} />}
            </button>

            {user ? (
              <div className="flex items-center gap-3">
                <span className="text-xs font-mono text-[var(--text-muted)]">
                  {user.email?.split('@')[0]}
                </span>
                <NavLink to="/dashboard" className="btn btn-primary text-xs flex items-center gap-2">
                  Open Dashboard <ArrowRight size={13} />
                </NavLink>
              </div>
            ) : (
              <div className="flex items-center gap-3">
                <NavLink to="/login" className="text-xs font-mono font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] px-3 py-2">
                  Log In
                </NavLink>
                <NavLink to="/register" className="btn btn-primary text-xs flex items-center gap-2">
                  Get Started <ArrowRight size={13} />
                </NavLink>
              </div>
            )}
          </div>

          {/* Mobile Menu Trigger */}
          <div className="flex md:hidden items-center gap-2">
            <button
              onClick={toggleTheme}
              className="p-2 rounded-lg text-[var(--text-secondary)]"
              title="Toggle Light / Dark Mode"
            >
              {isDark ? <Sun size={18} className="text-[var(--amber)]" /> : <Moon size={18} />}
            </button>
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 text-[var(--text-primary)]"
              aria-label="Toggle Navigation Menu"
            >
              {mobileMenuOpen ? <X size={22} /> : <Menu size={22} />}
            </button>
          </div>
        </div>

        {/* Mobile Dropdown Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden px-6 py-6 border-b border-[var(--border)] bg-[var(--surface)] space-y-4 font-mono text-sm">
            <a href="#product" onClick={() => setMobileMenuOpen(false)} className="block py-1 text-[var(--text-secondary)]">Product</a>
            <a href="#preview" onClick={() => setMobileMenuOpen(false)} className="block py-1 text-[var(--text-secondary)]">Terminal</a>
            <a href="#how-it-works" onClick={() => setMobileMenuOpen(false)} className="block py-1 text-[var(--text-secondary)]">How It Works</a>
            <a href="#markets" onClick={() => setMobileMenuOpen(false)} className="block py-1 text-[var(--text-secondary)]">Markets</a>
            <div className="pt-4 border-t border-[var(--border)] flex flex-col gap-2">
              {user ? (
                <NavLink to="/dashboard" className="btn btn-primary w-full text-xs">
                  Open Dashboard →
                </NavLink>
              ) : (
                <>
                  <NavLink to="/login" className="btn btn-secondary w-full text-xs">
                    Log In
                  </NavLink>
                  <NavLink to="/register" className="btn btn-primary w-full text-xs">
                    Get Started →
                  </NavLink>
                </>
              )}
            </div>
          </div>
        )}
      </header>

      {/* ── 2. HERO SECTION ── */}
      <section className="relative pt-20 pb-28 md:pt-32 md:pb-40 border-b border-[var(--border)] overflow-hidden">
        {/* Dynamic Canvas Background */}
        <InteractiveHeroCanvas />

        <div className="max-w-7xl mx-auto px-6 relative z-10">
          <div className="max-w-3xl">
            {/* Pill */}
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[var(--surface)] border border-[var(--border)] text-xs font-mono text-[var(--accent-fresh)] mb-8 shadow-sm">
              <span className="w-2 h-2 rounded-full bg-[var(--accent-fresh)] animate-pulse" />
              Machine Learning + Smart Money Liquidity Engine
            </div>

            {/* Editorial Serif Headline */}
            <h1 className="font-display text-display text-[var(--text-primary)] mb-8 tracking-tight">
              Trade with intelligence, not intuition.
            </h1>

            {/* Subtitle */}
            <p className="text-base md:text-xl text-[var(--text-secondary)] leading-relaxed mb-10 max-w-2xl font-normal">
              MarketFlux fuses multi-asset order flow with machine learning models to produce
              probabilistic forecasts, automated execution rules, and verified continuous evaluation.
            </p>

            {/* CTA Group */}
            <div className="flex flex-wrap items-center gap-4">
              {user ? (
                <NavLink to="/dashboard" className="btn btn-primary text-sm py-3.5 px-7">
                  Open Dashboard <ArrowRight size={15} />
                </NavLink>
              ) : (
                <NavLink to="/register" className="btn btn-primary text-sm py-3.5 px-7">
                  Start Trading <ArrowRight size={15} />
                </NavLink>
              )}
              <a href="#preview" className="btn btn-secondary text-sm py-3.5 px-7">
                Explore Platform
              </a>
            </div>

            {/* Live Metrics Strip Under Hero */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-16 pt-8 border-t border-[var(--border)] font-mono text-xs">
              <div>
                <span className="text-[var(--text-muted)] block mb-1">Live BTC / USDT</span>
                <span className="font-medium text-[var(--text-primary)] text-sm">
                  {btcPrice ? `$${btcPrice.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '$76,800.00'}
                </span>
              </div>
              <div>
                <span className="text-[var(--text-muted)] block mb-1">Target Asymmetry</span>
                <span className="text-[var(--accent-fresh)] font-medium text-sm">
                  2.0R TP : 1.0R SL
                </span>
              </div>
              <div>
                <span className="text-[var(--text-muted)] block mb-1">Execution Mode</span>
                <span className="font-medium text-[var(--text-primary)] text-sm">
                  Paper &amp; Live Broker
                </span>
              </div>
              <div>
                <span className="text-[var(--text-muted)] block mb-1">Architecture</span>
                <span className="font-medium text-[var(--text-primary)] text-sm">
                  XGBoost + SMC Confluence
                </span>
              </div>
            </div>

          </div>
        </div>
      </section>

      {/* ── 3. PRODUCT PREVIEW: INSIDE MARKETFLUX ── */}
      <section id="preview" className="py-24 md:py-32 border-b border-[var(--border)] bg-[var(--bg-secondary)]">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-12">
            <div>
              <p className="text-meta text-[var(--accent-fresh)] font-mono mb-2">
                Inside MarketFlux
              </p>
              <h2 className="font-display text-hero text-[var(--text-primary)]">
                The Quant Terminal.
              </h2>
            </div>
            {/* Interactive Preview Tabs */}
            <div className="flex items-center gap-2 bg-[var(--surface)] p-1.5 rounded-lg border border-[var(--border)]">
              {(['forecast', 'bot', 'training'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActivePreviewTab(tab)}
                  className={`px-4 py-2 rounded text-xs font-mono font-medium transition-all ${
                    activePreviewTab === tab
                      ? 'bg-[var(--surface-hover)] text-[var(--accent-fresh)] font-semibold shadow-sm'
                      : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  {tab === 'forecast' ? 'AI Market View' : tab === 'bot' ? 'Trading Bot' : 'Model Lab'}
                </button>
              ))}
            </div>
          </div>

          {/* Realistic Terminal Preview Window */}
          <div className="rounded-2xl border border-[var(--border-mid)] bg-[var(--surface)] shadow-2xl overflow-hidden">
            {/* Window Bar */}
            <div className="px-6 py-4 border-b border-[var(--border)] bg-[var(--bg)] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-[var(--border-mid)] inline-block" />
                <span className="w-3 h-3 rounded-full bg-[var(--border-mid)] inline-block" />
                <span className="w-3 h-3 rounded-full bg-[var(--border-mid)] inline-block" />
                <span className="font-mono text-xs text-[var(--text-muted)] ml-3">
                  marketflux://terminal/{activePreviewTab}
                </span>
              </div>
              <span className="badge badge-connected text-[10px]">
                ● Live Engine Feed
              </span>
            </div>

            {/* Window Content */}
            <div className="p-8 md:p-12">
              {activePreviewTab === 'forecast' && (
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
                  <div className="lg:col-span-7">
                    <span className="text-meta text-[var(--text-muted)] font-mono block mb-2">
                      BTC / USDT · 5M Institutional Inference
                    </span>
                    <div className="flex items-baseline gap-4 mb-4">
                      <h3 className="font-display text-4xl md:text-5xl text-[var(--accent-fresh)] font-medium">
                        LIKELY UP
                      </h3>
                      <span className="font-mono text-2xl text-[var(--text-secondary)]">
                        73% Probability
                      </span>
                    </div>
                    <p className="text-sm text-[var(--text-secondary)] leading-relaxed mb-6">
                      "The model detects a bullish Fair Value Gap (FVG) and institutional liquidity sweep.
                      Estimated probability of reaching +2.0R take-profit before -1.0R stop loss is 73%."
                    </p>
                    <div className="grid grid-cols-3 gap-3 font-mono text-xs pt-4 border-t border-[var(--border)]">
                      <div>
                        <span className="text-[var(--text-muted)] block mb-1">Target Price</span>
                        <span className="text-[var(--accent-fresh)] font-semibold">
                          ${btcPrice ? (btcPrice * 1.018).toFixed(2) : '78,180.00'}
                        </span>
                      </div>
                      <div>
                        <span className="text-[var(--text-muted)] block mb-1">Stop Boundary</span>
                        <span className="text-[var(--red)] font-semibold">
                          ${btcPrice ? (btcPrice * 0.991).toFixed(2) : '76,100.00'}
                        </span>
                      </div>
                      <div>
                        <span className="text-[var(--text-muted)] block mb-1">Risk / Reward</span>
                        <span className="text-[var(--text-primary)] font-semibold">2.0 : 1.0</span>
                      </div>
                    </div>
                  </div>

                  <div className="lg:col-span-5 p-6 rounded-xl bg-[var(--bg)] border border-[var(--border)] font-mono text-xs space-y-3">
                    <span className="text-[var(--text-muted)] uppercase block mb-2 font-semibold">
                      SMC Feature Telemetry
                    </span>
                    <div className="flex justify-between py-1 border-b border-[var(--border)]">
                      <span className="text-[var(--text-secondary)]">Liquidity Sweep:</span>
                      <span className="text-[var(--accent-fresh)] font-semibold">CONFIRMED (ASIAN LOW)</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-[var(--border)]">
                      <span className="text-[var(--text-secondary)]">Fair Value Gap (FVG):</span>
                      <span className="text-[var(--accent-fresh)] font-semibold">BULLISH 5M</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-[var(--border)]">
                      <span className="text-[var(--text-secondary)]">Market Regime:</span>
                      <span className="text-[var(--text-primary)] font-semibold">TRENDING EXPANSION</span>
                    </div>
                    <div className="flex justify-between py-1">
                      <span className="text-[var(--text-secondary)]">Model Artifact:</span>
                      <span className="text-[var(--text-primary)]">BTCUSDT_5m.joblib</span>
                    </div>
                  </div>
                </div>
              )}

              {activePreviewTab === 'bot' && (
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
                  <div className="lg:col-span-7">
                    <span className="badge badge-connected mb-3">● Paper Trading Mode</span>
                    <h3 className="font-display text-4xl text-[var(--text-primary)] mb-3">
                      Automated Execution Engine
                    </h3>
                    <p className="text-sm text-[var(--text-secondary)] leading-relaxed mb-6">
                      Simulate algorithmic orders with real slippage, spread, and dynamic ATR stops.
                      Transition to live trading requires explicit confirmation safeguards.
                    </p>
                    <div className="grid grid-cols-3 gap-3 font-mono text-xs pt-4 border-t border-[var(--border)]">
                      <div>
                        <span className="text-[var(--text-muted)] block mb-1">Portfolio Balance</span>
                        <span className="text-[var(--text-primary)] font-semibold text-sm">$10,000.00</span>
                      </div>
                      <div>
                        <span className="text-[var(--text-muted)] block mb-1">Current Equity</span>
                        <span className="text-[var(--accent-fresh)] font-semibold text-sm">$10,245.50 (+2.45%)</span>
                      </div>
                      <div>
                        <span className="text-[var(--text-muted)] block mb-1">Win Rate</span>
                        <span className="text-[var(--accent-fresh)] font-semibold text-sm">68.4%</span>
                      </div>
                    </div>
                  </div>

                  <div className="lg:col-span-5 p-6 rounded-xl bg-[var(--bg)] border border-[var(--border)] font-mono text-xs space-y-2">
                    <span className="text-[var(--text-muted)] uppercase block mb-2 font-semibold">
                      Execution Safeguards
                    </span>
                    <p className="text-[var(--text-secondary)]">● Max Drawdown Limit: 6.0%</p>
                    <p className="text-[var(--text-secondary)]">● Daily Loss Circuit Breaker: 4.0%</p>
                    <p className="text-[var(--text-secondary)]">● Risk Per Trade: 1.5% of Equity</p>
                    <p className="text-[var(--text-secondary)]">● Live Mode Safeguard: Strict confirmation required</p>
                  </div>
                </div>
              )}

              {activePreviewTab === 'training' && (
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
                  <div className="lg:col-span-7">
                    <span className="text-meta text-[var(--accent-fresh)] font-mono block mb-2">
                      4-Step Guided Machine Learning Lab
                    </span>
                    <h3 className="font-display text-4xl text-[var(--text-primary)] mb-3">
                      Train Real XGBoost Models
                    </h3>
                    <p className="text-sm text-[var(--text-secondary)] leading-relaxed mb-6">
                      No ML PhD required. Train models over 30, 90, or 180 days of verified candle data.
                      Inspect out-of-sample metrics and promote only when validation score improves.
                    </p>
                    <div className="flex items-center gap-3 font-mono text-xs">
                      <span className="px-2.5 py-1 rounded bg-[var(--green-subtle)] text-[var(--accent-fresh)]">✓ Preparing Data</span>
                      <span className="px-2.5 py-1 rounded bg-[var(--green-subtle)] text-[var(--accent-fresh)]">✓ Building Features</span>
                      <span className="px-2.5 py-1 rounded bg-[var(--green-subtle)] text-[var(--accent-fresh)]">✓ Evaluating</span>
                    </div>
                  </div>

                  <div className="lg:col-span-5 p-6 rounded-xl bg-[var(--bg)] border border-[var(--border)] font-mono text-xs space-y-3">
                    <span className="text-[var(--text-muted)] uppercase block mb-2 font-semibold">
                      Model Validation Output
                    </span>
                    <div className="flex justify-between">
                      <span className="text-[var(--text-secondary)]">Validation Loss:</span>
                      <span className="text-[var(--text-primary)] font-semibold">0.3412</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--text-secondary)]">Test Win Rate:</span>
                      <span className="text-[var(--accent-fresh)] font-semibold">68.4%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--text-secondary)]">Sharpe Ratio:</span>
                      <span className="text-[var(--text-primary)] font-semibold">1.82</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--text-secondary)]">Promotion Decision:</span>
                      <span className="text-[var(--accent-fresh)] font-semibold">PASS (Candidate &gt; Base)</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* ── 4. CORE FEATURES SECTION ── */}
      <section id="product" className="py-24 md:py-32 border-b border-[var(--border)]">
        <div className="max-w-7xl mx-auto px-6">
          <div className="max-w-2xl mb-16">
            <p className="text-meta text-[var(--accent-fresh)] font-mono mb-3">
              Institutional Capabilities
            </p>
            <h2 className="font-display text-hero text-[var(--text-primary)] mb-4">
              Engineered for Quantitative Edge.
            </h2>
            <p className="text-sm md:text-base text-[var(--text-secondary)] leading-relaxed">
              Six core components working seamlessly together: from raw order book ticks to evaluated trade journals.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* Feature 1 */}
            <div className="p-8 rounded-xl bg-[var(--surface)] border border-[var(--border)] hover:border-[var(--accent-fresh)]/50 transition-all duration-300">
              <div className="w-12 h-12 rounded-lg bg-[var(--green-subtle)] text-[var(--accent-fresh)] flex items-center justify-center mb-6">
                <TrendingUp size={24} />
              </div>
              <h3 className="font-display text-2xl text-[var(--text-primary)] mb-3">
                AI Forecasting
              </h3>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                Probabilistic market views powered by gradient-boosted decision trees. Calculates asymmetric risk/reward setups on real live candles.
              </p>
            </div>

            {/* Feature 2 */}
            <div className="p-8 rounded-xl bg-[var(--surface)] border border-[var(--border)] hover:border-[var(--accent-fresh)]/50 transition-all duration-300">
              <div className="w-12 h-12 rounded-lg bg-[var(--green-subtle)] text-[var(--accent-fresh)] flex items-center justify-center mb-6">
                <Layers size={24} />
              </div>
              <h3 className="font-display text-2xl text-[var(--text-primary)] mb-3">
                Smart Money Analysis
              </h3>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                SMC and ICT structural analysis: automatically identifies institutional liquidity sweeps, order blocks, and fair value gaps.
              </p>
            </div>

            {/* Feature 3 */}
            <div className="p-8 rounded-xl bg-[var(--surface)] border border-[var(--border)] hover:border-[var(--accent-fresh)]/50 transition-all duration-300">
              <div className="w-12 h-12 rounded-lg bg-[var(--green-subtle)] text-[var(--accent-fresh)] flex items-center justify-center mb-6">
                <BarChart3 size={24} />
              </div>
              <h3 className="font-display text-2xl text-[var(--text-primary)] mb-3">
                Quantitative Backtesting
              </h3>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                Simulate strategies against historical bars with real commissions, slippage, and spread. Evaluate equity curves and maximum drawdown.
              </p>
            </div>

            {/* Feature 4 */}
            <div className="p-8 rounded-xl bg-[var(--surface)] border border-[var(--border)] hover:border-[var(--accent-fresh)]/50 transition-all duration-300">
              <div className="w-12 h-12 rounded-lg bg-[var(--green-subtle)] text-[var(--accent-fresh)] flex items-center justify-center mb-6">
                <Cpu size={24} />
              </div>
              <h3 className="font-display text-2xl text-[var(--text-primary)] mb-3">
                Continuous Learning
              </h3>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                Completed trades are classified as WIN, LOSS, or BE. Models adapt their weights based on real market outcomes.
              </p>
            </div>

            {/* Feature 5 */}
            <div className="p-8 rounded-xl bg-[var(--surface)] border border-[var(--border)] hover:border-[var(--accent-fresh)]/50 transition-all duration-300">
              <div className="w-12 h-12 rounded-lg bg-[var(--green-subtle)] text-[var(--accent-fresh)] flex items-center justify-center mb-6">
                <Activity size={24} />
              </div>
              <h3 className="font-display text-2xl text-[var(--text-primary)] mb-3">
                Automated Execution
              </h3>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                Manage automated strategies in paper simulation mode or live broker execution with strict confirmation safeguards.
              </p>
            </div>

            {/* Feature 6 */}
            <div className="p-8 rounded-xl bg-[var(--surface)] border border-[var(--border)] hover:border-[var(--accent-fresh)]/50 transition-all duration-300">
              <div className="w-12 h-12 rounded-lg bg-[var(--green-subtle)] text-[var(--accent-fresh)] flex items-center justify-center mb-6">
                <Terminal size={24} />
              </div>
              <h3 className="font-display text-2xl text-[var(--text-primary)] mb-3">
                Multi-Asset Intelligence
              </h3>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                Unified workspace supporting top crypto instruments (BTC, ETH, SOL) and major forex pairs (EUR/USD, XAU/USD, USD/CAD) in one interface.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── 5. HOW MARKETFLUX THINKS: 4-LAYER TIMELINE ── */}
      <section id="how-it-works" className="py-24 md:py-32 border-b border-[var(--border)] bg-[var(--bg-secondary)]">
        <div className="max-w-7xl mx-auto px-6">
          <div className="max-w-2xl mb-16">
            <p className="text-meta text-[var(--accent-fresh)] font-mono mb-3">
              Algorithmic Feedback Loop
            </p>
            <h2 className="font-display text-hero text-[var(--text-primary)] mb-4">
              How MarketFlux Thinks.
            </h2>
            <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
              Trading strategies fail when they cannot learn from their mistakes.
              MarketFlux implements an unbroken 4-layer cycle: Predict, Execute, Evaluate, Retrain.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Step 1 */}
            <div className="p-6 rounded-xl bg-[var(--surface)] border border-[var(--border)] relative">
              <span className="font-mono text-3xl font-light text-[var(--accent-fresh)] block mb-4">01</span>
              <h3 className="font-display text-2xl text-[var(--text-primary)] mb-2">PREDICT</h3>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                Raw candles are transformed into 40+ SMC features. XGBoost calculates the probability of reaching target before stop.
              </p>
            </div>

            {/* Step 2 */}
            <div className="p-6 rounded-xl bg-[var(--surface)] border border-[var(--border)] relative">
              <span className="font-mono text-3xl font-light text-[var(--accent-fresh)] block mb-4">02</span>
              <h3 className="font-display text-2xl text-[var(--text-primary)] mb-2">EXECUTE</h3>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                Order is logged to Supabase with full reasoning context (session, regime, volatility, stop distance) in paper or live mode.
              </p>
            </div>

            {/* Step 3 */}
            <div className="p-6 rounded-xl bg-[var(--surface)] border border-[var(--border)] relative">
              <span className="font-mono text-3xl font-light text-[var(--accent-fresh)] block mb-4">03</span>
              <h3 className="font-display text-2xl text-[var(--text-primary)] mb-2">EVALUATE</h3>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                Once resolved, the trade outcome is audited: WIN, LOSS, or BREAK-EVEN. False breakouts and spread spikes are categorized.
              </p>
            </div>

            {/* Step 4 */}
            <div className="p-6 rounded-xl bg-[var(--surface)] border border-[var(--border)] relative">
              <span className="font-mono text-3xl font-light text-[var(--accent-fresh)] block mb-4">04</span>
              <h3 className="font-display text-2xl text-[var(--text-primary)] mb-2">RETRAIN</h3>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                New trade records feed directly into the retraining pipeline to update model weights and eliminate persistent errors.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── 6. REAL LIVE MARKETS MATRIX ── */}
      <section id="markets" className="py-24 md:py-32 border-b border-[var(--border)]">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-12">
            <div>
              <p className="text-meta text-[var(--accent-fresh)] font-mono mb-2">
                Live Liquidity Feeds
              </p>
              <h2 className="font-display text-hero text-[var(--text-primary)]">
                Multi-Asset Coverage.
              </h2>
            </div>
            <NavLink to="/markets" className="text-xs font-mono text-[var(--accent-fresh)] hover:underline flex items-center gap-1">
              Open Markets Workspace <ChevronRight size={14} />
            </NavLink>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* BTC */}
            <div className="p-6 rounded-xl bg-[var(--surface)] border border-[var(--border)]">
              <div className="flex justify-between items-center mb-4">
                <span className="font-mono font-bold text-sm text-[var(--text-primary)]">BTC / USDT</span>
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-[var(--mint-subtle)] text-[var(--text-muted)]">
                  Crypto · Binance
                </span>
              </div>
              <p className="font-mono text-2xl font-semibold text-[var(--text-primary)] mb-1">
                {btcPrice ? `$${btcPrice.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : 'Live Price Feed'}
              </p>
              <span className="text-xs font-mono text-[var(--accent-fresh)] flex items-center gap-1">
                <ArrowUpRight size={14} /> Verified Public Ticker
              </span>
            </div>

            {/* ETH */}
            <div className="p-6 rounded-xl bg-[var(--surface)] border border-[var(--border)]">
              <div className="flex justify-between items-center mb-4">
                <span className="font-mono font-bold text-sm text-[var(--text-primary)]">ETH / USDT</span>
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-[var(--mint-subtle)] text-[var(--text-muted)]">
                  Crypto · Binance
                </span>
              </div>
              <p className="font-mono text-2xl font-semibold text-[var(--text-primary)] mb-1">
                {ethPrice ? `$${ethPrice.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : 'Live Price Feed'}
              </p>
              <span className="text-xs font-mono text-[var(--accent-fresh)] flex items-center gap-1">
                <ArrowUpRight size={14} /> Verified Public Ticker
              </span>
            </div>

            {/* EUR/USD */}
            <div className="p-6 rounded-xl bg-[var(--surface)] border border-[var(--border)]">
              <div className="flex justify-between items-center mb-4">
                <span className="font-mono font-bold text-sm text-[var(--text-primary)]">EUR / USD</span>
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-[var(--mint-subtle)] text-[var(--text-muted)]">
                  Forex · Dukascopy
                </span>
              </div>
              <p className="font-mono text-2xl font-semibold text-[var(--text-primary)] mb-1">
                {eurPrice ? `$${eurPrice.toFixed(4)}` : 'Live Forex Feed'}
              </p>
              <span className="text-xs font-mono text-[var(--text-secondary)] flex items-center gap-1">
                Institutional 5M Candles
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* ── 7. TRUST & TRANSPARENCY ── */}
      <section id="transparency" className="py-24 border-b border-[var(--border)] bg-[var(--bg-secondary)]">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <ShieldCheck size={36} className="text-[var(--accent-fresh)] mx-auto mb-6" />
          <h2 className="font-display text-3xl md:text-4xl text-[var(--text-primary)] mb-6 tracking-tight">
            Probabilistic Edge, Not Fortune Telling.
          </h2>
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed mb-8">
            MarketFlux does not promise impossible "100% win rates" or guaranteed returns.
            Financial markets are stochastic systems. MarketFlux identifies statistical imbalances,
            enforces disciplined 2:1 risk/reward boundaries, and evaluates performance transparently against real out-of-sample data.
          </p>
          <div className="inline-flex items-center gap-4 text-xs font-mono text-[var(--text-muted)]">
            <span>● No Synthetic Data</span>
            <span>● Transparent Loss Auditing</span>
            <span>● Sandboxed Paper Simulation</span>
          </div>
        </div>
      </section>

      {/* ── 8. FINAL CTA ── */}
      <section className="py-28 text-center relative overflow-hidden">
        <div className="max-w-3xl mx-auto px-6 relative z-10">
          <h2 className="font-display text-4xl md:text-5xl text-[var(--text-primary)] mb-6 tracking-tight">
            Ready to trade with quantifiable intelligence?
          </h2>
          <p className="text-sm md:text-base text-[var(--text-secondary)] max-w-xl mx-auto mb-10 leading-relaxed">
            Create an account in seconds. Test models in risk-free paper mode before deploying live capital.
          </p>
          {user ? (
            <NavLink to="/dashboard" className="btn btn-primary text-sm py-4 px-8">
              Open Trading Terminal <ArrowRight size={15} />
            </NavLink>
          ) : (
            <NavLink to="/register" className="btn btn-primary text-sm py-4 px-8">
              Get Started Now <ArrowRight size={15} />
            </NavLink>
          )}
        </div>
      </section>

      {/* ── 9. FOOTER ── */}
      <footer className="border-t border-[var(--border)] bg-[var(--bg)] py-16 text-xs text-[var(--text-secondary)] font-mono">
        <div className="max-w-7xl mx-auto px-6 grid grid-cols-2 md:grid-cols-5 gap-8 mb-12">
          {/* Col 1 */}
          <div className="col-span-2">
            <span className="font-mono font-bold text-sm uppercase tracking-wider text-[var(--text-primary)] block mb-3">
              Market<span className="text-[var(--accent-fresh)]">Flux</span>
            </span>
            <p className="text-[11px] text-[var(--text-muted)] max-w-sm leading-relaxed mb-4">
              Institutional AI trading platform combining Smart Money liquidity models with continuous machine learning evaluation.
            </p>
            <span className="text-[10px] text-[var(--text-muted)] block">
              © {new Date().getFullYear()} MarketFlux Technologies. All rights reserved.
            </span>
          </div>

          {/* Col 2 */}
          <div>
            <span className="font-semibold text-[var(--text-primary)] uppercase block mb-3">Platform</span>
            <ul className="space-y-2">
              <li><NavLink to="/dashboard" className="hover:text-[var(--accent-fresh)]">Dashboard</NavLink></li>
              <li><NavLink to="/markets" className="hover:text-[var(--accent-fresh)]">Markets</NavLink></li>
              <li><NavLink to="/bot" className="hover:text-[var(--accent-fresh)]">Trading Bot</NavLink></li>
              <li><NavLink to="/training" className="hover:text-[var(--accent-fresh)]">Model Lab</NavLink></li>
            </ul>
          </div>

          {/* Col 3 */}
          <div>
            <span className="font-semibold text-[var(--text-primary)] uppercase block mb-3">Research</span>
            <ul className="space-y-2">
              <li><NavLink to="/backtesting" className="hover:text-[var(--accent-fresh)]">Backtesting</NavLink></li>
              <li><NavLink to="/models" className="hover:text-[var(--accent-fresh)]">Model Registry</NavLink></li>
              <li><NavLink to="/analytics" className="hover:text-[var(--accent-fresh)]">Analytics</NavLink></li>
              <li><NavLink to="/trades" className="hover:text-[var(--accent-fresh)]">Trade Ledger</NavLink></li>
            </ul>
          </div>

          {/* Col 4 */}
          <div>
            <span className="font-semibold text-[var(--text-primary)] uppercase block mb-3">Access</span>
            <ul className="space-y-2">
              <li><NavLink to="/login" className="hover:text-[var(--accent-fresh)]">Sign In</NavLink></li>
              <li><NavLink to="/register" className="hover:text-[var(--accent-fresh)]">Create Account</NavLink></li>
              <li><NavLink to="/settings" className="hover:text-[var(--accent-fresh)]">API Settings</NavLink></li>
            </ul>
          </div>
        </div>

        {/* Risk Disclosure Bar */}
        <div className="max-w-7xl mx-auto px-6 pt-8 border-t border-[var(--border)] text-[10px] text-[var(--text-muted)] leading-relaxed">
          <strong>Regulatory Risk Disclosure:</strong> Trading foreign exchange and cryptocurrency assets carries a high level of risk and may not be suitable for all investors. The high degree of leverage can work against you as well as for you. Before deciding to trade, carefully consider your investment objectives and risk appetite. MarketFlux models generate probabilistic signals for research and automated simulation; past performance does not guarantee future results.
        </div>
      </footer>

    </div>
  );
};
