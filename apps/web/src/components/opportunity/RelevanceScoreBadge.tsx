import React from 'react';
import { Sparkles, CheckCircle2, AlertCircle } from 'lucide-react';
import { Badge } from '../common/Badge';

interface RelevanceScoreBadgeProps {
  score: number;
  isEligible?: boolean;
  tier?: string;
  size?: 'xs' | 'sm' | 'md';
}

export const RelevanceScoreBadge: React.FC<RelevanceScoreBadgeProps> = ({
  score,
  isEligible = true,
  tier,
  size = 'sm',
}) => {
  const percent = Math.round(score * 100);

  const getTierDetails = () => {
    if (percent >= 80 || tier === 'HIGH') {
      return {
        variant: 'success' as const,
        label: 'High Match',
        color: 'text-emerald-400',
        bg: 'bg-emerald-950/40 border-emerald-700/50',
      };
    }
    if (percent >= 50 || tier === 'MEDIUM') {
      return {
        variant: 'info' as const,
        label: 'Medium Match',
        color: 'text-sky-400',
        bg: 'bg-sky-950/40 border-sky-700/50',
      };
    }
    return {
      variant: 'slate' as const,
      label: 'Low Match',
      color: 'text-slate-400',
      bg: 'bg-slate-900 border-slate-800',
    };
  };

  const details = getTierDetails();

  return (
    <div className="flex items-center gap-1.5">
      <div
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border font-mono ${details.bg}`}
      >
        <Sparkles className={`w-3.5 h-3.5 ${details.color}`} />
        <span className={`text-xs font-bold ${details.color}`}>{percent}%</span>
        <span className="text-[11px] text-slate-400">Match</span>
      </div>

      {!isEligible && (
        <Badge variant="warning" size={size} className="gap-1">
          <AlertCircle className="w-3 h-3 text-amber-400" />
          <span>Eligibility Flag</span>
        </Badge>
      )}
      {isEligible && percent >= 75 && (
        <Badge variant="success" size={size} className="gap-1">
          <CheckCircle2 className="w-3 h-3 text-emerald-400" />
          <span>Eligible</span>
        </Badge>
      )}
    </div>
  );
};
