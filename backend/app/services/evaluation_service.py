"""
MarketFlux – Evaluation Service
Fetches actual market prices after the forecast period and resolves trade outcomes.
Updates the `trades` table in Supabase with WIN / LOSS / BE results.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("marketflux.evaluation")


def get_supabase_client():
    """Return a Supabase client using the service role key (backend only)."""
    from supabase import create_client
    from ..config.settings import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set.")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def save_signal_to_supabase(signal: dict) -> Optional[str]:
    """
    Save a generated signal to the `trades` table.
    Returns the inserted row id or None on failure.

    The full reasoning context (SMC flags, session, regime, model confidence)
    is stored alongside the signal so the 4-layer evaluation loop has
    everything it needs to group trades and find model mistakes later.
    """
    try:
        client = get_supabase_client()
        smc = signal.get("smc", {})
        levels = signal.get("levels", {})

        row = {
            # Identity
            "pair":          signal["symbol"],
            "timeframe":     signal["timeframe"],
            "market_type":   signal.get("market_type", "crypto"),

            # Signal
            "direction":     signal.get("final_signal", "HOLD"),            # BUY / SELL / HOLD
            "market_price":  signal["current_price"],
            "entry":         levels.get("entry_price"),
            "stop_loss":     levels.get("stop_loss"),
            "take_profit":   levels.get("take_profit_1"),
            "position_size": None,                        # set by execution layer

            # Market context
            "market_regime": smc.get("regime"),
            "trend":         smc.get("trend"),
            "volatility":    smc.get("volatility"),
            "session":       smc.get("session"),

            # SMC flags (each stored as bool for easy SQL filtering)
            "liquidity_sweep": smc.get("liquidity_sweep", False),
            "bos":             smc.get("bos", False),
            "choch":           smc.get("choch", False),
            "order_block":     smc.get("order_block", False),
            "fvg":             smc.get("fvg", False),

            # Model metadata
            "model_confidence": signal.get("confidence_score"),
            "model_version":    signal.get("model_version"),
            "prediction":       signal.get("predicted_price"),

            # Outcome fields — filled by evaluate_pending_trades()
            "actual_outcome":    None,
            "actual_close_price": None,
            "pnl":               None,
            "max_drawdown":      None,
            "error_type":        None,
            "evaluated_at":      None,

            "timestamp": signal.get("signal_timestamp", datetime.now(timezone.utc).isoformat()),
        }

        resp = client.table("trades").insert(row).execute()
        inserted_id = resp.data[0]["id"] if resp.data else None
        log.info(f"✓ Signal saved to Supabase trades table (id={inserted_id})")
        return inserted_id

    except Exception as e:
        log.error(f"Failed to save signal to Supabase: {e}")
        return None


def evaluate_pending_trades(price_fn) -> int:
    """
    Check all unresolved trades in Supabase whose evaluation_time has passed.
    Fetch actual price and mark WIN / LOSS / BE.

    price_fn: callable(symbol: str, market_type: str) -> float
    Returns count of trades evaluated.
    """
    try:
        client = get_supabase_client()

        # Fetch all trades without an outcome
        resp = (
            client.table("trades")
            .select("*")
            .is_("actual_outcome", "null")
            .lte("evaluation_time", datetime.now(timezone.utc).isoformat())
            .execute()
        )

        trades = resp.data or []
        log.info(f"Evaluating {len(trades)} pending trades …")
        evaluated = 0

        for trade in trades:
            try:
                actual_price = price_fn(trade["pair"], trade.get("market_type", "crypto"))
                outcome, error_type = _resolve_outcome(trade, actual_price)

                pnl = _calculate_pnl(trade, actual_price)

                client.table("trades").update({
                    "actual_close_price": actual_price,
                    "actual_outcome":     outcome,
                    "pnl":                pnl,
                    "error_type":         error_type,
                    "evaluated_at":       datetime.now(timezone.utc).isoformat(),
                }).eq("id", trade["id"]).execute()

                # Also insert into signal_results for detailed tracking
                client.table("signal_results").insert({
                    "signal_id":        trade["id"],
                    "actual_price":     actual_price,
                    "price_difference": actual_price - trade["market_price"],
                    "error_percentage": abs(actual_price - float(trade.get("prediction", actual_price)))
                                        / max(float(trade["market_price"]), 1e-9) * 100,
                    "result":           outcome,
                    "evaluated_at":     datetime.now(timezone.utc).isoformat(),
                }).execute()

                log.info(f"  Trade {trade['id']}: {outcome} | actual=${actual_price:.4f}")
                evaluated += 1

            except Exception as e:
                log.warning(f"Could not evaluate trade {trade.get('id')}: {e}")

        return evaluated

    except Exception as e:
        log.error(f"Evaluation job failed: {e}")
        return 0


def _resolve_outcome(trade: dict, actual_price: float) -> tuple[str, Optional[str]]:
    """Determine WIN / LOSS / BE based on actual price vs entry/tp/sl."""
    direction   = trade.get("direction", "BUY")
    entry       = float(trade.get("entry") or trade["market_price"])
    take_profit = float(trade.get("take_profit") or entry * 1.01)
    stop_loss   = float(trade.get("stop_loss")   or entry * 0.99)

    if direction == "BUY":
        if actual_price >= take_profit:
            return "WIN", None
        elif actual_price <= stop_loss:
            return "LOSS", _classify_error(trade)
        else:
            return "BE", None
    elif direction == "SELL":
        if actual_price <= take_profit:
            return "WIN", None
        elif actual_price >= stop_loss:
            return "LOSS", _classify_error(trade)
        else:
            return "BE", None
    return "BE", None


def _classify_error(trade: dict) -> str:
    """Attempt to classify why a losing trade failed using its stored SMC context."""
    if trade.get("liquidity_sweep") and not trade.get("bos"):
        return "false_liquidity_sweep"
    if trade.get("fvg") and not trade.get("choch"):
        return "fvg_no_confirmation"
    if trade.get("bos") and not trade.get("order_block"):
        return "bos_no_ob"
    return "confluence_failure"


def _calculate_pnl(trade: dict, actual_price: float) -> float:
    """Calculate simple price-based P&L (without position sizing)."""
    direction = trade.get("direction", "BUY")
    entry     = float(trade.get("entry") or trade["market_price"])
    if direction == "BUY":
        return round(actual_price - entry, 5)
    elif direction == "SELL":
        return round(entry - actual_price, 5)
    return 0.0
