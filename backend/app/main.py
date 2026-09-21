import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.routes import health, market_data, forecasts, signals, auth_route, bot, training, backtest, models_route

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="MarketFlux API",
    description="AI Trading Forecasting Application",
    version="2.0.0"
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

@app.get("/")
def root():
    return {"message": "MarketFlux API is running", "version": "2.0.0"}
