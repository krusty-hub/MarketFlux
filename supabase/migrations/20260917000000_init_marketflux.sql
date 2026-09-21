-- ==============================================================================
-- MarketFlux Schema Migration: Profiles, Trades, Models, and RLS
-- ==============================================================================

-- 1. PROFILES TABLE
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    role TEXT DEFAULT 'trader',
    preferences JSONB DEFAULT '{"theme": "dark", "default_market": "BTCUSDT", "default_timeframe": "5m"}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS on profiles
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- Profiles Policies
DROP POLICY IF EXISTS "Users can view their own profile" ON public.profiles;
CREATE POLICY "Users can view their own profile"
    ON public.profiles FOR SELECT
    USING (auth.uid() = id);

DROP POLICY IF EXISTS "Users can update their own profile" ON public.profiles;
CREATE POLICY "Users can update their own profile"
    ON public.profiles FOR UPDATE
    USING (auth.uid() = id);

-- Automatic Profile Creation Trigger on Auth Signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, full_name, avatar_url)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1)),
        COALESCE(NEW.raw_user_meta_data->>'avatar_url', '')
    )
    ON CONFLICT (id) DO UPDATE
    SET email = EXCLUDED.email;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 2. TRADES TABLE
CREATE TABLE IF NOT EXISTS public.trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    pair TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    market_type TEXT NOT NULL DEFAULT 'crypto',
    direction TEXT NOT NULL,
    market_price NUMERIC(16, 6) NOT NULL,
    entry NUMERIC(16, 6),
    stop_loss NUMERIC(16, 6),
    take_profit NUMERIC(16, 6),
    position_size NUMERIC(16, 6),
    market_regime TEXT,
    trend TEXT,
    volatility NUMERIC(16, 6),
    session TEXT,
    liquidity_sweep BOOLEAN DEFAULT false,
    bos BOOLEAN DEFAULT false,
    choch BOOLEAN DEFAULT false,
    order_block BOOLEAN DEFAULT false,
    fvg BOOLEAN DEFAULT false,
    model_confidence NUMERIC(6, 4),
    model_version TEXT,
    prediction NUMERIC(16, 6),
    actual_outcome TEXT, -- WIN | LOSS | BE
    actual_close_price NUMERIC(16, 6),
    pnl NUMERIC(16, 4),
    max_drawdown NUMERIC(8, 4),
    error_type TEXT,
    evaluated_at TIMESTAMPTZ,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexing for trades query performance
CREATE INDEX IF NOT EXISTS idx_trades_pair_time ON public.trades(pair, timeframe);
CREATE INDEX IF NOT EXISTS idx_trades_outcome ON public.trades(actual_outcome);
CREATE INDEX IF NOT EXISTS idx_trades_user_id ON public.trades(user_id);
CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON public.trades(timestamp DESC);

-- Enable RLS on trades
ALTER TABLE public.trades ENABLE ROW LEVEL SECURITY;

-- Trades Policies:
-- 1) Authenticated users can view global platform signals (where user_id IS NULL) or their own trades
DROP POLICY IF EXISTS "Users can read their own or system trades" ON public.trades;
CREATE POLICY "Users can read their own or system trades"
    ON public.trades FOR SELECT
    USING (user_id IS NULL OR auth.uid() = user_id);

-- 2) Authenticated users can insert trades scoped to their user_id
DROP POLICY IF EXISTS "Users can insert their own trades" ON public.trades;
CREATE POLICY "Users can insert their own trades"
    ON public.trades FOR INSERT
    WITH CHECK (auth.uid() = user_id OR user_id IS NULL);

-- 3) Users can update only their own trades
DROP POLICY IF EXISTS "Users can update their own trades" ON public.trades;
CREATE POLICY "Users can update their own trades"
    ON public.trades FOR UPDATE
    USING (auth.uid() = user_id);

-- 3. MODEL VERSIONS TABLE
CREATE TABLE IF NOT EXISTS public.model_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    training_date TIMESTAMPTZ NOT NULL,
    dataset_size INT NOT NULL,
    win_rate NUMERIC(6, 4),
    profit_factor NUMERIC(8, 4),
    max_drawdown NUMERIC(6, 4),
    precision NUMERIC(6, 4),
    model_path TEXT,
    is_active BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_model_versions_symbol_tf ON public.model_versions(symbol, timeframe);
CREATE INDEX IF NOT EXISTS idx_model_versions_active ON public.model_versions(is_active);

-- Enable RLS on model_versions
ALTER TABLE public.model_versions ENABLE ROW LEVEL SECURITY;

-- Model Versions Policies:
DROP POLICY IF EXISTS "Allow read access to model versions for all users" ON public.model_versions;
CREATE POLICY "Allow read access to model versions for all users"
    ON public.model_versions FOR SELECT
    USING (true);

-- 4. USER SETTINGS & BOT CONFIGURATIONS
CREATE TABLE IF NOT EXISTS public.user_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    risk_per_trade_pct NUMERIC(5, 2) DEFAULT 1.5,
    max_daily_loss_pct NUMERIC(5, 2) DEFAULT 4.0,
    max_drawdown_pct NUMERIC(5, 2) DEFAULT 6.0,
    max_open_positions INT DEFAULT 3,
    stop_loss_atr NUMERIC(5, 2) DEFAULT 1.5,
    take_profit_rr NUMERIC(5, 2) DEFAULT 2.0,
    trading_session TEXT DEFAULT 'ANY',
    paper_mode BOOLEAN DEFAULT true,
    require_live_confirmation BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.user_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can manage their own settings" ON public.user_settings;
CREATE POLICY "Users can manage their own settings"
    ON public.user_settings FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);
