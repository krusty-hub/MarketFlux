-- ==============================================================
-- MarketFlux Paper-Trading Engine — Supabase Migration
-- Run this in: https://supabase.com/dashboard/project/sjwlhesqrjyqgvqnuxri/sql/new
-- ==============================================================

-- ── 1. PORTFOLIOS ─────────────────────────────────────────────
-- Holds virtual paper balance, equity, and trading mode per user.
CREATE TABLE IF NOT EXISTS public.portfolios (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE,
    paper_balance  NUMERIC(16, 4) NOT NULL DEFAULT 10000.0,
    equity         NUMERIC(16, 4) NOT NULL DEFAULT 10000.0,
    live_balance   NUMERIC(16, 4) NOT NULL DEFAULT 0.0,
    mode           TEXT NOT NULL DEFAULT 'paper' CHECK (mode IN ('paper', 'live')),
    total_pnl      NUMERIC(16, 4) NOT NULL DEFAULT 0.0,
    today_pnl      NUMERIC(16, 4) NOT NULL DEFAULT 0.0,
    win_count      INTEGER NOT NULL DEFAULT 0,
    loss_count     INTEGER NOT NULL DEFAULT 0,
    peak_equity    NUMERIC(16, 4) NOT NULL DEFAULT 10000.0,
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    updated_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_portfolios_user ON public.portfolios(user_id);

ALTER TABLE public.portfolios ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can read own portfolio" ON public.portfolios;
CREATE POLICY "Users can read own portfolio"
    ON public.portfolios FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own portfolio" ON public.portfolios;
CREATE POLICY "Users can insert own portfolio"
    ON public.portfolios FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own portfolio" ON public.portfolios;
CREATE POLICY "Users can update own portfolio"
    ON public.portfolios FOR UPDATE
    USING (auth.uid() = user_id);

-- Service role bypass for backend operations
DROP POLICY IF EXISTS "Service role full access portfolios" ON public.portfolios;
CREATE POLICY "Service role full access portfolios"
    ON public.portfolios FOR ALL
    USING (true)
    WITH CHECK (true);


-- ── 2. RISK_SETTINGS ─────────────────────────────────────────
-- Stores per-user risk parameters from the UI.
CREATE TABLE IF NOT EXISTS public.risk_settings (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id               UUID REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE,
    max_daily_loss_pct    NUMERIC(6, 2) NOT NULL DEFAULT 4.0,
    max_drawdown_pct      NUMERIC(6, 2) NOT NULL DEFAULT 6.0,
    risk_per_trade_pct    NUMERIC(6, 2) NOT NULL DEFAULT 1.5,
    max_open_positions    INTEGER NOT NULL DEFAULT 3,
    max_position_size_usd NUMERIC(16, 4) NOT NULL DEFAULT 2500.0,
    stop_loss_atr         NUMERIC(6, 2) NOT NULL DEFAULT 1.5,
    take_profit_rr        NUMERIC(6, 2) NOT NULL DEFAULT 2.0,
    trading_session       TEXT NOT NULL DEFAULT 'ANY',
    consecutive_loss_limit INTEGER NOT NULL DEFAULT 3,
    created_at            TIMESTAMPTZ DEFAULT NOW(),
    updated_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_risk_settings_user ON public.risk_settings(user_id);

ALTER TABLE public.risk_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can manage own risk settings" ON public.risk_settings;
CREATE POLICY "Users can manage own risk settings"
    ON public.risk_settings FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Service role full access risk_settings" ON public.risk_settings;
CREATE POLICY "Service role full access risk_settings"
    ON public.risk_settings FOR ALL
    USING (true)
    WITH CHECK (true);


-- ── 3. POSITIONS ──────────────────────────────────────────────
-- Tracks all paper-traded positions (open and closed).
CREATE TABLE IF NOT EXISTS public.positions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    symbol          TEXT NOT NULL,
    direction       TEXT NOT NULL CHECK (direction IN ('LONG', 'SHORT')),
    entry_price     NUMERIC(16, 6) NOT NULL,
    current_price   NUMERIC(16, 6),
    size            NUMERIC(16, 8) NOT NULL,
    notional_value  NUMERIC(16, 4) NOT NULL,
    stop_loss       NUMERIC(16, 6),
    take_profit     NUMERIC(16, 6),
    unrealized_pnl  NUMERIC(16, 4) NOT NULL DEFAULT 0.0,
    realized_pnl    NUMERIC(16, 4),
    status          TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED', 'HALTED', 'LIQUIDATED')),
    close_reason    TEXT,
    entry_time      TIMESTAMPTZ DEFAULT NOW(),
    close_time      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_positions_user   ON public.positions(user_id);
CREATE INDEX IF NOT EXISTS idx_positions_status ON public.positions(status);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON public.positions(symbol);

ALTER TABLE public.positions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can read own positions" ON public.positions;
CREATE POLICY "Users can read own positions"
    ON public.positions FOR SELECT
    USING (user_id IS NULL OR auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own positions" ON public.positions;
CREATE POLICY "Users can insert own positions"
    ON public.positions FOR INSERT
    WITH CHECK (auth.uid() = user_id OR user_id IS NULL);

DROP POLICY IF EXISTS "Users can update own positions" ON public.positions;
CREATE POLICY "Users can update own positions"
    ON public.positions FOR UPDATE
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Service role full access positions" ON public.positions;
CREATE POLICY "Service role full access positions"
    ON public.positions FOR ALL
    USING (true)
    WITH CHECK (true);


-- ── 4. ACTIVITY_LOGS ──────────────────────────────────────────
-- Drives the "Trading Engine Activity Feed" in the UI.
CREATE TABLE IF NOT EXISTS public.activity_logs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    message     TEXT NOT NULL,
    level       TEXT NOT NULL DEFAULT 'INFO' CHECK (level IN ('INFO', 'SUCCESS', 'WARN', 'ERROR')),
    category    TEXT DEFAULT 'SYSTEM',
    metadata    JSONB,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_activity_logs_user ON public.activity_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_activity_logs_time ON public.activity_logs(created_at DESC);

ALTER TABLE public.activity_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can read own logs" ON public.activity_logs;
CREATE POLICY "Users can read own logs"
    ON public.activity_logs FOR SELECT
    USING (user_id IS NULL OR auth.uid() = user_id);

DROP POLICY IF EXISTS "Service role full access activity_logs" ON public.activity_logs;
CREATE POLICY "Service role full access activity_logs"
    ON public.activity_logs FOR ALL
    USING (true)
    WITH CHECK (true);
