import React, { useState } from 'react';
import { HelpCircle } from 'lucide-react';

export const TERMS_GLOSSARY: Record<string, { title: string; explanation: string }> = {
  'R:R': {
    title: 'Risk / Reward Ratio',
    explanation: 'For every $1 of planned risk, the strategy targets $X of potential reward. E.g. 2:1 targets $2 profit for every $1 risked.',
  },
  'RR': {
    title: 'Risk / Reward Ratio',
    explanation: 'For every $1 of planned risk, the strategy targets $X of potential reward.',
  },
  'TP': {
    title: 'Take Profit',
    explanation: 'An automatic order that closes your trade at a profit once the market reaches a specified target price.',
  },
  'SL': {
    title: 'Stop Loss',
    explanation: 'A safety order that automatically closes a trade at a set price to prevent larger losses if the market moves against you.',
  },
  'ATR': {
    title: 'Average True Range',
    explanation: 'Measures market volatility. Higher ATR means larger price swings, helping set wider stop losses.',
  },
  'SMC': {
    title: 'Smart Money Concepts',
    explanation: 'Trading strategies that look for institutional footprints: liquidity sweeps, order blocks, and imbalance zones.',
  },
  'ICT': {
    title: 'Inner Circle Trader',
    explanation: 'A methodology focusing on fair value gaps (FVG), market structure shifts, and institutional trading sessions.',
  },
  'RSI': {
    title: 'Relative Strength Index',
    explanation: 'A momentum gauge from 0 to 100. Above 70 suggests overbought (stretched up), below 30 suggests oversold.',
  },
  'MACD': {
    title: 'Moving Average Convergence Divergence',
    explanation: 'Shows the relationship between two moving averages to spot changes in momentum and trend direction.',
  },
  'XGB': {
    title: 'XGBoost Machine Learning',
    explanation: 'Extreme Gradient Boosting: an advanced algorithm that combines hundreds of decision trees to forecast price direction.',
  },
  'MDD': {
    title: 'Maximum Drawdown',
    explanation: 'The largest peak-to-trough drop in account balance. Measures worst-case historical portfolio decline.',
  },
  'PnL': {
    title: 'Profit & Loss',
    explanation: 'Total financial gain or loss realized or currently open in your trades.',
  },
  'Drawdown': {
    title: 'Drawdown',
    explanation: 'The percentage decline from an account’s peak equity down to its lowest point during a trading period.',
  },
  'Sharpe': {
    title: 'Sharpe Ratio',
    explanation: 'Measures return relative to risk taken. A Sharpe above 1.0 is considered good, above 2.0 is excellent.',
  },
  'Paper Mode': {
    title: 'Paper Trading (Simulation)',
    explanation: 'Trading in a risk-free sandbox environment using simulated money. No real funds are at risk.',
  },
};

interface TermTooltipProps {
  term: string;
  children?: React.ReactNode;
}

export const TermTooltip: React.FC<TermTooltipProps> = ({ term, children }) => {
  const [open, setOpen] = useState(false);
  const info = TERMS_GLOSSARY[term] || { title: term, explanation: 'Financial or machine learning metric.' };

  return (
    <span className="relative inline-flex items-center gap-1 group cursor-help">
      <span className="border-b border-dotted border-[var(--text-muted)] group-hover:border-[var(--accent-fresh)]">
        {children || term}
      </span>
      <button
        type="button"
        className="text-[var(--text-muted)] hover:text-[var(--accent-fresh)] p-0.5"
        onClick={(e) => {
          e.stopPropagation();
          setOpen(!open);
        }}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        aria-label={`What is ${term}?`}
      >
        <HelpCircle size={12} />
      </button>

      {open && (
        <div
          className="absolute z-50 bottom-full mb-2 left-1/2 -translate-x-1/2 w-64 p-3 rounded-lg shadow-xl text-left pointer-events-none transition-all"
          style={{
            backgroundColor: 'var(--surface-hover)',
            border: '1px solid var(--border-mid)',
            color: 'var(--text-primary)',
          }}
        >
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--accent-fresh)] mb-1">
            {info.title}
          </p>
          <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
            {info.explanation}
          </p>
        </div>
      )}
    </span>
  );
};
