-- ==============================================================
-- MarketFlux Paper-Trading Engine — Supabase Migration Part 2
-- Run this in: https://supabase.com/dashboard/project/sjwlhesqrjyqgvqnuxri/sql/new
-- ==============================================================

-- ── 5. PAPER_TRADES (AI ANALYSIS ENGINE) ──────────────────────
-- Tracks positions pushed from the AI Analysis Engine
CREATE TABLE IF NOT EXISTS public.paper_trades (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    symbol              VARCHAR NOT NULL,
    timeframe           VARCHAR NOT NULL,
    direction           VARCHAR NOT NULL CHECK (direction IN ('LONG', 'SHORT')),
    entry_price         NUMERIC(16, 6) NOT NULL,
    stop_loss           NUMERIC(16, 6),
    take_profit         NUMERIC(16, 6),
    position_size       NUMERIC(16, 8) NOT NULL,
    status              VARCHAR NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'OPEN', 'CLOSED')),
    realized_pnl        NUMERIC(16, 4) DEFAULT 0.0,
    ai_confidence       NUMERIC(5, 2),
    model_id            VARCHAR,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_paper_trades_user ON public.paper_trades(user_id);
CREATE INDEX IF NOT EXISTS idx_paper_trades_status ON public.paper_trades(status);

ALTER TABLE public.paper_trades ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can read own paper_trades" ON public.paper_trades;
CREATE POLICY "Users can read own paper_trades"
    ON public.paper_trades FOR SELECT
    USING (user_id IS NULL OR auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own paper_trades" ON public.paper_trades;
CREATE POLICY "Users can insert own paper_trades"
    ON public.paper_trades FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own paper_trades" ON public.paper_trades;
CREATE POLICY "Users can update own paper_trades"
    ON public.paper_trades FOR UPDATE
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Service role full access paper_trades" ON public.paper_trades;
CREATE POLICY "Service role full access paper_trades"
    ON public.paper_trades FOR ALL
    USING (true)
    WITH CHECK (true);
