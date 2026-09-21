import React, { useState } from 'react';
import { X } from 'lucide-react';

interface LiveConfirmationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (code: string) => void;
}

export const LiveConfirmationModal: React.FC<LiveConfirmationModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
}) => {
  const [inputVal, setInputVal] = useState('');
  const [error, setError]       = useState('');

  if (!isOpen) return null;

  const handleConfirm = () => {
    if (inputVal.trim() !== 'CONFIRM LIVE') {
      setError('Type exactly "CONFIRM LIVE" to proceed.');
      return;
    }
    setError('');
    onConfirm(inputVal.trim());
    onClose();
    setInputVal('');
  };

  const handleClose = () => {
    onClose();
    setInputVal('');
    setError('');
  };

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div className="modal">
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            marginBottom: 28,
          }}
        >
          <div>
            <p className="text-meta" style={{ color: 'var(--red)', marginBottom: 8 }}>
              Critical Warning
            </p>
            <h2 id="modal-title" style={{ fontSize: 20, fontWeight: 500, color: 'var(--text-primary)', margin: 0 }}>
              Enable Live Trading
            </h2>
          </div>
          <button
            onClick={handleClose}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--text-muted)',
              padding: 0,
              marginTop: 2,
            }}
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        {/* Warning copy */}
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.65, marginBottom: 24 }}>
          Enabling live trading will route real capital to your configured broker.
          Confirm that risk limits, stop loss thresholds and position sizes are
          calibrated before proceeding.
        </p>

        {/* Confirmation input */}
        <div style={{ marginBottom: 20 }}>
          <label
            htmlFor="confirm-input"
            className="field-label"
            style={{ marginBottom: 10 }}
          >
            Type <span style={{ fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-primary)' }}>CONFIRM LIVE</span> to proceed
          </label>
          <input
            id="confirm-input"
            type="text"
            value={inputVal}
            onChange={(e) => {
              setInputVal(e.target.value);
              setError('');
            }}
            placeholder="CONFIRM LIVE"
            className="field-input font-mono"
            autoFocus
            onKeyDown={(e) => e.key === 'Enter' && handleConfirm()}
          />
          {error && (
            <p style={{ marginTop: 8, fontSize: 12, color: 'var(--red)' }}>{error}</p>
          )}
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
          <button className="btn btn-ghost btn-sm" onClick={handleClose}>
            Cancel
          </button>
          <button
            className="btn btn-danger btn-sm"
            onClick={handleConfirm}
            disabled={inputVal.trim() !== 'CONFIRM LIVE'}
            style={{ opacity: inputVal.trim() !== 'CONFIRM LIVE' ? 0.35 : 1 }}
          >
            Enable Live
          </button>
        </div>
      </div>
    </div>
  );
};
