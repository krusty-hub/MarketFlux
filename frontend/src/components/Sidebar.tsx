import React, { useState, useEffect } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  TrendingUp,
  Layers,
  GraduationCap,
  History,
  Bot,
  FlaskConical,
  BarChart3,
  Settings,
  Sun,
  Moon,
  LogOut,
  Globe,
  Menu,
  X,
} from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { apiClient } from '../services/api';

interface SidebarProps {
  botMode: 'paper' | 'live';
  onOpenLiveModal: () => void;
  darkMode?: boolean;
  onToggleDark?: () => void;
}

const NAV_GROUPS = [
  {
    title: 'Overview',
    items: [
      { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
      { to: '/markets', label: 'Markets', icon: TrendingUp },
    ],
  },
  {
    title: 'Intelligence',
    items: [
      { to: '/models', label: 'Models', icon: Layers },
      { to: '/training', label: 'Training', icon: GraduationCap },
      { to: '/forecast', label: 'AI Outlook', icon: FlaskConical },
    ],
  },
  {
    title: 'Trading',
    items: [
      { to: '/trades', label: 'Trades', icon: History },
      { to: '/bot', label: 'Bot Engine', icon: Bot },
      { to: '/backtesting', label: 'Backtest', icon: FlaskConical },
    ],
  },
  {
    title: 'System',
    items: [
      { to: '/analytics', label: 'Analytics', icon: BarChart3 },
      { to: '/settings', label: 'Settings', icon: Settings },
    ],
  },
];

export const Sidebar: React.FC<SidebarProps> = ({
  botMode,
  onOpenLiveModal,
}) => {
  const [open, setOpen] = useState(false);
  const [apiConnected, setApiConnected] = useState<boolean | null>(null);
  const { user, profile, signOut } = useAuth();
  const { isDark, toggleTheme } = useTheme();
  const navigate = useNavigate();

  const isLive = botMode === 'live';

  // Check backend connectivity
  useEffect(() => {
    let mounted = true;
    const checkApi = async () => {
      try {
        await apiClient.get('/health/');
        if (mounted) setApiConnected(true);
      } catch {
        if (mounted) setApiConnected(false);
      }
    };
    checkApi();
    const interval = setInterval(checkApi, 20000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const handleLogout = async () => {
    await signOut();
    navigate('/');
  };

  const userDisplayName = profile?.full_name || user?.email?.split('@')[0] || 'Trader';
  const userInitial = userDisplayName.charAt(0).toUpperCase();

  const navContent = (
    <nav className="flex-1 overflow-y-auto py-3 px-3 space-y-5">
      {NAV_GROUPS.map((group) => (
        <div key={group.title}>
          <p className="px-3 mb-1.5 text-[10px] font-mono font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            {group.title}
          </p>
          <div className="space-y-0.5">
            {group.items.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                      isActive
                        ? 'bg-[var(--surface-hover)] text-[var(--text-primary)] font-semibold shadow-xs'
                        : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)]'
                    }`
                  }
                  onClick={() => setOpen(false)}
                >
                  <Icon size={15} className="shrink-0 text-[var(--accent-fresh)] opacity-85" />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );

  const bottomContent = (
    <div className="p-3 border-t border-[var(--border)] bg-[var(--surface-subtle)] space-y-2">
      {/* Backend & Bot Status Pill */}
      <div className="px-3 py-2 rounded-lg bg-[var(--surface)] border border-[var(--border)] flex items-center justify-between text-[11px] font-mono">
        <div className="flex items-center gap-1.5">
          <span
            className={`w-2 h-2 rounded-full ${
              apiConnected === true
                ? 'bg-[var(--accent-fresh)] shadow-[0_0_6px_var(--accent-fresh)]'
                : apiConnected === false
                ? 'bg-[var(--red)]'
                : 'bg-[var(--text-muted)]'
            }`}
          />
          <span className="text-[var(--text-secondary)]">
            {apiConnected === true ? 'API Ready' : apiConnected === false ? 'API Offline' : 'Connecting...'}
          </span>
        </div>

        <button
          onClick={isLive ? undefined : onOpenLiveModal}
          className={`cursor-pointer hover:underline ${isLive ? 'text-[var(--red)] font-semibold' : 'text-[var(--text-muted)]'}`}
        >
          {isLive ? 'LIVE' : 'PAPER'}
        </button>
      </div>

      {/* Authenticated User Session Card */}
      {user ? (
        <div className="p-2.5 rounded-lg bg-[var(--surface)] border border-[var(--border)]">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-6 h-6 rounded-full bg-[var(--accent-subtle)] border border-[var(--accent-border)] flex items-center justify-center font-mono font-semibold text-[11px] text-[var(--accent-fresh)] shrink-0">
                {userInitial}
              </div>
              <div className="min-w-0">
                <p className="text-xs font-semibold text-[var(--text-primary)] truncate">
                  {userDisplayName}
                </p>
                <p className="text-[10px] text-[var(--text-muted)] font-mono truncate">
                  {user.email}
                </p>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="p-1 text-[var(--text-muted)] hover:text-[var(--red)] transition-colors rounded"
              title="Sign Out"
            >
              <LogOut size={13} />
            </button>
          </div>
        </div>
      ) : null}

      {/* Utility links: Theme Toggle + Landing Page */}
      <div className="flex items-center justify-between px-1 pt-1 text-[11px] text-[var(--text-muted)]">
        <button
          onClick={toggleTheme}
          className="flex items-center gap-1.5 hover:text-[var(--text-primary)] transition-colors py-1 cursor-pointer"
          title="Toggle Light / Dark Mode"
        >
          {isDark ? <Sun size={13} className="text-[var(--amber)]" /> : <Moon size={13} />}
          <span>{isDark ? 'Light' : 'Dark'}</span>
        </button>

        <NavLink
          to="/"
          className="flex items-center gap-1 hover:text-[var(--text-primary)] transition-colors py-1 no-underline text-[var(--text-muted)]"
        >
          <Globe size={12} />
          <span>Home →</span>
        </NavLink>
      </div>
    </div>
  );

  return (
    <>
      {/* ── Desktop sidebar ── */}
      <aside className="sidebar" aria-label="Main navigation">
        {/* Wordmark */}
        <div className="px-5 py-4 border-b border-[var(--border)] flex items-center justify-between">
          <NavLink to="/dashboard" className="no-underline flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-[var(--accent-fresh)] shadow-[0_0_8px_var(--accent-fresh)]" />
            <span className="font-mono font-bold text-sm tracking-wider uppercase text-[var(--text-primary)]">
              Market<span className="text-[var(--accent-fresh)]">Flux</span>
            </span>
          </NavLink>
        </div>

        {navContent}
        {bottomContent}
      </aside>

      {/* ── Mobile: hamburger trigger ── */}
      <div className="hidden mobile-menu-trigger fixed top-4 left-4 z-50">
        <button
          onClick={() => setOpen(!open)}
          className="bg-[var(--surface)] border border-[var(--border)] rounded-lg w-9 h-9 flex items-center justify-center cursor-pointer text-[var(--text-primary)] shadow-sm"
          aria-label={open ? 'Close menu' : 'Open menu'}
        >
          {open ? <X size={18} /> : <Menu size={18} />}
        </button>
      </div>

      {/* ── Mobile: overlay sidebar ── */}
      {open && (
        <>
          <div
            onClick={() => setOpen(false)}
            className="fixed inset-0 z-40 bg-black/40 backdrop-blur-xs"
          />
          <aside className="sidebar open z-50">
            <div className="px-5 py-4 border-b border-[var(--border)] flex items-center justify-between">
              <NavLink to="/dashboard" className="no-underline flex items-center gap-2" onClick={() => setOpen(false)}>
                <span className="w-2.5 h-2.5 rounded-full bg-[var(--accent-fresh)]" />
                <span className="font-mono font-bold text-sm tracking-wider uppercase text-[var(--text-primary)]">
                  Market<span className="text-[var(--accent-fresh)]">Flux</span>
                </span>
              </NavLink>
              <button
                onClick={() => setOpen(false)}
                className="p-1 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
              >
                <X size={18} />
              </button>
            </div>
            {navContent}
            {bottomContent}
          </aside>
        </>
      )}
    </>
  );
};
