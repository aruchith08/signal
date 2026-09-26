import React, { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getOpportunities } from '../services/api/opportunities';
import { Opportunity } from '../types/opportunity';
import { OpportunityCard } from '../components/opportunity/OpportunityCard';
import { Input } from '../components/common/Input';
import { Button } from '../components/common/Button';
import { EmptyState } from '../components/common/EmptyState';
import { Search, Filter, ShieldCheck, CheckCheck, SlidersHorizontal, RotateCcw } from 'lucide-react';

const CATEGORIES = [
  { label: 'All Categories', value: '' },
  { label: 'Hackathons', value: 'HACKATHON' },
  { label: 'Contests', value: 'CONTEST' },
  { label: 'Internships', value: 'INTERNSHIP' },
  { label: 'Student Programs', value: 'STUDENT_PROGRAM' },
  { label: 'Fellowships', value: 'FELLOWSHIP' },
  { label: 'Scholarships', value: 'SCHOLARSHIP' },
  { label: 'AI Competitions', value: 'AI_COMPETITION' },
];

export const FeedPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialQuery = searchParams.get('search') || '';
  const initialCategory = searchParams.get('category') || '';

  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState(initialQuery);
  const [selectedCategory, setSelectedCategory] = useState(initialCategory);
  const [verificationFilter, setVerificationFilter] = useState<'ALL' | 'OFFICIAL' | 'VERIFIED'>('ALL');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'ACTIVE' | 'DISCOVERED'>('ALL');

  useEffect(() => {
    let isMounted = true;
    async function loadData() {
      try {
        setLoading(true);
        const res = await getOpportunities({
          category: selectedCategory || undefined,
          limit: 100,
        });
        if (isMounted) {
          setOpportunities(res.items);
          setError(null);
        }
      } catch (err: any) {
        if (isMounted) setError(err.message || 'Failed to load opportunities');
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    loadData();
    return () => {
      isMounted = false;
    };
  }, [selectedCategory]);

  // Sync search state with URL params
  useEffect(() => {
    const q = searchParams.get('search');
    if (q !== null && q !== search) {
      setSearch(q);
    }
  }, [searchParams]);

  // Client-side filtering across text and verification
  const filteredOpportunities = useMemo(() => {
    return opportunities.filter((item) => {
      // Text search
      if (search.trim()) {
        const q = search.toLowerCase();
        const matchesTitle = (item.title || '').toLowerCase().includes(q);
        const matchesCanonical = (item.canonical_name || '').toLowerCase().includes(q);
        const matchesSummary = (item.summary || '').toLowerCase().includes(q);
        const matchesSkills = (item.required_skills || []).some(s => s.toLowerCase().includes(q));
        const matchesTags = (item.tags || []).some(t => t.toLowerCase().includes(q));
        if (!matchesTitle && !matchesCanonical && !matchesSummary && !matchesSkills && !matchesTags) {
          return false;
        }
      }

      // Verification filter
      if (verificationFilter === 'OFFICIAL' && !item.official && item.verification_status !== 'OFFICIAL') {
        return false;
      }
      if (verificationFilter === 'VERIFIED' && item.verification_status === 'UNVERIFIED') {
        return false;
      }

      // Status filter
      if (statusFilter !== 'ALL' && item.status !== statusFilter) {
        return false;
      }

      return true;
    });
  }, [opportunities, search, verificationFilter, statusFilter]);

  const handleResetFilters = () => {
    setSearch('');
    setSelectedCategory('');
    setVerificationFilter('ALL');
    setStatusFilter('ALL');
    setSearchParams({});
  };

  return (
    <div className="space-y-6">
      {/* Title & Filter Bar */}
      <div>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold font-mono text-slate-100 tracking-tight">
              OPPORTUNITY INTELLIGENCE FEED
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Verified programs, hackathons, contests, and internships across global sources.
            </p>
          </div>

          <div className="text-xs font-mono text-slate-400">
            Showing <span className="text-emerald-400 font-bold">{filteredOpportunities.length}</span> of {opportunities.length} tracked
          </div>
        </div>

        {/* Filter Toolbar */}
        <div className="mt-6 flex flex-col md:flex-row gap-3">
          <div className="flex-1">
            <Input
              placeholder="Filter by title, technology (e.g. Python, AI), or organization..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              leftIcon={<Search className="w-4 h-4" />}
            />
          </div>

          {/* Verification Level Toggle */}
          <div className="flex items-center gap-1.5 p-1 rounded-lg border border-slate-800 bg-slate-900/80 shrink-0">
            <button
              onClick={() => setVerificationFilter('ALL')}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                verificationFilter === 'ALL'
                  ? 'bg-slate-800 text-slate-100 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              All
            </button>
            <button
              onClick={() => setVerificationFilter('OFFICIAL')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                verificationFilter === 'OFFICIAL'
                  ? 'bg-sky-950/80 text-sky-300 border border-sky-700/60 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <ShieldCheck className="w-3.5 h-3.5 text-sky-400" />
              Official Only
            </button>
            <button
              onClick={() => setVerificationFilter('VERIFIED')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                verificationFilter === 'VERIFIED'
                  ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-700/60 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <CheckCheck className="w-3.5 h-3.5 text-emerald-400" />
              Verified Only
            </button>
          </div>
        </div>

        {/* Category Pills Bar */}
        <div className="mt-3 flex items-center gap-1.5 overflow-x-auto pb-2 scrollbar-none">
          {CATEGORIES.map((cat) => {
            const isSelected = selectedCategory === cat.value;
            return (
              <button
                key={cat.value}
                onClick={() => setSelectedCategory(cat.value)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all ${
                  isSelected
                    ? 'bg-emerald-950/70 text-emerald-300 border border-emerald-600/50 shadow-sm'
                    : 'bg-slate-900/60 text-slate-400 border border-slate-800/80 hover:text-slate-200 hover:border-slate-700'
                }`}
              >
                {cat.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Grid of Opportunity Cards */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-pulse">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-44 rounded-xl bg-slate-900/60 border border-slate-800" />
          ))}
        </div>
      ) : filteredOpportunities.length === 0 ? (
        <EmptyState
          icon={<Filter className="w-10 h-10" />}
          title="No opportunities match your current filters"
          description="Try broadening your search keywords or resetting the verification level and category filters."
          actionLabel="Reset All Filters"
          onAction={handleResetFilters}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredOpportunities.map((opp) => (
            <OpportunityCard key={opp.id} opportunity={opp} />
          ))}
        </div>
      )}
    </div>
  );
};
