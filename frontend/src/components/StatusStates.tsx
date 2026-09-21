import React from 'react';
import { WifiOff, AlertTriangle, Inbox, RefreshCw, Loader2 } from 'lucide-react';

interface StateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export const OfflineState: React.FC<StateProps> = ({
  title = 'Connection Unavailable',
  message = "MarketFlux can't reach the backend service right now. Make sure the backend server is running.",
  onRetry,
  className = '',
}) => {
  return (
    <div className={`p-8 md:p-12 text-center rounded-xl border border-[var(--border)] bg-[var(--surface)] my-6 ${className}`}>
      <div className="w-12 h-12 rounded-full bg-[var(--red-subtle)] text-[var(--red)] flex items-center justify-center mx-auto mb-4">
        <WifiOff size={22} />
      </div>
      <h3 className="font-display text-2xl md:text-3xl text-[var(--text-primary)] mb-2 tracking-tight">
        {title}
      </h3>
      <p className="text-sm text-[var(--text-secondary)] max-w-md mx-auto mb-6 leading-relaxed">
        {message}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="btn btn-secondary inline-flex items-center gap-2 text-xs"
        >
          <RefreshCw size={13} />
          Retry Connection
        </button>
      )}
    </div>
  );
};

export const ErrorState: React.FC<StateProps> = ({
  title = 'Data Unavailable',
  message = 'An unexpected error occurred while communicating with the data engine.',
  onRetry,
  className = '',
}) => {
  return (
    <div className={`p-8 md:p-12 text-center rounded-xl border border-[var(--border)] bg-[var(--surface)] my-6 ${className}`}>
      <div className="w-12 h-12 rounded-full bg-[var(--amber-subtle)] text-[var(--amber)] flex items-center justify-center mx-auto mb-4">
        <AlertTriangle size={22} />
      </div>
      <h3 className="font-display text-2xl md:text-3xl text-[var(--text-primary)] mb-2 tracking-tight">
        {title}
      </h3>
      <p className="text-sm text-[var(--text-secondary)] max-w-md mx-auto mb-6 leading-relaxed">
        {message}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="btn btn-secondary inline-flex items-center gap-2 text-xs"
        >
          <RefreshCw size={13} />
          Retry Action
        </button>
      )}
    </div>
  );
};

export const EmptyState: React.FC<StateProps & { actionLabel?: string; onAction?: () => void }> = ({
  title = 'No Data Available',
  message = 'There are no active records or signals to display at this time.',
  actionLabel,
  onAction,
  className = '',
}) => {
  return (
    <div className={`p-8 md:p-12 text-center rounded-xl border border-[var(--border)] bg-[var(--surface)] my-6 ${className}`}>
      <div className="w-12 h-12 rounded-full bg-[var(--accent-subtle)] text-[var(--accent-fresh)] flex items-center justify-center mx-auto mb-4">
        <Inbox size={22} />
      </div>
      <h3 className="font-display text-2xl md:text-3xl text-[var(--text-primary)] mb-2 tracking-tight">
        {title}
      </h3>
      <p className="text-sm text-[var(--text-secondary)] max-w-md mx-auto mb-6 leading-relaxed">
        {message}
      </p>
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          className="btn btn-primary inline-flex items-center gap-2 text-xs"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
};

export const LoadingState: React.FC<{ message?: string; className?: string }> = ({
  message = 'Connecting to MarketFlux data stream...',
  className = '',
}) => {
  return (
    <div className={`p-12 text-center my-6 ${className}`}>
      <Loader2 size={24} className="animate-spin text-[var(--accent-fresh)] mx-auto mb-3" />
      <p className="text-xs uppercase tracking-widest text-[var(--text-muted)] font-mono">
        {message}
      </p>
    </div>
  );
};
