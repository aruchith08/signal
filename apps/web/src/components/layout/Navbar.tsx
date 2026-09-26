import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Bell, Shield, Sparkles, Cpu } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

export const Navbar: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const navigate = useNavigate();
  const { user } = useAuth();

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/feed?search=${encodeURIComponent(searchQuery.trim())}`);
    }
  };

  return (
    <header className="h-16 border-b border-slate-800/80 bg-[#090D16]/90 backdrop-blur-md sticky top-0 z-20 px-6 flex items-center justify-between">
      {/* Search Input Bar */}
      <form onSubmit={handleSearchSubmit} className="max-w-md w-full relative">
        <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search CodeVita, Smart India Hackathon, internships, fellowships..."
          className="w-full bg-slate-900/90 border border-slate-800 rounded-lg pl-9 pr-12 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500/70 focus:ring-1 focus:ring-emerald-500/20 font-sans transition-colors"
        />
        <div className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none">
          <kbd className="px-1.5 py-0.5 text-[10px] font-mono font-medium text-slate-400 bg-slate-800 rounded border border-slate-700">
            ↵
          </kbd>
        </div>
      </form>

      {/* Right Controls */}
      <div className="flex items-center gap-4">
        {/* Intelligence Engine Status Pill */}
        <div className="hidden lg:flex items-center gap-2 px-3 py-1 rounded-full border border-slate-800 bg-slate-900/60 text-xs font-mono text-slate-400">
          <Cpu className="w-3.5 h-3.5 text-emerald-400" />
          <span>Multi-Tier Deduplication & Consensus Active</span>
        </div>

        {/* Telegram / Alerts Pill */}
        <button
          onClick={() => navigate('/notifications')}
          className="relative p-2 rounded-lg border border-slate-800 bg-slate-900 hover:bg-slate-800 text-slate-300 transition-colors"
          title="In-app & Telegram Alerts"
        >
          <Bell className="w-4 h-4" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-emerald-400 ring-2 ring-[#090D16]" />
        </button>

        {/* User Avatar */}
        <div
          onClick={() => navigate('/profile')}
          className="flex items-center gap-2.5 pl-2 border-l border-slate-800 cursor-pointer group"
        >
          <div className="w-8 h-8 rounded-lg bg-emerald-950 border border-emerald-700/60 flex items-center justify-center text-xs font-mono font-bold text-emerald-300 group-hover:border-emerald-500 transition-colors">
            {user?.name ? user.name.slice(0, 2).toUpperCase() : 'AC'}
          </div>
          <div className="hidden sm:block text-left">
            <div className="text-xs font-semibold text-slate-200 group-hover:text-emerald-400 transition-colors">
              {user?.name || 'Alex Chen'}
            </div>
            <div className="text-[10px] text-slate-500 font-mono">
              Student Explorer
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
