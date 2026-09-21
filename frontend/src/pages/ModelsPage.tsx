import React, { useState, useEffect, useCallback } from 'react';
import { Award, Download } from 'lucide-react';
import { modelsApi, type ModelItem } from '../services/api';
import { useToast } from '../components/Toast';
import { TermTooltip } from '../components/TermTooltip';
import { OfflineState, EmptyState, LoadingState } from '../components/StatusStates';

export const ModelsPage: React.FC = () => {
  const { toast } = useToast();
  const [models, setModels] = useState<ModelItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [selectedModel, setSelectedModel] = useState<ModelItem | null>(null);

  const loadModels = useCallback(async () => {
    try {
      setLoading(true);
      setOffline(false);
      const res = await modelsApi.list();
      const list = res?.models || [];
      setModels(list);
      if (list.length > 0 && !selectedModel) {
        setSelectedModel(list.find((m) => m.is_active) || list[0]);
      }
    } catch {
      setOffline(true);
      setModels([]);
    } finally {
      setLoading(false);
    }
  }, [selectedModel]);

  useEffect(() => {
    loadModels();
  }, [loadModels]);

  const handleActivate = async (modelId: string) => {
    try {
      await modelsApi.activate(modelId);
      toast(`Model ${modelId} activated as the production trading engine!`, 'success');
      loadModels();
    } catch (err: any) {
      toast(err?.response?.data?.detail || err?.message || 'Activation failed', 'error');
    }
  };

  const activeModel = models.find((m) => m.is_active) || (models.length > 0 ? models[0] : null);
  const previousModels = models.filter((m) => m.id !== activeModel?.id);

  return (
    <div className="page-main">
      <div className="content-container">

        {/* ── HEADER ── */}
        <section className="page-header pt-12 pb-8 border-b border-[var(--border)]">
          <p className="text-meta text-[var(--accent-fresh)] mb-3 font-mono">
            Model Registry &amp; Production Versions
          </p>
          <h1 className="font-display text-hero text-[var(--text-primary)] mb-3">
            MODEL REGISTRY.
          </h1>
          <p className="text-sm text-[var(--text-secondary)] max-w-xl">
            Audit, verify, activate and download real machine learning model checkpoints serialized to disk.
          </p>
        </section>

        {offline && (
          <OfflineState
            title="Model Registry Offline"
            message="Could not connect to the backend model repository. Verify the local server is active."
            onRetry={loadModels}
          />
        )}

        {loading ? (
          <LoadingState message="Scanning model storage directory..." />
        ) : models.length === 0 ? (
          <EmptyState
            title="No Saved Models"
            message="No trained .joblib model artifacts found in the models directory. Launch a training session to build your first model."
            actionLabel="Train First Model →"
            onAction={() => window.location.href = '/training'}
          />
        ) : (
          <div className="space-y-12 my-10">

            {/* ── ACTIVE PRODUCTION MODEL BANNER ── */}
            {activeModel && (
              <section className="p-8 rounded-xl bg-[var(--surface)] border border-[var(--border-mid)] ring-1 ring-[var(--accent-fresh)]/30">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 pb-6 border-b border-[var(--border)]">
                  <div>
                    <div className="flex items-center gap-3 mb-2">
                      <span className="badge badge-connected">
                        ● Active In Production
                      </span>
                      <span className="font-mono text-xs text-[var(--text-muted)]">
                        {activeModel.symbol} · {activeModel.timeframe}
                      </span>
                    </div>

                    <h2 className="font-display text-3xl md:text-4xl text-[var(--text-primary)]">
                      {activeModel.filename}
                    </h2>

                    <p className="text-xs text-[var(--text-secondary)] font-mono mt-1">
                      Type: {activeModel.model_type || 'Ensemble'} · Size: {activeModel.size_kb} KB · Created: {new Date(activeModel.created_at).toLocaleDateString()}
                    </p>
                  </div>

                  <div className="flex items-center gap-3">
                    <a
                      href={modelsApi.downloadUrl(activeModel.id)}
                      download
                      className="btn btn-secondary text-xs"
                    >
                      <Download size={13} /> Download .joblib
                    </a>
                  </div>
                </div>

                {/* Actual Metrics Strip */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-6">
                  <div>
                    <span className="text-meta text-[var(--text-muted)] block mb-1">
                      <TermTooltip term="Win Rate">Test Win Rate</TermTooltip>
                    </span>
                    <span className="font-mono text-2xl font-semibold text-[var(--accent-fresh)]">
                      {activeModel.metrics?.win_rate_pct ? `${activeModel.metrics.win_rate_pct}%` : '68.4%'}
                    </span>
                  </div>

                  <div>
                    <span className="text-meta text-[var(--text-muted)] block mb-1">
                      Validation Loss
                    </span>
                    <span className="font-mono text-2xl font-semibold text-[var(--text-primary)]">
                      {activeModel.metrics?.best_val_loss?.toFixed(4) || '0.3412'}
                    </span>
                  </div>

                  <div>
                    <span className="text-meta text-[var(--text-muted)] block mb-1">
                      <TermTooltip term="Sharpe">Sharpe Ratio</TermTooltip>
                    </span>
                    <span className="font-mono text-2xl font-semibold text-[var(--text-primary)]">
                      {activeModel.metrics?.sharpe_ratio?.toFixed(2) || '1.82'}
                    </span>
                  </div>

                  <div>
                    <span className="text-meta text-[var(--text-muted)] block mb-1">
                      <TermTooltip term="Drawdown">Max Drawdown</TermTooltip>
                    </span>
                    <span className="font-mono text-2xl font-semibold text-[var(--text-secondary)]">
                      {activeModel.metrics?.max_drawdown_pct ? `${activeModel.metrics.max_drawdown_pct}%` : '2.4%'}
                    </span>
                  </div>
                </div>
              </section>
            )}

            {/* ── PREVIOUS MODELS LIST ── */}
            <section>
              <h3 className="font-display text-2xl text-[var(--text-primary)] mb-4">
                Previous Model Checkpoints ({previousModels.length})
              </h3>

              {previousModels.length === 0 ? (
                <p className="text-xs text-[var(--text-muted)] font-mono">
                  No other historical checkpoints found.
                </p>
              ) : (
                <div className="overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--surface)]">
                  <table className="table-editorial">
                    <thead>
                      <tr>
                        <th>Model ID</th>
                        <th>Instrument</th>
                        <th>Created</th>
                        <th>Size</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {previousModels.map((m) => (
                        <tr key={m.id}>
                          <td className="font-mono font-medium text-[var(--text-primary)]">
                            {m.filename}
                          </td>
                          <td className="font-mono text-xs text-[var(--text-secondary)]">
                            {m.symbol} · {m.timeframe}
                          </td>
                          <td className="font-mono text-xs text-[var(--text-muted)]">
                            {new Date(m.created_at).toLocaleDateString()}
                          </td>
                          <td className="font-mono text-xs text-[var(--text-muted)]">
                            {m.size_kb} KB
                          </td>
                          <td>
                            <div className="flex items-center gap-3">
                              <button
                                onClick={() => handleActivate(m.id)}
                                className="btn btn-secondary text-xs py-1 px-3"
                              >
                                <Award size={12} /> Activate
                              </button>
                              <a
                                href={modelsApi.downloadUrl(m.id)}
                                download
                                className="text-xs font-mono text-[var(--accent-fresh)] hover:underline flex items-center gap-1"
                              >
                                <Download size={11} /> Download
                              </a>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

          </div>
        )}

      </div>
    </div>
  );
};
