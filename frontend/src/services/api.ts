import axios from 'axios';
import { supabase } from '../lib/supabase';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

// Attach Supabase access token to every outgoing request when authenticated
apiClient.interceptors.request.use(async (config) => {
  if (supabase) {
    try {
      const { data } = await supabase.auth.getSession();
      const token = data?.session?.access_token;
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    } catch {
      // Continue without token
    }
  }
  return config;
});

// ── TYPES ──

export interface Candle {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface MarketOhlcvResponse {
  symbol: string;
  market_type: string;
  timeframe: string;
  count: number;
  candles: Candle[];
}

export interface ModelItem {
  id: string;
  filename: string;
  symbol: string;
  timeframe: string;
  version: string;
  is_active: boolean;
  size_kb: number;
  created_at: string;
  model_type: string;
  metrics?: Record<string, any>;
}

export interface TrainingConfig {
  symbol?: string;
  timeframe?: string;
  model_type?: string;
  epochs?: number;
  batch_size?: number;
  learning_rate?: number;
  limit?: number;
  train_split?: number;
  val_split?: number;
  test_split?: number;
  risk_pct?: number;
  lookahead?: number;
  random_seed?: number;
  [key: string]: any;
}

export type TrainingStatus =
  | 'IDLE'
  | 'STARTING'
  | 'RUNNING'
  | 'PAUSED'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED'
  | 'idle'
  | 'running'
  | 'paused'
  | 'completed'
  | 'failed'
  | 'stopped'
  | (string & {});

export interface TrainingJobData {
  id: string;
  status: TrainingStatus;
  progress_pct: number;
  current_epoch: number;
  total_epochs: number;
  train_loss: number | null;
  val_loss: number | null;
  accuracy: number | null;
  f1_score: number | null;
  logs: string[];
  recent_logs?: any[];
  metrics_history?: any[];
  epochs?: number;
  config: TrainingConfig;
  error?: string | null;
  created_at: string;
  updated_at: string;
  model_filename?: string;
  [key: string]: any;
}

export interface BacktestConfig {
  symbol: string;
  timeframe: string;
  limit: number;
  starting_balance: number;
  risk_per_trade_pct: number;
  spread: number;
  commission?: number;
  slippage_pct?: number;
  model_id?: string | null;
  min_confidence?: number;
  [key: string]: any;
}

export interface BacktestResult {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  break_even_trades?: number;
  win_rate: number;
  net_profit: number;
  return_pct: number;
  profit_factor: number;
  max_drawdown_pct: number;
  expectancy: number;
  sharpe_ratio?: number;
  equity_curve: Array<{ date: string; equity: number }>;
  trades: any[];
  [key: string]: any;
}

export interface BotStatusData {
  is_running: boolean;
  mode: 'paper' | 'live';
  positions: any[];
  logs?: any[];
  risk_config?: any;
  pnl?: number;
  win_rate?: number;
  trades_count?: number;
  [key: string]: any;
}

export interface ExecuteTradeParams {
  symbol: string;
  direction: 'LONG' | 'SHORT';
  entry_price?: number;
  size?: number;
  notional_usd?: number;
  stop_loss?: number;
  take_profit?: number;
}

export interface TradeExecutionResult {
  executed: boolean;
  reason?: string;
  position?: any;
  margin_used?: number;
  remaining_balance?: number;
}

export interface ClosePositionResult {
  closed: boolean;
  position?: any;
  realized_pnl?: number;
  new_balance?: number;
}

export interface PriceFeedStatus {
  running: boolean;
  tracked_symbols: string[];
  cached_prices: Record<string, number>;
  last_update: Record<string, number>;
  subscriber_count: number;
}

export interface WsMessage {
  type: string;
  prices: Record<string, number>;
  price_feed_active: boolean;
  portfolio?: {
    paper_balance: number;
    equity: number;
    today_pnl: number;
    unrealized_pnl: number;
  };
  positions?: Array<{
    id: string;
    full_id: string;
    symbol: string;
    direction: string;
    entry_price: number;
    current_price: number;
    unrealized_pnl: number;
    status: string;
  }>;
}

// ── API MODULES ──

export const marketApi = {
  getSymbols: async () => {
    const res = await apiClient.get('/market/symbols');
    return res.data;
  },
  getPrice: async (symbol: string, type: 'crypto' | 'forex') => {
    const res = await apiClient.get(`/market/${symbol}/price?market_type=${type}`);
    return res.data;
  },
  getOhlcv: async (
    symbol: string,
    timeframe: string = '5m',
    marketType: 'crypto' | 'forex' = 'crypto',
    limit: number = 200
  ): Promise<MarketOhlcvResponse> => {
    const res = await apiClient.get(`/market/${symbol}/ohlcv`, {
      params: {
        timeframe,
        market_type: marketType,
        limit,
      },
    });
    return res.data;
  },
};

export const forecastApi = {
  runForecast: async (symbol: string, type: 'crypto' | 'forex', timeframe: string, news_sentiment: number = 0.0, is_high_impact_news_window: boolean = false) => {
    const res = await apiClient.post(`/forecasts/run?symbol=${symbol}&market_type=${type}&timeframe=${timeframe}&news_sentiment=${news_sentiment}&is_high_impact_news_window=${is_high_impact_news_window}`);
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
  analyze: async (config: any): Promise<any> => {
    const res = await apiClient.post('/forecast/analyze', config);
    return res.data;
  }
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
  getErrors: async (symbol?: string) => {
    const res = await apiClient.get('/signals/errors', { params: { symbol } });
    return res.data;
  },
};

export const botApi = {
  getStatus: async (): Promise<BotStatusData> => {
    const res = await apiClient.get('/bot/status');
    return res.data;
  },
  setControl: async (action: 'START' | 'PAUSE' | 'STOP' | 'EMERGENCY_KILL') => {
    const res = await apiClient.post('/bot/control', { action });
    return res.data;
  },
  setMode: async (mode: 'paper' | 'live', confirmation?: string) => {
    const res = await apiClient.post('/bot/mode', { mode, confirmation });
    return res.data;
  },
  updateRisk: async (riskConfig: Record<string, any>) => {
    const res = await apiClient.post('/bot/risk-config', riskConfig);
    return res.data;
  },

  // ── NEW: Paper Trading Execution ──

  executeTrade: async (params: ExecuteTradeParams): Promise<TradeExecutionResult> => {
    const res = await apiClient.post('/bot/execute', params);
    return res.data;
  },

  closePosition: async (positionId: string, closePrice?: number): Promise<ClosePositionResult> => {
    const res = await apiClient.post(`/bot/close-position/${positionId}`, {
      close_price: closePrice,
    });
    return res.data;
  },

  getPortfolio: async () => {
    const res = await apiClient.get('/bot/portfolio');
    return res.data;
  },

  resetPortfolio: async () => {
    const res = await apiClient.post('/bot/portfolio/reset');
    return res.data;
  },

  getPositions: async () => {
    const res = await apiClient.get('/bot/positions');
    return res.data;
  },

  getPositionHistory: async (limit: number = 50) => {
    const res = await apiClient.get(`/bot/positions/history?limit=${limit}`);
    return res.data;
  },

  getActivityLogs: async (limit: number = 30) => {
    const res = await apiClient.get(`/bot/activity-logs?limit=${limit}`);
    return res.data;
  },

  getPriceFeedStatus: async (): Promise<PriceFeedStatus> => {
    const res = await apiClient.get('/bot/price-feed');
    return res.data;
  },

  // ── WebSocket Connection ──

  connectWebSocket: (
    userId?: string,
    onMessage?: (data: WsMessage) => void,
    onError?: (err: Event) => void,
    onClose?: () => void,
  ): WebSocket => {
    const wsBase = API_BASE_URL.replace(/^http/, 'ws');
    const url = userId
      ? `${wsBase}/bot/ws?user_id=${userId}`
      : `${wsBase}/bot/ws`;

    const ws = new WebSocket(url);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage?.(data);
      } catch {
        // ignore parse errors
      }
    };

    ws.onerror = (err) => {
      onError?.(err);
    };

    ws.onclose = () => {
      onClose?.();
    };

    return ws;
  },
};

