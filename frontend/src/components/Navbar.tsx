import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  Activity,
  BarChart2,
  Cpu,
  History,
  Layers,
  Settings,
  Shield,
  TrendingUp,
  Zap,
} from 'lucide-react';

interface NavbarProps {
  botMode?: 'paper' | 'live';
  onOpenLiveModal?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ botMode = 'paper', onOpenLiveModal }) => {
  const navLinks = [
    { to: '/', label: 'Dashboard', icon: Activity },
    { to: '/markets', label: 'Markets', icon: TrendingUp },
    { to: '/bot', label: 'Bot Desk', icon: Shield },
    { to: '/training', label: 'ML Training', icon: Cpu, badge: 'CORE' },
    { to: '/backtesting', label: 'Backtesting', icon: BarChart2 },
    { to: '/models', label: 'Models', icon: Layers },
    { to: '/trades', label: 'Trades', icon: History },
    { to: '/analytics', label: 'Analytics', icon: Zap },
    { to: '/settings', label: 'Settings', icon: Settings },
  ];

  return (
    <header className="sticky top-0 z-50 w-full border-b border-[#27272A] bg-[#09090B]/90 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
        {/* Brand & Identity */}
        <div className="flex items-center gap-6">
          <NavLink to="/" className="flex items-center gap-3">
            <div className="relative flex h-8 w-8 items-center justify-center rounded-lg bg-[#FF7817]/10 border border-[#FF7817]/30">
              <span className="h-3 w-3 rounded-full bg-[#FF7817] shadow-[0_0_12px_#FF7817]"></span>
            </div>
            <div>
              <span className="font-sans text-lg font-bold tracking-tight text-[#FAFAFA]">
                MARKET<span className="text-[#FF7817]">FLUX</span>
              </span>
              <span className="ml-2 rounded px-1.5 py-0.5 text-[10px] font-medium tracking-wider uppercase bg-[#27272A] text-[#A1A1AA]">
                QUANT v3.0
              </span>
            </div>
          </NavLink>

          {/* Nav Links */}
          <nav className="hidden lg:flex items-center gap-1">
            {navLinks.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `relative flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium transition-all ${
                      isActive
                        ? 'bg-[#18181B] text-[#FAFAFA] border border-[#3F3F46]'
                        : 'text-[#A1A1AA] hover:bg-[#121215] hover:text-[#FAFAFA]'
                    }`
                  }
                >
                  <Icon className="h-3.5 w-3.5" />
                  <span>{item.label}</span>
                  {item.badge && (
                    <span className="rounded bg-[#FF7817]/20 px-1 py-0.2 text-[9px] font-bold text-[#FF7817]">
                      {item.badge}
                    </span>
                  )}
                </NavLink>
              );
            })}
          </nav>
        </div>

        {/* Right Status Badges & CTAs */}
        <div className="flex items-center gap-3">
          {/* Server Connection Indicator */}
          <div className="hidden sm:flex items-center gap-2 rounded-full border border-[#27272A] bg-[#121215] px-3 py-1 text-xs">
            <span className="h-2 w-2 rounded-full bg-[#10B981] animate-pulse"></span>
            <span className="text-[11px] font-data text-[#A1A1AA]">FASTAPI :8000</span>
          </div>

          {/* Account Mode Pill */}
          <div
            onClick={onOpenLiveModal}
            className={`cursor-pointer flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium transition-all ${
              botMode === 'live'
                ? 'border-[#F43F5E]/50 bg-[#F43F5E]/10 text-[#F43F5E] hover:bg-[#F43F5E]/20'
                : 'border-[#27272A] bg-[#18181B] text-[#10B981] hover:border-[#3F3F46]'
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                botMode === 'live' ? 'bg-[#F43F5E]' : 'bg-[#10B981]'
              }`}
            ></span>
            <span className="font-data uppercase tracking-wider text-[11px]">
              {botMode === 'live' ? 'LIVE DESK' : 'PAPER $10,000'}
            </span>
          </div>

          {/* Quick CTA to Training */}
          <NavLink
            to="/training"
            className="flex items-center gap-2 rounded-lg bg-[#FF7817] px-3.5 py-1.5 text-xs font-semibold text-[#09090B] shadow-[0_0_15px_rgba(255,120,23,0.3)] transition-all hover:bg-[#FF8A34]"
          >
            <Cpu className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Train Model</span>
          </NavLink>
        </div>
      </div>
    </header>
  );
};
