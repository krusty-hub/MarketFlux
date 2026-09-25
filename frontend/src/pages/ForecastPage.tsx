import React, { useState, useEffect } from 'react';
import { Play, Activity, TrendingUp, TrendingDown, Target, Shield, Check, X } from 'lucide-react';
import { forecastApi, tradesApi, modelsApi, type ModelItem } from '../services/api';
import { useToast } from '../components/Toast';
import { useAuth } from '../auth/AuthContext';

export const ForecastPage: React.FC = () => {
  const { user } = useAuth();
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [models, setModels] = useState<ModelItem[]>([]);
  
  // Form State
  const [formData, setFormData] = useState({
    symbol: 'BTCUSDT',
    historical_period: 1000,
    timeframe: '5m',
    model_id: '',
    balance: 10000.0,
    risk_per_trade_pct: 1.5,
    slippage_pct: 0.02,
    min_confidence_pct: 30.0
  });

  const [analysisResult, setAnalysisResult] = useState<any>(null);
  const [isExecuting, setIsExecuting] = useState(false);

  useEffect(() => {
    // Load available models from the registry
    modelsApi.list().then((res) => {
      const activeModels = res.models || [];
      setModels(activeModels);
      if (activeModels.length > 0) {
        // Find active model if any, else pick first
        const active = activeModels.find((m: ModelItem) => m.is_active);
        setFormData(f => ({ ...f, model_id: active ? active.id : activeModels[0].id }));
      }
    }).catch(err => {
      console.error("Failed to load models", err);
      toast("Failed to connect to Model Registry", "error");
    });
  }, []);

  const handleRunAnalysis = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setAnalysisResult(null);
    try {
      const res = await forecastApi.analyze(formData);
      setAnalysisResult(res);
      if (res.status === 'REJECTED') {
        toast(`Analysis Rejected: ${res.message}`, "info");
      } else {
        toast("Analysis complete. Setup generated.", "success");
      }
    } catch (err: any) {
      toast(err?.response?.data?.detail || "AI Analysis failed", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleExecuteTrade = async () => {
    if (!analysisResult?.setup || !user) return;
    setIsExecuting(true);
    try {
      const { setup } = analysisResult;
      await tradesApi.execute({
        user_id: user.id,
        symbol: setup.symbol,
        timeframe: setup.timeframe,
        direction: setup.direction,
        entry_price: setup.entry_price,
        stop_loss: setup.stop_loss,
        take_profit: setup.take_profit,
        position_size: setup.position_size,
        ai_confidence: setup.confidence,
        model_id: setup.model_id
      });
      toast("Trade successfully pushed to the Bot Engine!", "success");
      setAnalysisResult(null);
    } catch (err: any) {
      toast(err?.response?.data?.detail || "Trade execution failed", "error");
    } finally {
      setIsExecuting(false);
    }
  };

  return (
    <div className="page-main">
      <div className="content-container">
        
        {/* HEADER */}
        <section className="page-header pt-12 pb-8 border-b border-[var(--border)]">
          <p className="text-meta text-[var(--accent-fresh)] mb-3 font-mono">
            Unified AI Analysis Engine
          </p>
          <h1 className="font-display text-hero text-[var(--text-primary)] mb-3">
            AI MODEL OUTLOOK.
          </h1>
          <p className="text-sm text-[var(--text-secondary)] max-w-xl">
            Configure risk parameters and query the active ML model to generate probability-scored trade setups.
          </p>
        </section>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 my-8">
          
          {/* LEFT: Configuration Form */}
          <div className="lg:col-span-5 space-y-6">
            <div className="p-6 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
              <h2 className="font-mono text-sm uppercase text-[var(--text-primary)] mb-6">Analysis Parameters</h2>
              
              <form onSubmit={handleRunAnalysis} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">Market</label>
                    <select
                      className="form-input"
                      value={formData.symbol}
                      onChange={(e) => setFormData({...formData, symbol: e.target.value})}
                    >
                      <option value="BTCUSDT">BTC/USDT</option>
                      <option value="ETHUSDT">ETH/USDT</option>
                      <option value="EURUSD">EUR/USD</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">Timeframe</label>
                    <select
                      className="form-input"
                      value={formData.timeframe}
                      onChange={(e) => setFormData({...formData, timeframe: e.target.value})}
                    >
                      <option value="1m">1 Minute</option>
                      <option value="5m">5 Minutes</option>
                      <option value="15m">15 Minutes</option>
                      <option value="1h">1 Hour</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">Historical Context (Bars)</label>
                  <input
                    type="number"
                    className="form-input"
                    value={formData.historical_period}
                    onChange={(e) => setFormData({...formData, historical_period: parseInt(e.target.value) || 1000})}
                  />
                </div>

                <div>
                  <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">Strategy Model</label>
                  <select
                    className="form-input font-mono text-xs"
                    value={formData.model_id}
                    onChange={(e) => setFormData({...formData, model_id: e.target.value})}
                  >
                    {models.map(m => (
                      <option key={m.id} value={m.id}>{m.filename} {m.is_active ? '(Active)' : ''}</option>
                    ))}
                  </select>
                </div>

                <div className="pt-4 border-t border-[var(--border)]">
                  <h3 className="text-xs font-mono text-[var(--text-primary)] uppercase mb-4">Risk Controls</h3>
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div>
                      <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">Base Capital ($)</label>
                      <input
                        type="number"
                        className="form-input"
                        step="0.01"
                        value={formData.balance}
                        onChange={(e) => setFormData({...formData, balance: parseFloat(e.target.value) || 10000})}
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">Risk Per Trade (%)</label>
                      <input
                        type="number"
                        className="form-input"
                        step="0.1"
                        value={formData.risk_per_trade_pct}
                        onChange={(e) => setFormData({...formData, risk_per_trade_pct: parseFloat(e.target.value) || 1.5})}
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">Simulated Slippage (%)</label>
                      <input
                        type="number"
                        className="form-input"
                        step="0.01"
                        value={formData.slippage_pct}
                        onChange={(e) => setFormData({...formData, slippage_pct: parseFloat(e.target.value) || 0.02})}
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">Min Confidence (%)</label>
                      <input
                        type="number"
                        className="form-input"
                        step="1"
                        value={formData.min_confidence_pct}
                        onChange={(e) => setFormData({...formData, min_confidence_pct: parseFloat(e.target.value) || 30})}
                      />
                    </div>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading || !formData.model_id}
                  className="btn btn-primary w-full mt-6 flex items-center justify-center gap-2"
                >
                  {loading ? <Activity className="animate-spin" size={16} /> : <Play size={16} />}
                  Run AI Analysis
                </button>
              </form>
            </div>
          </div>

          {/* RIGHT: Results Panel */}
          <div className="lg:col-span-7">
            {!analysisResult && !loading && (
              <div className="h-full flex flex-col items-center justify-center p-12 text-center border border-dashed border-[var(--border-mid)] rounded-xl bg-[var(--surface)] opacity-50">
                <Activity size={32} className="text-[var(--text-muted)] mb-4" />
                <p className="font-mono text-sm text-[var(--text-secondary)]">Awaiting Analysis</p>
                <p className="text-xs text-[var(--text-muted)] mt-2">Configure parameters and run the engine.</p>
              </div>
            )}

            {loading && (
              <div className="h-full flex flex-col items-center justify-center p-12 text-center rounded-xl bg-[var(--surface)] border border-[var(--border)]">
                <Activity size={32} className="text-[var(--accent-fresh)] animate-pulse mb-4" />
                <p className="font-mono text-sm text-[var(--text-primary)]">Crunching Chart Data...</p>
              </div>
            )}

            {analysisResult && analysisResult.status === 'REJECTED' && (
              <div className="h-full flex flex-col items-center justify-center p-12 text-center rounded-xl bg-[var(--bg)] border border-[var(--amber)] border-opacity-50">
                <X size={32} className="text-[var(--amber)] mb-4" />
                <h3 className="font-display text-2xl text-[var(--amber)] mb-2">Setup Rejected</h3>
                <p className="text-sm text-[var(--text-secondary)] mb-4">{analysisResult.message}</p>
                <div className="font-mono text-xs bg-[var(--surface-hover)] px-4 py-2 rounded-full border border-[var(--border)]">
                  Confidence: {analysisResult.confidence}% / Required: {formData.min_confidence_pct}%
                </div>
              </div>
            )}

            {analysisResult && analysisResult.status === 'ACCEPTED' && analysisResult.setup && (
              <div className="rounded-xl border border-[var(--accent-fresh)] bg-[var(--surface)] overflow-hidden shadow-lg shadow-[var(--accent-fresh)]/10">
                <div className="bg-[var(--accent-fresh)]/10 border-b border-[var(--accent-fresh)]/30 p-6 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {analysisResult.setup.direction === 'LONG' ? (
                      <TrendingUp size={24} className="text-[var(--accent-fresh)]" />
                    ) : (
                      <TrendingDown size={24} className="text-[var(--red)]" />
                    )}
                    <div>
                      <span className="text-meta text-[var(--text-primary)] font-semibold uppercase block">
                        {analysisResult.setup.direction} {analysisResult.setup.symbol}
                      </span>
                      <span className="font-mono text-xs text-[var(--text-secondary)]">
                        {analysisResult.setup.timeframe} · Model: {analysisResult.setup.model_id}
                      </span>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="text-meta text-[var(--text-muted)] block mb-1">AI Confidence</span>
                    <span className="font-mono text-2xl font-bold text-[var(--accent-fresh)]">
                      {analysisResult.setup.confidence}%
                    </span>
                  </div>
                </div>

                <div className="p-6">
                  <div className="grid grid-cols-2 gap-6 mb-8">
                    <div className="p-4 rounded border border-[var(--border)] bg-[var(--bg)]">
                      <span className="text-xs font-mono text-[var(--text-muted)] block mb-1">Entry Price</span>
                      <span className="font-mono text-lg font-semibold text-[var(--text-primary)]">
                        {analysisResult.setup.entry_price}
                      </span>
                    </div>
                    <div className="p-4 rounded border border-[var(--border)] bg-[var(--bg)]">
                      <span className="text-xs font-mono text-[var(--text-muted)] block mb-1">Position Size</span>
                      <span className="font-mono text-lg font-semibold text-[var(--text-primary)]">
                        {analysisResult.setup.position_size}
                      </span>
                    </div>
                  </div>

                  <div className="space-y-4 mb-8 relative">
                    {/* Visual Target Lines */}
                    <div className="flex justify-between items-center text-sm font-mono p-3 rounded bg-[var(--green-subtle)]/5 border border-[var(--accent-fresh)]/30">
                      <span className="text-[var(--accent-fresh)] flex items-center gap-2">
                        <Target size={14}/> Take Profit (2R)
                      </span>
                      <span className="text-[var(--text-primary)] font-semibold">{analysisResult.setup.take_profit}</span>
                    </div>
                    
                    <div className="flex justify-between items-center text-sm font-mono p-3 rounded bg-[var(--red)]/5 border border-[var(--red)]/30">
                      <span className="text-[var(--red)] flex items-center gap-2">
                        <Shield size={14}/> Stop Loss (1R)
                      </span>
                      <span className="text-[var(--text-primary)] font-semibold">{analysisResult.setup.stop_loss}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-4 pt-6 border-t border-[var(--border)]">
                    <button
                      onClick={handleExecuteTrade}
                      disabled={isExecuting}
                      className="btn btn-primary flex-1 flex items-center justify-center gap-2"
                    >
                      {isExecuting ? <Activity size={16} className="animate-spin" /> : <Check size={16} />}
                      Push to Bot Engine (Execute)
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
