import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getOpportunityById } from '../services/api/opportunities';
import { evaluateRelevance } from '../services/api/users';
import { OpportunityDetail } from '../types/opportunity';
import { RelevanceScoreResult } from '../types/user';
import { useAuth } from '../contexts/AuthContext';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { VerificationBadge } from '../components/opportunity/VerificationBadge';
import { TrustIndicator } from '../components/opportunity/TrustIndicator';
import { LifecycleTimeline } from '../components/opportunity/LifecycleTimeline';
import { SourceEvidenceList } from '../components/opportunity/SourceEvidenceList';
import { ConsensusCard } from '../components/opportunity/ConsensusCard';
import { ConflictAlert } from '../components/opportunity/ConflictAlert';
import { SaveFollowButtons } from '../components/opportunity/SaveFollowButtons';
import { 
  ArrowLeft, 
  ExternalLink, 
  Sparkles, 
  CheckCircle2, 
  AlertCircle, 
  Layers, 
  FileText, 
  Globe, 
  Share2 
} from 'lucide-react';

export const OpportunityDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [opp, setOpp] = useState<OpportunityDetail | null>(null);
  const [relevance, setRelevance] = useState<RelevanceScoreResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showRaw, setShowRaw] = useState(false);

  useEffect(() => {
    let isMounted = true;
    async function load() {
      if (!id) return;
      try {
        setLoading(true);
        const data = await getOpportunityById(id);
        if (isMounted) {
          setOpp(data);
          setError(null);
        }

        // Fetch relevance evaluation if active user exists
        if (user?.id) {
          try {
            const relData = await evaluateRelevance(user.id, id);
            if (isMounted) setRelevance(relData);
          } catch (e) {
            console.warn('Relevance evaluation not available for opportunity', e);
          }
        }
      } catch (err: any) {
        if (isMounted) setError(err.message || 'Opportunity not found');
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    load();
    return () => {
      isMounted = false;
    };
  }, [id, user?.id]);

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-6 w-32 bg-slate-800 rounded" />
        <div className="h-36 bg-slate-900 rounded-xl border border-slate-800" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 h-96 bg-slate-900 rounded-xl border border-slate-800" />
          <div className="h-96 bg-slate-900 rounded-xl border border-slate-800" />
        </div>
      </div>
    );
  }

  if (error || !opp) {
    return (
      <div className="p-12 text-center rounded-xl border border-slate-800 bg-slate-900/40 max-w-lg mx-auto space-y-4">
        <AlertCircle className="w-10 h-10 text-rose-400 mx-auto" />
        <h2 className="text-base font-bold text-slate-200">Opportunity Not Found</h2>
        <p className="text-xs text-slate-400">{error || 'The requested opportunity record does not exist.'}</p>
        <Button variant="outline" size="sm" onClick={() => navigate('/feed')}>
          <ArrowLeft className="w-4 h-4" />
          Back to Feed
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Top Navigation Row */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => navigate(-1)}
          className="inline-flex items-center gap-2 text-xs font-mono text-slate-400 hover:text-slate-200 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back</span>
        </button>

        <div className="flex items-center gap-2">
          <SaveFollowButtons opportunityId={opp.id} title={opp.title} size="md" />
        </div>
      </div>

      {/* Main Hero Header Card */}
      <div className="p-6 md:p-8 rounded-2xl border border-slate-800 bg-slate-900/80 shadow-xl space-y-4">
        <div className="flex flex-wrap items-center gap-2.5">
          <Badge variant="purple" size="sm" className="font-mono uppercase">
            {opp.category}
          </Badge>

          <VerificationBadge
            status={opp.verification_status}
            official={opp.official}
            confidence={opp.verification_confidence ?? opp.confidence_score}
            sourceCount={opp.source_count}
            size="sm"
          />

          {opp.year && (
            <Badge variant="slate" size="sm" className="font-mono">
              {opp.year}
            </Badge>
          )}

          {opp.country && (
            <Badge variant="outline" size="sm" className="gap-1">
              <Globe className="w-3 h-3 text-slate-400" />
              {opp.country}
            </Badge>
          )}
        </div>

        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-slate-100 tracking-tight">
            {opp.title}
          </h1>
          {opp.canonical_name && opp.canonical_name !== opp.title && (
            <p className="text-xs font-mono text-slate-400 mt-1">
              Program Identity: <span className="text-emerald-400">{opp.canonical_name}</span>
            </p>
          )}
        </div>

        {opp.summary && (
          <p className="text-sm text-slate-300 leading-relaxed max-w-4xl">
            {opp.summary}
          </p>
        )}

        {/* External Portal CTA */}
        {opp.application_url && (
          <div className="pt-2">
            <a
              href={opp.application_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs shadow-md transition-all"
            >
              <span>Visit Official Application Portal</span>
              <ExternalLink className="w-4 h-4" />
            </a>
          </div>
        )}
      </div>

      {/* 2-Column Intelligence Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left 2 Cols: Timeline, Fact Consensus, Discrepancies, Sources */}
        <div className="lg:col-span-2 space-y-6">
          {/* Conflict Alert (if any discrepancies detected) */}
          {opp.conflicts && opp.conflicts.length > 0 && (
            <ConflictAlert conflicts={opp.conflicts} />
          )}

          {/* Fact Consensus Table */}
          {opp.consensus && opp.consensus.length > 0 && (
            <ConsensusCard consensusList={opp.consensus} />
          )}

          {/* Lifecycle & Milestone Timeline */}
          <Card className="space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold font-mono text-slate-200 uppercase tracking-wider">
                Event Schedule & Milestones
              </h3>
              <span className="text-xs text-slate-500 font-mono">
                {opp.events?.length || 0} tracked phases
              </span>
            </div>
            <LifecycleTimeline events={opp.events || []} />
          </Card>

          {/* Corroborating Sources Evidence */}
          <Card className="space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold font-mono text-slate-200 uppercase tracking-wider">
                Corroborating Sources & Provenance
              </h3>
              <span className="text-xs text-slate-500 font-mono">
                {opp.sources?.length || 0} source records
              </span>
            </div>
            <SourceEvidenceList sources={opp.sources || []} />
          </Card>

          {/* Program Information / Raw Collapsible */}
          {opp.raw_content && (
            <Card className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold font-mono text-slate-200 uppercase tracking-wider">
                  Raw Ingested Content
                </h3>
                <Button
                  variant="ghost"
                  size="xs"
                  onClick={() => setShowRaw(!showRaw)}
                >
                  {showRaw ? 'Hide Raw' : 'Inspect Raw Data'}
                </Button>
              </div>
              {showRaw && (
                <pre className="p-3.5 rounded-lg bg-slate-950 border border-slate-800 text-[11px] font-mono text-slate-400 overflow-x-auto whitespace-pre-wrap max-h-64">
                  {opp.raw_content}
                </pre>
              )}
            </Card>
          )}
        </div>

        {/* Right 1 Col: Intelligence Verification & Personalized Match Breakdown */}
        <div className="space-y-6">
          {/* Trust Gauge */}
          <Card className="space-y-3">
            <h3 className="text-xs font-bold font-mono text-slate-300 uppercase tracking-wider">
              Verification Engine
            </h3>
            <TrustIndicator
              confidenceScore={opp.verification_confidence ?? opp.confidence_score}
              sourceCount={opp.source_count}
              officialSourcePresent={opp.official_source_present}
            />
          </Card>

          {/* Personalized Match Dial */}
          {relevance && (
            <Card className="space-y-4 border-emerald-800/40 bg-slate-900/90">
              <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-emerald-400" />
                  <h3 className="text-xs font-bold font-mono text-slate-200 uppercase tracking-wider">
                    Your Personal Match
                  </h3>
                </div>
                <span className="text-sm font-bold font-mono text-emerald-400">
                  {Math.round(relevance.overall_score * 100)}%
                </span>
              </div>

              {/* Match Factors */}
              <div className="space-y-2 text-xs font-mono">
                <div className="flex justify-between text-slate-400">
                  <span>Skill Alignment</span>
                  <span className="text-slate-200 font-semibold">
                    {Math.round(relevance.breakdown.skill_score * 100)}%
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Domain Relevance</span>
                  <span className="text-slate-200 font-semibold">
                    {Math.round(relevance.breakdown.domain_score * 100)}%
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Interest Resonance</span>
                  <span className="text-slate-200 font-semibold">
                    {Math.round(relevance.breakdown.interest_score * 100)}%
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Academic Eligibility</span>
                  <span className="text-slate-200 font-semibold">
                    {Math.round(relevance.breakdown.education_score * 100)}%
                  </span>
                </div>
              </div>

              {/* Matched Skills Chips */}
              {relevance.matched_skills && relevance.matched_skills.length > 0 && (
                <div className="pt-2 border-t border-slate-800/60">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 block mb-1.5">
                    Matched Skills
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {relevance.matched_skills.map((skill: string) => (
                      <span
                        key={skill}
                        className="px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-700/50 text-[10px] font-mono"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Eligibility Status */}
              <div className="pt-2 border-t border-slate-800/60 flex items-center gap-2">
                {relevance.is_eligible ? (
                  <div className="flex items-center gap-1.5 text-xs text-emerald-400 font-medium">
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Eligible for your graduation profile</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-1.5 text-xs text-amber-400 font-medium">
                    <AlertCircle className="w-4 h-4" />
                    <span>Potential graduation or domain mismatch</span>
                  </div>
                )}
              </div>
            </Card>
          )}

          {/* Target Demographics / Eligibility */}
          <Card className="space-y-3 text-xs">
            <h3 className="text-xs font-bold font-mono text-slate-300 uppercase tracking-wider">
              Eligibility & Criteria
            </h3>
            <div className="space-y-2 text-slate-300">
              {opp.target_audience && (
                <div>
                  <span className="text-slate-500 block text-[10px] uppercase font-mono">
                    Target Audience
                  </span>
                  <p className="mt-0.5">{opp.target_audience}</p>
                </div>
              )}
              {opp.eligibility && (
                <div>
                  <span className="text-slate-500 block text-[10px] uppercase font-mono">
                    Criteria
                  </span>
                  <p className="mt-0.5">{opp.eligibility}</p>
                </div>
              )}
              {opp.required_skills && opp.required_skills.length > 0 && (
                <div>
                  <span className="text-slate-500 block text-[10px] uppercase font-mono">
                    Required Skills
                  </span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {opp.required_skills.map((s: string) => (
                      <Badge key={s} variant="slate" size="xs" className="font-mono">
                        {s}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};
