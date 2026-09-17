import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { Eye, EyeOff, Lock, Mail, User, ArrowRight, CheckCircle2, AlertCircle, Activity, ShieldCheck } from 'lucide-react';
import { useAuth } from '../../auth/AuthContext';

export const RegisterPage: React.FC = () => {
  const { signUp, configured } = useAuth();

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [registered, setRegistered] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Please complete all required fields.');
      return;
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters long.');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    setError(null);

    const { error: authErr } = await signUp(email, password, fullName);
    setLoading(false);

    if (authErr) {
      setError(authErr.message || 'Failed to create account.');
    } else {
      setRegistered(true);
    }
  };

  return (
    <div className="min-h-screen flex flex-col justify-center items-center bg-[var(--bg)] px-4 py-12">
      {/* Wordmark */}
      <div className="text-center mb-8">
        <NavLink to="/" className="inline-block no-underline">
          <span className="font-mono font-bold text-xl uppercase tracking-widest text-[var(--text-primary)]">
            Market<span className="text-[var(--accent-fresh)]">Flux</span>
          </span>
        </NavLink>
        <p className="text-xs text-[var(--text-muted)] font-mono mt-2">
          Institutional Algorithmic Trading Intelligence
        </p>
      </div>

      {/* Auth Card */}
      <div className="w-full max-w-md p-8 md:p-10 rounded-2xl bg-[var(--surface)] border border-[var(--border)] shadow-xl relative overflow-hidden">
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-[var(--accent-fresh)] to-transparent opacity-70" />

        {registered ? (
          <div className="text-center py-6">
            <div className="w-14 h-14 rounded-full bg-[var(--green-subtle)] text-[var(--accent-fresh)] flex items-center justify-center mx-auto mb-4">
              <CheckCircle2 size={30} />
            </div>
            <h2 className="font-display text-3xl text-[var(--text-primary)] mb-2">
              Registration Successful
            </h2>
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed mb-6">
              Your trader account has been initialized. If confirmation is enabled on your Supabase instance, please check your inbox. Otherwise, you can log in immediately.
            </p>
            <NavLink to="/login" className="btn btn-primary w-full py-3 text-xs">
              Proceed to Sign In <ArrowRight size={14} />
            </NavLink>
          </div>
        ) : (
          <>
            <div className="mb-6">
              <h1 className="font-display text-3xl text-[var(--text-primary)] tracking-tight">
                Create Account
              </h1>
              <p className="text-xs text-[var(--text-secondary)] mt-1">
                Gain access to automated execution, SMC market models, and institutional backtesting.
              </p>
            </div>

            {!configured && (
              <div className="mb-6 p-3.5 rounded-lg bg-[var(--amber-subtle)] border border-[var(--amber)]/30 text-xs text-[var(--amber)] flex items-start gap-2.5">
                <AlertCircle size={16} className="shrink-0 mt-0.5" />
                <span>
                  Supabase credentials not configured in <code className="font-mono text-[11px]">.env</code>.
                </span>
              </div>
            )}

            {error && (
              <div className="mb-6 p-3.5 rounded-lg bg-[var(--red-subtle)] border border-[var(--red)]/40 text-xs text-[var(--red)] flex items-start gap-2.5 font-mono">
                <AlertCircle size={16} className="shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-meta text-[var(--text-muted)] font-mono mb-1.5">
                  Full Name / Trading Pseudonym
                </label>
                <div className="relative">
                  <input
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Alex Vance"
                    className="input-editorial pl-10 text-sm"
                  />
                  <User size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
                </div>
              </div>

              <div>
                <label className="block text-meta text-[var(--text-muted)] font-mono mb-1.5">
                  Email Address
                </label>
                <div className="relative">
                  <input
                    type="email"
                    required
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="trader@marketflux.ai"
                    className="input-editorial pl-10 text-sm font-mono"
                  />
                  <Mail size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
                </div>
              </div>

              <div>
                <label className="block text-meta text-[var(--text-muted)] font-mono mb-1.5">
                  Password
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    autoComplete="new-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Min 6 characters"
                    className="input-editorial pl-10 pr-10 text-sm font-mono"
                  />
                  <Lock size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-meta text-[var(--text-muted)] font-mono mb-1.5">
                  Confirm Password
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Repeat password"
                    className="input-editorial pl-10 text-sm font-mono"
                  />
                  <Lock size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
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
                      Creating Account...
                    </span>
                  ) : (
                    <span className="flex items-center justify-center gap-2">
                      Create Trader Account <ArrowRight size={14} />
                    </span>
                  )}
                </button>
              </div>
            </form>

            <div className="mt-8 pt-6 border-t border-[var(--border)] text-center text-xs text-[var(--text-secondary)]">
              Already have an account?{' '}
              <NavLink to="/login" className="text-[var(--accent-fresh)] font-semibold hover:underline">
                Sign In
              </NavLink>
            </div>
          </>
        )}
      </div>

      <div className="mt-8 flex items-center gap-2 text-[11px] text-[var(--text-muted)] font-mono">
        <ShieldCheck size={14} className="text-[var(--accent-fresh)]" />
        Zero Third-Party Tracking · Supabase Row-Level Security Enforced
      </div>
    </div>
  );
};
