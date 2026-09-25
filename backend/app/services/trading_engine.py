"""
MarketFlux – Trading Engine
Core execution engine that bridges signals → risk checks → order execution.
Handles both paper and (future) live execution modes.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from . import portfolio_service as portfolio
from . import position_service as positions
from . import activity_log_service as activity
from .price_feed import price_feed

log = logging.getLogger("marketflux.trading_engine")


class TradingEngine:
    """
    Execution engine that processes trade signals and manages the full
    lifecycle: risk validation → margin reservation → position opening.
    """

    def execute_paper_trade(
        self,
        user_id: str,
        symbol: str,
        direction: str,
        entry_price: Optional[float] = None,
        size: Optional[float] = None,
        notional_usd: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Execute a paper trade.
        
        You can specify either:
        - `size` (asset amount, e.g. 0.024 BTC) + `entry_price`
        - `notional_usd` (dollar amount, e.g. $2500) → auto-calculates size
        
        Steps:
        1. Resolve entry price from live feed if not provided
        2. Calculate position size
        3. Validate against risk limits
        4. Deduct margin from paper balance
        5. Open position in database
        6. Log the execution
        """
        # 1. Resolve entry price
        if entry_price is None:
            entry_price = price_feed.get_price(symbol.replace("/", ""))
            if entry_price is None:
                raise ValueError(
                    f"No live price available for {symbol}. "
                    "Ensure the price feed is running."
                )

        # 2. Calculate position size
        if size is None and notional_usd is not None:
            size = notional_usd / entry_price
        elif size is None:
            # Default: use risk_per_trade_pct of equity
            port = portfolio.get_or_create_portfolio(user_id)
            risk_settings = portfolio.get_risk_settings(user_id)
            risk_pct = risk_settings.get("risk_per_trade_pct", 1.5) / 100.0
            notional_usd = float(port.get("equity", 10000.0)) * risk_pct * 10  # ~10x margin
            size = notional_usd / entry_price

        notional_value = entry_price * size

        # 3. Validate risk limits
        open_count = positions.count_open_positions(user_id)
        risk_check = portfolio.check_risk_limits(user_id, notional_value, open_count)

        if not risk_check["allowed"]:
            activity.add_log(
                user_id,
                f"Trade REJECTED: {direction} {symbol} — {risk_check['reason']}",
                level="WARN",
                category="RISK",
            )
            return {
                "executed": False,
                "reason": risk_check["reason"],
            }

        # 4. Deduct margin from paper balance
        port = portfolio.get_or_create_portfolio(user_id)
        paper_balance = float(port.get("paper_balance", 10000.0))

        # Margin = notional value (simplified: 1:1 for paper trading)
        margin_required = notional_value
        if margin_required > paper_balance:
            activity.add_log(
                user_id,
                f"Trade REJECTED: Insufficient balance (${paper_balance:,.2f} < ${margin_required:,.2f})",
                level="WARN",
                category="RISK",
            )
            return {
                "executed": False,
                "reason": f"Insufficient paper balance: ${paper_balance:,.2f} < ${margin_required:,.2f}",
            }

        new_balance = paper_balance - margin_required
        portfolio.update_portfolio(user_id, {"paper_balance": round(new_balance, 4)})

        # 5. Open position in database
        position = positions.open_position(
            user_id=user_id,
            symbol=symbol,
            direction=direction.upper(),
            entry_price=entry_price,
            size=size,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        # 6. Log the execution
        pos_id = position.get("id", "???")[:8]
        activity.add_log(
            user_id,
            f"[PAPER] Filled order {pos_id} {direction.upper()} {size:.6f} {symbol} @ ${entry_price:,.2f}",
            level="SUCCESS",
            category="TRADE",
            metadata={
                "position_id": position.get("id"),
                "symbol": symbol,
                "direction": direction.upper(),
                "entry_price": entry_price,
                "size": size,
                "notional_usd": round(notional_value, 2),
            },
        )

        # Update equity
        unrealized = positions.calculate_total_unrealized_pnl(user_id)
        portfolio.update_equity(user_id, new_balance, unrealized)

        log.info(
            f"Paper trade executed: {direction.upper()} {size:.6f} {symbol} "
            f"@ ${entry_price:,.2f} (notional: ${notional_value:,.2f})"
        )

        return {
            "executed": True,
            "position": position,
            "margin_used": round(margin_required, 2),
            "remaining_balance": round(new_balance, 2),
        }

    def close_paper_position(
        self,
        user_id: str,
        position_id: str,
        close_price: Optional[float] = None,
        reason: str = "MANUAL",
    ) -> Dict[str, Any]:
        """
        Close an open paper position.
        
        Steps:
        1. Resolve close price from live feed if not provided
        2. Close the position (calculates realized P&L)
        3. Return margin + P&L to paper balance
        4. Update portfolio stats
        5. Log the closure
        """
        pos = positions.get_position_by_id(position_id)
        if not pos:
            raise ValueError(f"Position {position_id} not found.")
        if pos.get("user_id") != user_id:
            raise ValueError("Position does not belong to this user.")

        symbol = pos["symbol"]

        # 1. Resolve close price
        if close_price is None:
            close_price = price_feed.get_price(symbol.replace("/", ""))
            if close_price is None:
                # Fallback to current_price in DB
                close_price = float(pos.get("current_price", pos["entry_price"]))

        # 2. Close position
        closed = positions.close_position(position_id, close_price, reason)
        realized_pnl = float(closed.get("realized_pnl", 0.0))

        # 3. Return margin + P&L to paper balance
        port = portfolio.get_or_create_portfolio(user_id)
        paper_balance = float(port.get("paper_balance", 0.0))
        notional = float(pos.get("notional_value", 0.0))
        new_balance = paper_balance + notional + realized_pnl
        
        # 4. Update portfolio stats
        today_pnl = float(port.get("today_pnl", 0.0)) + realized_pnl
        total_pnl = float(port.get("total_pnl", 0.0)) + realized_pnl
        win_count = int(port.get("win_count", 0))
        loss_count = int(port.get("loss_count", 0))

        if realized_pnl >= 0:
            win_count += 1
        else:
            loss_count += 1

        portfolio.update_portfolio(user_id, {
            "paper_balance": round(new_balance, 4),
            "today_pnl": round(today_pnl, 4),
            "total_pnl": round(total_pnl, 4),
            "win_count": win_count,
            "loss_count": loss_count,
        })

        # Update equity with remaining unrealized
        unrealized = positions.calculate_total_unrealized_pnl(user_id)
        portfolio.update_equity(user_id, new_balance, unrealized)

        # 5. Log
        pnl_str = f"${realized_pnl:+,.2f}"
        activity.add_log(
            user_id,
            f"[PAPER] Closed {pos['direction']} {symbol} — P&L: {pnl_str} ({reason})",
            level="SUCCESS" if realized_pnl >= 0 else "WARN",
            category="TRADE",
            metadata={
                "position_id": position_id,
                "realized_pnl": realized_pnl,
                "close_price": close_price,
                "reason": reason,
            },
        )

        return {
            "closed": True,
            "position": closed,
            "realized_pnl": round(realized_pnl, 4),
            "new_balance": round(new_balance, 4),
        }


# Module-level singleton
trading_engine = TradingEngine()
