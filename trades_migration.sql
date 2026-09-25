# How to Apply This Migration
# 1. Go to: https://supabase.com/dashboard/project/sjwlhesqrjyqgvqnuxri/sql/new
# 2. Clear the editor, paste ALL the SQL below, and click ▶ Run

-- ==============================================================
-- TRADES TABLE (MarketFlux — Execution Ledger)
-- ==============================================================
CREATE TABLE IF NOT EXISTS public.trades (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    pair             TEXT NOT NULL,
    timeframe        TEXT NOT NULL,
    market_type      TEXT NOT NULL DEFAULT 'crypto',
    direction        TEXT NOT NULL,
    market_price     NUMERIC(16, 6) NOT NULL,
    entry            NUMERIC(16, 6),
    stop_loss        NUMERIC(16, 6),
    take_profit      NUMERIC(16, 6),
    position_size    NUMERIC(16, 6),
    market_regime    TEXT,
    trend            TEXT,
    volatility       NUMERIC(16, 6),
    session          TEXT,
    liquidity_sweep  BOOLEAN DEFAULT false,
    bos              BOOLEAN DEFAULT false,
    choch            BOOLEAN DEFAULT false,
    order_block      BOOLEAN DEFAULT false,
    fvg              BOOLEAN DEFAULT false,
    model_confidence NUMERIC(6, 4),
    model_version    TEXT,
    prediction       NUMERIC(16, 6),
    actual_outcome   TEXT,                   -- WIN | LOSS | BE
    actual_close_price NUMERIC(16, 6),
    pnl              NUMERIC(16, 4),
    max_drawdown     NUMERIC(8, 4),
    error_type       TEXT,
    evaluated_at     TIMESTAMPTZ,
    timestamp        TIMESTAMPTZ DEFAULT NOW(),
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_trades_pair_time  ON public.trades(pair, timeframe);
CREATE INDEX IF NOT EXISTS idx_trades_outcome    ON public.trades(actual_outcome);
CREATE INDEX IF NOT EXISTS idx_trades_user_id    ON public.trades(user_id);
CREATE INDEX IF NOT EXISTS idx_trades_timestamp  ON public.trades(timestamp DESC);

-- Enable Row Level Security
ALTER TABLE public.trades ENABLE ROW LEVEL SECURITY;

-- RLS Policy: anyone can read system signals (user_id IS NULL) or their own rows
DROP POLICY IF EXISTS "Users can read their own or system trades" ON public.trades;
CREATE POLICY "Users can read their own or system trades"
    ON public.trades FOR SELECT
    USING (user_id IS NULL OR auth.uid() = user_id);

-- RLS Policy: authenticated users can insert rows tied to their account
DROP POLICY IF EXISTS "Users can insert their own trades" ON public.trades;
CREATE POLICY "Users can insert their own trades"
    ON public.trades FOR INSERT
    WITH CHECK (auth.uid() = user_id OR user_id IS NULL);

-- RLS Policy: authenticated users can update only their own rows
DROP POLICY IF EXISTS "Users can update their own trades" ON public.trades;
CREATE POLICY "Users can update their own trades"
    ON public.trades FOR UPDATE
    USING (auth.uid() = user_id);

-- ==============================================================
-- SIGNAL RESULTS TABLE (outcome tracking per signal)
-- ==============================================================
CREATE TABLE IF NOT EXISTS public.signal_results (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id        UUID REFERENCES public.trades(id) ON DELETE CASCADE,
    actual_price     NUMERIC(16, 6),
    price_difference NUMERIC(16, 6),
    error_percentage NUMERIC(10, 6),
    result           TEXT,
    evaluated_at     TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.signal_results ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role full access to signal_results" ON public.signal_results;
CREATE POLICY "Service role full access to signal_results"
    ON public.signal_results FOR ALL
    USING (true)
    WITH CHECK (true);
