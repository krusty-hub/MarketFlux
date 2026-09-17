import React, { useState } from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import { Eye, EyeOff, Lock, Mail, ArrowRight, Activity, ShieldCheck, AlertCircle } from 'lucide-react';
import { useAuth } from '../../auth/AuthContext';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { signIn, configured } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const redirectPath = location.state?.from?.pathname || '/dashboard';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Please enter both email and password.');
      return;
    }

    setLoading(true);
    setError(null);

    const { error: authErr } = await signIn(email, password);
    setLoading(false);

    if (authErr) {
      setError(authErr.message || 'Invalid email or password.');
    } else {
      navigate(redirectPath, { replace: true });
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
        {/* Top subtle accent glow */}
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-[var(--accent-fresh)] to-transparent opacity-70" />

        <div className="mb-6">
          <h1 className="font-display text-3xl text-[var(--text-primary)] tracking-tight">
            Terminal Access
          </h1>
          <p className="text-xs text-[var(--text-secondary)] mt-1">
            Sign in with your verified credentials to access live models and execution controls.
          </p>
        </div>

        {!configured && (
          <div className="mb-6 p-3.5 rounded-lg bg-[var(--amber-subtle)] border border-[var(--amber)]/30 text-xs text-[var(--amber)] flex items-start gap-2.5">
            <AlertCircle size={16} className="shrink-0 mt-0.5" />
            <span>
              Supabase credentials not configured in <code className="font-mono text-[11px]">.env</code>. Make sure <code className="font-mono text-[11px]">VITE_SUPABASE_URL</code> and <code className="font-mono text-[11px]">VITE_SUPABASE_ANON_KEY</code> are set.
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

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-meta text-[var(--text-muted)] font-mono">
                Password
              </label>
              <NavLink
                to="/forgot-password"
                className="text-[11px] font-mono text-[var(--accent-fresh)] hover:underline"
              >
                Forgot password?
              </NavLink>
            </div>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
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

          <div className="pt-2">
            <button
              type="submit"
              disabled={loading || !configured}
              className="btn btn-primary w-full py-3 text-xs"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <Activity size={14} className="animate-spin text-[var(--btn-text)]" />
                  Authenticating...
                </span>
              ) : (
                <span className="flex items-center justify-center gap-2">
                  Sign In to Terminal <ArrowRight size={14} />
                </span>
              )}
            </button>
          </div>
        </form>

        <div className="mt-8 pt-6 border-t border-[var(--border)] text-center text-xs text-[var(--text-secondary)]">
          Don't have an account yet?{' '}
          <NavLink to="/register" className="text-[var(--accent-fresh)] font-semibold hover:underline">
            Create Trader Account
          </NavLink>
        </div>
      </div>

      <div className="mt-8 flex items-center gap-2 text-[11px] text-[var(--text-muted)] font-mono">
        <ShieldCheck size={14} className="text-[var(--accent-fresh)]" />
        Encrypted TLS · Supabase JWT Authentication
      </div>
    </div>
  );
};
