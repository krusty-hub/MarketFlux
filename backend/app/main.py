import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.routes import health, market_data, forecasts, forecast, signals, auth_route, bot, training, backtest, models_route, trades

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("marketflux")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages application startup and shutdown lifecycle.
    Starts the Binance price feed and risk monitoring worker on boot,
    and gracefully shuts them down on exit.
    """
    # ── STARTUP ──
    log.info("Starting MarketFlux services...")

    # Start the Binance WebSocket price feed
    from .services.price_feed import price_feed
    try:
        await price_feed.start()
        log.info("✓ Binance price feed started")
    except Exception as e:
        log.warning(f"Price feed failed to start: {e}")

    # Start the background risk monitoring worker
    from .services.risk_worker import risk_worker
    try:
        await risk_worker.start()
        log.info("✓ Risk monitoring worker started")
    except Exception as e:
        log.warning(f"Risk worker failed to start: {e}")

    log.info("MarketFlux services ready")

    yield  # App is running

    # ── SHUTDOWN ──
    log.info("Shutting down MarketFlux services...")
    try:
        await risk_worker.stop()
    except Exception:
        pass
    try:
        await price_feed.stop()
    except Exception:
        pass
    log.info("MarketFlux services stopped")


app = FastAPI(
    title="MarketFlux API",
    description="AI Trading Forecasting Application with Paper Trading Engine",
    version="2.0.0",
    lifespan=lifespan,
)

# Configure CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", 
        "http://127.0.0.1:5173", 
        "http://localhost:5174", 
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/health", tags=["Health"])
app.include_router(auth_route.router, prefix="/api/auth", tags=["Auth"])
app.include_router(market_data.router, prefix="/api/market", tags=["Market Data"])
app.include_router(forecasts.router, prefix="/api/forecasts", tags=["Forecasts"])
app.include_router(signals.router, prefix="/api/signals", tags=["Signals"])
app.include_router(bot.router, prefix="/api/bot", tags=["Bot"])
app.include_router(training.router, prefix="/api/training", tags=["Training"])
app.include_router(backtest.router, prefix="/api/backtest", tags=["Backtest"])
app.include_router(models_route.router, prefix="/api/models", tags=["Models"])
app.include_router(forecast.router, prefix="/api/forecast", tags=["Unified Forecast"])
app.include_router(trades.router, prefix="/api/trades", tags=["Trades"])

@app.get("/")
def root():
    return {"message": "MarketFlux API is running", "version": "2.0.0"}
