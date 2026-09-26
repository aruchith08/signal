import React from 'react';
import { VerificationStatus } from '../../types/opportunity';
import { Badge } from '../common/Badge';
import { ShieldCheck, CheckCheck, AlertTriangle, HelpCircle, AlertOctagon } from 'lucide-react';

interface VerificationBadgeProps {
  status: VerificationStatus;
  official?: boolean;
  confidence?: number | null;
  sourceCount?: number;
  size?: 'xs' | 'sm' | 'md';
}

export const VerificationBadge: React.FC<VerificationBadgeProps> = ({
  status,
  official,
  confidence,
  sourceCount,
  size = 'sm',
}) => {
  const normStatus = (status || '').toUpperCase();

  if (official || normStatus === 'OFFICIAL') {
    return (
      <Badge variant="info" size={size} className="gap-1.5 font-mono">
        <ShieldCheck className="w-3.5 h-3.5 text-sky-400 shrink-0" />
        <span>Official Source</span>
        {confidence !== undefined && confidence !== null && (
          <span className="opacity-70 text-[10px]">({Math.round(confidence * 100)}%)</span>
        )}
      </Badge>
    );
  }

  if (normStatus === 'CROSS_SOURCE_VERIFIED') {
    return (
      <Badge variant="success" size={size} className="gap-1.5 font-mono">
        <CheckCheck className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
        <span>Cross-Verified</span>
        {sourceCount && sourceCount > 1 ? (
          <span className="bg-emerald-800/50 px-1 rounded text-[10px]">{sourceCount} sources</span>
        ) : confidence !== undefined && confidence !== null ? (
          <span className="opacity-70 text-[10px]">({Math.round(confidence * 100)}%)</span>
        ) : null}
      </Badge>
    );
  }

  if (normStatus === 'CONFLICTING') {
    return (
      <Badge variant="error" size={size} className="gap-1.5 font-mono">
        <AlertTriangle className="w-3.5 h-3.5 text-rose-400 shrink-0" />
        <span>Source Conflict</span>
      </Badge>
    );
  }

  if (normStatus === 'SUSPICIOUS' || normStatus === 'REJECTED') {
    return (
      <Badge variant="error" size={size} className="gap-1.5 font-mono">
        <AlertOctagon className="w-3.5 h-3.5 text-rose-400 shrink-0" />
        <span>Flagged</span>
      </Badge>
    );
  }

  return (
    <Badge variant="slate" size={size} className="gap-1.5 font-mono">
      <HelpCircle className="w-3.5 h-3.5 text-slate-400 shrink-0" />
      <span>Single Source</span>
      {confidence !== undefined && confidence !== null && (
        <span className="opacity-60 text-[10px]">({Math.round(confidence * 100)}%)</span>
      )}
    </Badge>
  );
};
