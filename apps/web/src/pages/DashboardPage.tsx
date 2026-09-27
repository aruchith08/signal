import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getDashboardOverview } from '../services/api/dashboard';
import { DashboardOverview } from '../types/dashboard';
import { useAuth } from '../contexts/AuthContext';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { OpportunityCard } from '../components/opportunity/OpportunityCard';
import { VerificationBadge } from '../components/opportunity/VerificationBadge';
import { SaveFollowButtons } from '../components/opportunity/SaveFollowButtons';
import { 
  Radar, 
  Clock, 
  ShieldCheck, 
  Sparkles, 
  ChevronRight, 
  AlertTriangle,
  Globe,
  ExternalLink,
  Flame,
  Layers
} from 'lucide-react';

export const DashboardPage: React.FC = () => {
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    let isMounted = true;
    async function load() {
      try {
        setLoading(true);
        const res = await getDashboardOverview(user?.id);
        if (isMounted) {
          setData(res);
          setError(null);
        }
      } catch (err: any) {
        if (isMounted) setError(err.message || 'Failed to load dashboard overview');
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    load();
    return () => {
      isMounted = false;
    };
  }, [user?.id]);

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 bg-slate-800/60 rounded-md w-64" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-24 bg-slate-800/40 rounded-xl border border-slate-800" />
          ))}
        </div>
        <div className="h-64 bg-slate-800/40 rounded-xl border border-slate-800" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-8 text-center rounded-xl border border-rose-800/60 bg-rose-950/20">
        <AlertTriangle className="w-8 h-8 text-rose-400 mx-auto mb-2" />
        <h3 className="text-sm font-semibold text-rose-200">Unable to load dashboard</h3>
        <p className="text-xs text-rose-400/80 mt-1">{error || 'Server did not respond'}</p>
        <Button variant="outline" size="sm" className="mt-4" onClick={() => window.location.reload()}>
          Retry Connection
        </Button>
      </div>
    );
  }

  const { stats, top_priority, for_you, deadlines_approaching, recent_announcements } = data;

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-slate-100 font-mono tracking-tight">
              INTELLIGENCE RADAR
            </h1>
            <Badge variant="success" size="xs">
              Live Monitoring
            </Badge>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Personalized opportunity radar for{' '}
            <span className="text-slate-200 font-semibold">{user?.name || 'Alex Chen'}</span> •{' '}
            {user?.education_level || 'B.Tech CS'}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => navigate('/feed')}>
            Browse All Opportunities
            <ChevronRight className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>

      {/* Metric Counters Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4 border-slate-800/80 bg-slate-900/60 flex items-center justify-between">
          <div>
            <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">
              Tracked Opportunities
            </span>
            <div className="text-2xl font-bold font-mono text-slate-100 mt-1">
              {stats?.total_tracked ?? (stats as any)?.opportunities_tracked ?? 0}
            </div>
          </div>
          <div className="p-2.5 rounded-lg bg-slate-800/80 text-emerald-400 border border-slate-700/60">
            <Radar className="w-5 h-5" />
          </div>
        </Card>

        <Card className="p-4 border-slate-800/80 bg-slate-900/60 flex items-center justify-between">
          <div>
            <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">
              Active Phases
            </span>
            <div className="text-2xl font-bold font-mono text-sky-400 mt-1">
              {stats?.active_events ?? 0}
            </div>
          </div>
          <div className="p-2.5 rounded-lg bg-slate-800/80 text-sky-400 border border-slate-700/60">
            <Layers className="w-5 h-5" />
          </div>
        </Card>

        <Card className="p-4 border-slate-800/80 bg-slate-900/60 flex items-center justify-between">
          <div>
            <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">
              Verified Sources
            </span>
            <div className="text-2xl font-bold font-mono text-emerald-400 mt-1">
              {stats?.verified_sources ?? (stats as any)?.sources_total ?? 0}
            </div>
          </div>
          <div className="p-2.5 rounded-lg bg-slate-800/80 text-emerald-400 border border-slate-700/60">
            <ShieldCheck className="w-5 h-5" />
          </div>
        </Card>

        <Card className="p-4 border-slate-800/80 bg-slate-900/60 flex items-center justify-between">
          <div>
            <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">
              Approaching Deadlines
            </span>
            <div className="text-2xl font-bold font-mono text-amber-400 mt-1">
              {stats?.critical_deadlines ?? 0}
            </div>
          </div>
          <div className="p-2.5 rounded-lg bg-slate-800/80 text-amber-400 border border-slate-700/60">
            <Clock className="w-5 h-5" />
          </div>
        </Card>
      </div>

      {/* Top Priority Hero Card */}
      {top_priority && top_priority.opportunity && (
        <div className="relative overflow-hidden rounded-2xl border border-emerald-600/40 bg-gradient-to-br from-emerald-950/40 via-slate-900 to-[#0A0E17] p-6 shadow-2xl">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Badge variant="success" size="sm" className="font-mono gap-1.5 shadow-sm">
                <Flame className="w-3.5 h-3.5 text-emerald-400 fill-emerald-400" />
                TOP PRIORITY INTELLIGENCE
              </Badge>
              <VerificationBadge
                status={top_priority.opportunity.verification_status}
                official={top_priority.opportunity.official}
                confidence={top_priority.opportunity.verification_confidence}
                sourceCount={top_priority.opportunity.source_count}
              />
            </div>

            <SaveFollowButtons
              opportunityId={top_priority.opportunity.id}
              title={top_priority.opportunity.title}
            />
          </div>

          <div className="mt-4 grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-2">
              <h2
                onClick={() => navigate(`/opportunities/${top_priority.opportunity.id}`)}
                className="text-xl font-bold text-slate-100 hover:text-emerald-300 transition-colors cursor-pointer"
              >
                {top_priority.opportunity.title}
              </h2>
              <p className="text-xs text-slate-300 leading-relaxed max-w-2xl">
                {top_priority.opportunity.summary ||
                  'High-relevance flagship opportunity with imminent critical milestone.'}
              </p>

              <div className="pt-2 flex flex-wrap items-center gap-2">
                <span className="text-xs font-mono text-emerald-400 font-semibold">
                  Why Priority:
                </span>
                <span className="text-xs text-slate-300">{top_priority.reason}</span>
              </div>
            </div>

            <div className="flex flex-col justify-between p-4 rounded-xl bg-slate-900/80 border border-slate-800">
              <div className="space-y-2">
                <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
                  Target Milestone
                </span>
                <div className="text-sm font-semibold text-slate-200">
                  {top_priority.top_event?.event_name || 'Registration Deadline'}
                </div>
                {top_priority.top_event?.deadline_date && (
                  <div className="text-xs font-mono text-amber-400 flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5" />
                    Deadline:{' '}
                    {new Date(top_priority.top_event.deadline_date).toLocaleDateString()}
                  </div>
                )}
              </div>

              <div className="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between">
                {top_priority.opportunity.application_url && (
                  <a
                    href={top_priority.opportunity.application_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-xs font-medium text-emerald-400 hover:underline"
                  >
                    Official Portal <ExternalLink className="w-3 h-3" />
                  </a>
                )}
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => navigate(`/opportunities/${top_priority.opportunity.id}`)}
                >
                  View Details
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Two Column Layout: For You Recommendations + Approaching Deadlines */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left 2 Cols: For You Feed */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-emerald-400" />
              <h2 className="text-sm font-bold font-mono text-slate-100 uppercase tracking-wider">
                Recommended For You
              </h2>
            </div>
            <button
              onClick={() => navigate('/feed')}
              className="text-xs text-slate-400 hover:text-emerald-400 transition-colors"
            >
              View all ({stats.total_tracked}) →
            </button>
          </div>

          <div className="grid grid-cols-1 gap-4">
            {for_you.map((item) => (
              <OpportunityCard
                key={item.opportunity.id}
                opportunity={item.opportunity}
                matchScore={item.score}
                isEligible={item.is_eligible}
                matchTier={item.tier}
                matchedSkills={item.matched_skills}
              />
            ))}
          </div>
        </div>

        {/* Right 1 Col: Urgent Deadlines Watch */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-amber-400" />
              <h2 className="text-sm font-bold font-mono text-slate-100 uppercase tracking-wider">
                Imminent Deadlines
              </h2>
            </div>
            <Badge variant="warning" size="xs" className="font-mono">
              Next 14 Days
            </Badge>
          </div>

          <div className="space-y-3">
            {deadlines_approaching.length === 0 ? (
              <div className="p-6 rounded-xl border border-slate-800 bg-slate-900/50 text-center text-xs text-slate-400">
                No critical deadlines closing within the next 14 days.
              </div>
            ) : (
              deadlines_approaching.map((item, idx) => {
                const days = item.days_remaining;
                const isUrgent = days <= 3;

                return (
                  <div
                    key={idx}
                    onClick={() => navigate(`/opportunities/${item.opportunity.id}`)}
                    className="p-3.5 rounded-xl border border-slate-800 bg-slate-900/80 hover:border-slate-700 hover:bg-[#131D33] transition-all cursor-pointer space-y-2 group"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <h4 className="text-xs font-semibold text-slate-200 group-hover:text-emerald-400 transition-colors line-clamp-1">
                        {item.opportunity.title}
                      </h4>
                      <span
                        className={`text-xs font-mono font-bold px-1.5 py-0.5 rounded shrink-0 ${
                          isUrgent
                            ? 'bg-rose-950/80 text-rose-300 border border-rose-800/60'
                            : 'bg-amber-950/80 text-amber-300 border border-amber-800/60'
                        }`}
                      >
                        {days === 0 ? 'Today' : `${days}d left`}
                      </span>
                    </div>

                    <div className="text-[11px] text-slate-400 flex items-center justify-between font-mono">
                      <span>{item.event.event_name}</span>
                      <span className="text-slate-500">
                        {item.event.deadline_date
                          ? new Date(item.event.deadline_date).toLocaleDateString()
                          : ''}
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
