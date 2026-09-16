import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const marketApi = {
  getSymbols: async () => {
    const res = await apiClient.get('/market/symbols');
    return res.data;
  },
  getPrice: async (symbol: string, type: 'crypto' | 'forex') => {
    const res = await apiClient.get(`/market/${symbol}/price?market_type=${type}`);
    return res.data;
  },
};

export const forecastApi = {
  runForecast: async (symbol: string, type: 'crypto' | 'forex', timeframe: string) => {
    const res = await apiClient.post(`/forecasts/run?symbol=${symbol}&market_type=${type}&timeframe=${timeframe}`);
    return res.data;
  },
  getStatus: async () => {
    const res = await apiClient.get('/forecasts/status');
    return res.data;
  },
  getLatest: async () => {
    const res = await apiClient.get('/forecasts/latest');
    return res.data;
  },
};

export const signalsApi = {
  getHistory: async (limit: number = 50) => {
    const res = await apiClient.get(`/signals/history?limit=${limit}`);
    return res.data;
  },
  getPerformance: async () => {
    const res = await apiClient.get('/signals/performance');
    return res.data;
  },
};
