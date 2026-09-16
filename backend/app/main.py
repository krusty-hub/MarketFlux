import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.routes import health, market_data, forecasts, signals

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="MarketFlux API",
    description="AI Trading Forecasting Application",
    version="2.0.0"
)

# Configure CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/health", tags=["Health"])
app.include_router(market_data.router, prefix="/api/market", tags=["Market Data"])
app.include_router(forecasts.router, prefix="/api/forecasts", tags=["Forecasts"])
app.include_router(signals.router, prefix="/api/signals", tags=["Signals"])

@app.get("/")
def root():
    return {"message": "MarketFlux API is running"}
