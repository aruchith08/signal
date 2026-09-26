import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  Radar, 
  Compass, 
  Bookmark, 
  ShieldAlert, 
  Activity, 
  User, 
  Settings, 
  Sparkles,
  ExternalLink
} from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

export const Sidebar: React.FC = () => {
  const { user, savedIds, followedIds } = useAuth();

  const navItems = [
    { to: '/', label: 'Dashboard', icon: Radar, badge: null },
    { to: '/feed', label: 'Opportunities', icon: Compass, badge: null },
    { 
      to: '/saved', 
      label: 'Saved & Followed', 
      icon: Bookmark, 
      badge: (savedIds.size + followedIds.size) > 0 ? `${savedIds.size + followedIds.size}` : null 
    },
    { to: '/review', label: 'Review Queue', icon: ShieldAlert, badge: null },
    { to: '/activity', label: 'Activity & Sources', icon: Activity, badge: null },
    { to: '/profile', label: 'Profile & Preferences', icon: User, badge: null },
  ];

  return (
    <aside className="w-64 border-r border-slate-800/80 bg-[#0A0E17] flex flex-col justify-between h-screen sticky top-0 shrink-0 select-none z-30">
      {/* Brand Header */}
      <div className="p-5 border-b border-slate-800/80">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-700 flex items-center justify-center shadow-lg shadow-emerald-950/40 text-white font-mono font-bold text-lg">
            📡
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-mono font-bold tracking-tight text-slate-100 text-base">
                SIGNAL
              </span>
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-700/50">
                v1.0
              </span>
            </div>
            <p className="text-[11px] text-slate-400 font-mono flex items-center gap-1.5 mt-0.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Intelligence Online
            </p>
          </div>
        </div>
      </div>

      {/* Main Navigation Items */}
      <nav className="p-3 space-y-1 overflow-y-auto flex-1">
        <div className="px-3 py-2 text-[10px] font-mono uppercase tracking-wider text-slate-400 font-semibold">
          Platform
        </div>

        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-emerald-950/50 text-emerald-300 border border-emerald-700/40 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
                }`
              }
            >
              <div className="flex items-center gap-2.5">
                <Icon className="w-4 h-4 shrink-0" />
                <span>{item.label}</span>
              </div>
              {item.badge && (
                <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-300 border border-slate-700">
                  {item.badge}
                </span>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Active User Terminal Card */}
      <div className="p-3 border-t border-slate-800/80 bg-slate-950/40">
        <div className="p-3 rounded-lg border border-slate-800 bg-[#0F172A]/70">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
              Active Student Profile
            </span>
            <span className="w-2 h-2 rounded-full bg-emerald-400" title="Connected" />
          </div>

          <div className="mt-2">
            <div className="text-xs font-bold text-slate-200 truncate">
              {user?.name || 'Alex Chen'}
            </div>
            <div className="text-[11px] text-slate-400 font-mono truncate">
              {user?.education_level || 'B.Tech CS'} • {user?.graduation_year || 2026}
            </div>
          </div>

          <div className="mt-2.5 pt-2 border-t border-slate-800/60 flex items-center justify-between text-[11px] text-slate-400 font-mono">
            <span>Threshold:</span>
            <span className="text-emerald-400 font-semibold">
              {user ? Math.round(user.relevance_threshold * 100) : 50}%
            </span>
          </div>
        </div>
      </div>
    </aside>
  );
};
