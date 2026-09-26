import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Opportunity } from '../../types/opportunity';
import { Badge } from '../common/Badge';
import { VerificationBadge } from './VerificationBadge';
import { SaveFollowButtons } from './SaveFollowButtons';
import { EligibilityChips } from './EligibilityChips';
import { RelevanceScoreBadge } from './RelevanceScoreBadge';
import { Calendar, Clock, ChevronRight, Sparkles } from 'lucide-react';

interface OpportunityCardProps {
  opportunity: Opportunity;
  matchScore?: number;
  isEligible?: boolean;
  matchTier?: string;
  matchedSkills?: string[];
  daysRemaining?: number | null;
  activeDeadline?: string | null;
}

export const OpportunityCard: React.FC<OpportunityCardProps> = ({
  opportunity,
  matchScore,
  isEligible = true,
  matchTier,
  matchedSkills,
  daysRemaining,
  activeDeadline,
}) => {
  const navigate = useNavigate();

  const handleCardClick = () => {
    navigate(`/opportunities/${opportunity.id}`);
  };

  const formatDeadline = (dateStr?: string | null) => {
    if (!dateStr) return null;
    try {
      return new Date(dateStr).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div
      onClick={handleCardClick}
      className="group relative flex flex-col justify-between rounded-xl border border-slate-800 bg-[#0F172A]/80 p-5 shadow-lg backdrop-blur-sm transition-all duration-200 hover:border-slate-700 hover:bg-[#131D33]/90 hover:shadow-xl cursor-pointer"
    >
      {/* Top Meta Row */}
      <div className="space-y-2.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="purple" size="xs" className="font-mono uppercase tracking-wider">
              {opportunity.category || 'OPPORTUNITY'}
            </Badge>

            <VerificationBadge
              status={opportunity.verification_status}
              official={opportunity.official}
              confidence={opportunity.verification_confidence ?? opportunity.confidence_score}
              sourceCount={opportunity.source_count}
              size="xs"
            />

            {opportunity.year && (
              <Badge variant="slate" size="xs" className="font-mono">
                {opportunity.year}
              </Badge>
            )}
          </div>

          <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
            <SaveFollowButtons opportunityId={opportunity.id} title={opportunity.title} size="sm" />
          </div>
        </div>

        {/* Title & Canonical Name */}
        <div>
          <h3 className="text-base font-semibold text-slate-100 group-hover:text-emerald-400 transition-colors line-clamp-1">
            {opportunity.title}
          </h3>
          {opportunity.canonical_name && opportunity.canonical_name !== opportunity.title && (
            <p className="text-xs text-slate-400 font-mono mt-0.5 line-clamp-1">
              Program: {opportunity.canonical_name}
            </p>
          )}
        </div>

        {/* Summary Snippet */}
        {opportunity.summary && (
          <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
            {opportunity.summary}
          </p>
        )}
      </div>

      {/* Middle: Personalized Match & Skills Highlight (if provided) */}
      {matchScore !== undefined && (
        <div className="mt-3.5 pt-3 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-2">
          <RelevanceScoreBadge
            score={matchScore}
            isEligible={isEligible}
            tier={matchTier}
            size="xs"
          />

          {matchedSkills && matchedSkills.length > 0 && (
            <div className="flex items-center gap-1 text-[11px] text-emerald-400 font-mono">
              <Sparkles className="w-3 h-3" />
              <span>Matches: {matchedSkills.slice(0, 2).join(', ')}</span>
            </div>
          )}
        </div>
      )}

      {/* Bottom Row: Eligibility Chips & Deadline */}
      <div className="mt-4 pt-3 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-3">
        <EligibilityChips
          country={opportunity.country}
          targetAudience={opportunity.target_audience}
          eligibility={opportunity.eligibility}
          requiredSkills={opportunity.required_skills}
          tags={opportunity.tags}
          maxSkills={2}
        />

        <div className="flex items-center gap-2 text-xs font-mono shrink-0">
          {(daysRemaining !== undefined && daysRemaining !== null) || activeDeadline ? (
            <div
              className={`flex items-center gap-1 font-semibold ${
                daysRemaining !== null && daysRemaining !== undefined && daysRemaining <= 3
                  ? 'text-rose-400'
                  : daysRemaining !== null && daysRemaining !== undefined && daysRemaining <= 7
                  ? 'text-amber-400'
                  : 'text-slate-300'
              }`}
            >
              <Clock className="w-3.5 h-3.5 text-amber-400" />
              <span>
                {daysRemaining !== null && daysRemaining !== undefined
                  ? daysRemaining === 0
                    ? 'Closes Today'
                    : daysRemaining < 0
                    ? 'Closed'
                    : `${daysRemaining}d left`
                  : formatDeadline(activeDeadline)}
              </span>
            </div>
          ) : (
            <span className="text-slate-500 flex items-center gap-1 text-[11px]">
              <Calendar className="w-3 h-3" />
              Ongoing
            </span>
          )}

          <ChevronRight className="w-4 h-4 text-slate-600 group-hover:text-emerald-400 group-hover:translate-x-0.5 transition-all" />
        </div>
      </div>
    </div>
  );
};