export const modelsApi = {
  list: async (): Promise<{ count: number; models: ModelItem[] }> => {
    const res = await apiClient.get('/models');
    return res.data;
  },
  getDetails: async (modelId: string): Promise<{ model: ModelItem }> => {
    const res = await apiClient.get(`/models/${modelId}`);
    return res.data;
  },
  activate: async (modelId: string) => {
    const res = await apiClient.post(`/models/${modelId}/activate`);
    return res.data;
  },
  delete: async (modelId: string) => {
    const res = await apiClient.delete(`/models/${modelId}`);
    return res.data;
  },
  downloadUrl: (modelId: string): string => {
    return `${API_BASE_URL}/models/${modelId}/download`;
  },
};

export const trainingApi = {
  start: async (config: TrainingConfig): Promise<{ message: string; job: TrainingJobData }> => {
    const res = await apiClient.post('/training/start', config);
    return res.data;
  },
  listJobs: async (): Promise<{ jobs: TrainingJobData[] }> => {
    const res = await apiClient.get('/training/jobs');
    return res.data;
  },
  getActiveJob: async (): Promise<{ job: TrainingJobData | null }> => {
    const res = await apiClient.get('/training/active');
    return res.data;
  },
  getActive: async (): Promise<{ job: TrainingJobData | null }> => {
    const res = await apiClient.get('/training/active');
    return res.data;
  },
  getJobStatus: async (jobId: string): Promise<{ job: TrainingJobData }> => {
    const res = await apiClient.get(`/training/jobs/${jobId}`);
    return res.data;
  },
  getJob: async (jobId: string): Promise<{ job: TrainingJobData }> => {
    const res = await apiClient.get(`/training/jobs/${jobId}`);
    return res.data;
  },
  pauseJob: async (jobId: string) => {
    const res = await apiClient.post(`/training/jobs/${jobId}/pause`);
    return res.data;
  },
  pause: async (jobId: string) => {
    const res = await apiClient.post(`/training/jobs/${jobId}/pause`);
    return res.data;
  },
  resumeJob: async (jobId: string) => {
    const res = await apiClient.post(`/training/jobs/${jobId}/resume`);
    return res.data;
  },
  resume: async (jobId: string) => {
    const res = await apiClient.post(`/training/jobs/${jobId}/resume`);
    return res.data;
  },
  stopJob: async (jobId: string) => {
    const res = await apiClient.post(`/training/jobs/${jobId}/stop`);
    return res.data;
  },
  stop: async (jobId: string) => {
    const res = await apiClient.post(`/training/jobs/${jobId}/stop`);
    return res.data;
  },
  subscribeStream: (
    jobId: string,
    onMessage?: (event: any) => void,
    onError?: (err: any) => void
  ): EventSource => {
    const es = new EventSource(`${API_BASE_URL}/training/jobs/${jobId}/stream`);
    if (onMessage) {
      es.onmessage = (e) => {
        try {
          const parsed = JSON.parse(e.data);
          onMessage(parsed);
        } catch {
          onMessage(e.data);
        }
      };
    }
    if (onError) {
      es.onerror = (err) => onError(err);
    }
    return es;
  },
};

export const backtestApi = {
  run: async (config: BacktestConfig): Promise<BacktestResult> => {
    const res = await apiClient.post('/backtest/run', config);
    return res.data;
  },
};


export const tradesApi = {
  execute: async (tradeData: any): Promise<any> => {
    const res = await apiClient.post('/trades/execute', tradeData);
    return res.data;
  }
};

