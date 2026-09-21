import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { Mail, ArrowRight, ArrowLeft, Activity, CheckCircle2, AlertCircle } from 'lucide-react';
import { useAuth } from '../../auth/AuthContext';

export const ForgotPasswordPage: React.FC = () => {
  const { resetPassword, configured } = useAuth();

  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) {
      setError('Please enter your account email address.');
      return;
    }

    setLoading(true);
    setError(null);

    const { error: resetErr } = await resetPassword(email);
    setLoading(false);

    if (resetErr) {
      setError(resetErr.message || 'Failed to send password reset email.');
    } else {
      setSubmitted(true);
    }
  };

  return (
    <div className="min-h-screen flex flex-col justify-center items-center bg-[var(--bg)] px-4 py-12">
      <div className="text-center mb-8">
        <NavLink to="/" className="inline-block no-underline">
          <span className="font-mono font-bold text-xl uppercase tracking-widest text-[var(--text-primary)]">
            Market<span className="text-[var(--accent-fresh)]">Flux</span>
          </span>
        </NavLink>
        <p className="text-xs text-[var(--text-muted)] font-mono mt-2">
          Security &amp; Account Recovery
        </p>
      </div>

      <div className="w-full max-w-md p-8 md:p-10 rounded-2xl bg-[var(--surface)] border border-[var(--border)] shadow-xl relative overflow-hidden">
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-[var(--accent-fresh)] to-transparent opacity-70" />

        {submitted ? (
          <div className="text-center py-6">
            <div className="w-14 h-14 rounded-full bg-[var(--green-subtle)] text-[var(--accent-fresh)] flex items-center justify-center mx-auto mb-4">
              <CheckCircle2 size={30} />
            </div>
            <h2 className="font-display text-3xl text-[var(--text-primary)] mb-2">
              Instructions Dispatched
            </h2>
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed mb-6">
              If an account exists for <span className="font-mono font-semibold text-[var(--text-primary)]">{email}</span>, a secure password recovery link has been sent to that address.
            </p>
            <NavLink to="/login" className="btn btn-secondary w-full py-3 text-xs">
              <ArrowLeft size={14} /> Back to Sign In
            </NavLink>
          </div>
        ) : (
          <>
            <div className="mb-6">
              <h1 className="font-display text-3xl text-[var(--text-primary)] tracking-tight">
                Reset Password
              </h1>
              <p className="text-xs text-[var(--text-secondary)] mt-1">
                Enter your account email to receive a password reset link.
              </p>
            </div>

            {error && (
              <div className="mb-6 p-3.5 rounded-lg bg-[var(--red-subtle)] border border-[var(--red)]/40 text-xs text-[var(--red)] flex items-start gap-2.5 font-mono">
                <AlertCircle size={16} className="shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-meta text-[var(--text-muted)] font-mono mb-1.5">
                  Account Email
                </label>
                <div className="relative">
                  <input
                    type="email"
                    required
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="name@firm.com"
                    className="input-editorial pl-10 text-sm font-mono"
                  />
                  <Mail size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
                </div>
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  disabled={loading || !configured}
                  className="btn btn-primary w-full py-3 text-xs"
                >
                  {loading ? (
                    <span className="flex items-center gap-2">
                      <Activity size={14} className="animate-spin text-[var(--btn-text)]" />
                      Sending Link...
                    </span>
                  ) : (
                    <span className="flex items-center justify-center gap-2">
                      Send Reset Instructions <ArrowRight size={14} />
                    </span>
                  )}
                </button>
              </div>
            </form>

            <div className="mt-8 pt-6 border-t border-[var(--border)] text-center text-xs text-[var(--text-secondary)]">
              Remember your credentials?{' '}
              <NavLink to="/login" className="text-[var(--accent-fresh)] font-semibold hover:underline">
                Return to Sign In
              </NavLink>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
