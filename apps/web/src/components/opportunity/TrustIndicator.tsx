import React from 'react';
import { Shield, Check, AlertCircle } from 'lucide-react';

interface TrustIndicatorProps {
  confidenceScore: number;
  sourceCount: number;
  officialSourcePresent: boolean;
}

export const TrustIndicator: React.FC<TrustIndicatorProps> = ({
  confidenceScore,
  sourceCount,
  officialSourcePresent,
}) => {
  const percentage = Math.round((confidenceScore || 0) * 100);

  const getScoreColor = () => {
    if (percentage >= 80) return 'text-emerald-400 bg-emerald-500';
    if (percentage >= 50) return 'text-amber-400 bg-amber-500';
    return 'text-rose-400 bg-rose-500';
  };

  return (
    <div className="flex flex-col gap-1.5 p-3 rounded-lg bg-slate-900/90 border border-slate-800">
      <div className="flex items-center justify-between text-xs">
        <span className="text-slate-400 font-medium flex items-center gap-1.5">
          <Shield className="w-3.5 h-3.5 text-slate-500" />
          Intelligence Confidence
        </span>
        <span className={`font-mono font-bold ${getScoreColor().split(' ')[0]}`}>
          {percentage}%
        </span>
      </div>

      {/* Progress Bar */}
      <div className="h-1.5 w-full rounded-full bg-slate-800 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${getScoreColor().split(' ')[1]}`}
          style={{ width: `${Math.min(100, Math.max(0, percentage))}%` }}
        />
      </div>

      <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-slate-800/60 font-mono">
        <span className="flex items-center gap-1">
          {officialSourcePresent ? (
            <>
              <Check className="w-3 h-3 text-sky-400" />
              <span className="text-sky-300">Official Publisher</span>
            </>
          ) : (
            <>
              <AlertCircle className="w-3 h-3 text-slate-500" />
              <span>Third-Party Aggregator</span>
            </>
          )}
        </span>
        <span>
          {sourceCount} {sourceCount === 1 ? 'source' : 'corroborating sources'}
        </span>
      </div>
    </div>
  );
};
