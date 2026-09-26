import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getSavedOpportunities, getFollowedOpportunities } from '../services/api/interactions';
import { Opportunity } from '../types/opportunity';
import { useAuth } from '../contexts/AuthContext';
import { OpportunityCard } from '../components/opportunity/OpportunityCard';
import { EmptyState } from '../components/common/EmptyState';
import { Bookmark, Bell, Compass, Sparkles } from 'lucide-react';

export const SavedPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'SAVED' | 'FOLLOWED'>('SAVED');
  const [savedList, setSavedList] = useState<Opportunity[]>([]);
  const [followedList, setFollowedList] = useState<Opportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const { user, savedIds, followedIds } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    let isMounted = true;
    async function loadData() {
      if (!user?.id) return;
      try {
        setLoading(true);
        const [saved, followed] = await Promise.all([
          getSavedOpportunities(user.id),
          getFollowedOpportunities(user.id),
        ]);
        if (isMounted) {
          setSavedList(saved);
          setFollowedList(followed);
        }
      } catch (err) {
        console.warn('Failed to load saved/followed opportunities', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    loadData();
    return () => {
      isMounted = false;
    };
  }, [user?.id, savedIds.size, followedIds.size]);

  const displayedList = activeTab === 'SAVED' ? savedList : followedList;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold font-mono text-slate-100 tracking-tight">
          SAVED & TRACKED OPPORTUNITIES
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Review your personal bookmarks and active program watch subscriptions.
        </p>

        {/* Tab Switcher */}
        <div className="mt-6 flex items-center gap-2 border-b border-slate-800 pb-2">
          <button
            onClick={() => setActiveTab('SAVED')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold font-mono transition-all ${
              activeTab === 'SAVED'
                ? 'bg-amber-950/70 text-amber-300 border border-amber-600/50 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
            }`}
          >
            <Bookmark className="w-3.5 h-3.5" />
            <span>Bookmarked ({savedIds.size})</span>
          </button>

          <button
            onClick={() => setActiveTab('FOLLOWED')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold font-mono transition-all ${
              activeTab === 'FOLLOWED'
                ? 'bg-sky-950/70 text-sky-300 border border-sky-600/50 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
            }`}
          >
            <Bell className="w-3.5 h-3.5" />
            <span>Following ({followedIds.size})</span>
          </button>
        </div>
      </div>

      {/* Grid or Empty State */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-pulse">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-44 rounded-xl bg-slate-900/60 border border-slate-800" />
          ))}
        </div>
      ) : displayedList.length === 0 ? (
        <EmptyState
          icon={
            activeTab === 'SAVED' ? (
              <Bookmark className="w-10 h-10 text-amber-500/50" />
            ) : (
              <Bell className="w-10 h-10 text-sky-500/50" />
            )
          }
          title={
            activeTab === 'SAVED'
              ? 'No bookmarked opportunities yet'
              : 'No opportunities followed yet'
          }
          description={
            activeTab === 'SAVED'
              ? 'Click the bookmark button on any opportunity card in your feed to save it for quick review later.'
              : 'Follow high-value opportunities to receive proactive deadline notifications and change monitoring alerts.'
          }
          actionLabel="Explore Opportunities"
          onAction={() => navigate('/feed')}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {displayedList.map((opp) => (
            <OpportunityCard key={opp.id} opportunity={opp} />
          ))}
        </div>
      )}
    </div>
  );
};
