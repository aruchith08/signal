import React from 'react';
import { FactConsensus } from '../../types/opportunity';
import { CheckCircle, AlertTriangle, Layers } from 'lucide-react';
import { Badge } from '../common/Badge';

interface ConsensusCardProps {
  consensusList: FactConsensus[];
}

export const ConsensusCard: React.FC<ConsensusCardProps> = ({ consensusList }) => {
  if (!consensusList || consensusList.length === 0) {
    return null;
  }

  return (
    <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-emerald-400" />
          <h4 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
            Multi-Source Fact Consensus
          </h4>
        </div>
        <Badge variant="success" size="xs">
          Cross-Verified Facts
        </Badge>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
        {consensusList.map((fact) => {
          const ratioPercent = Math.round(fact.agreement_ratio * 100);
          const isAgreed = fact.status === 'AGREED' || fact.agreement_ratio >= 0.7;

          return (
            <div
              key={fact.id || fact.field_name}
              className="p-2.5 rounded-lg border border-slate-800/80 bg-[#0A0E17]/80 flex flex-col justify-between"
            >
              <div className="flex items-center justify-between text-xs">
                <span className="font-mono text-slate-400 font-medium capitalize">
                  {fact.field_name.replace(/_/g, ' ')}
                </span>
                <span
                  className={`inline-flex items-center gap-1 text-[11px] font-mono ${
                    isAgreed ? 'text-emerald-400' : 'text-amber-400'
                  }`}
                >
                  {isAgreed ? (
                    <CheckCircle className="w-3 h-3" />
                  ) : (
                    <AlertTriangle className="w-3 h-3" />
                  )}
                  {fact.agreeing_sources_count}/{fact.total_reporting_sources} sources ({ratioPercent}%)
                </span>
              </div>

              <div className="mt-1.5 text-xs font-medium text-slate-200 truncate">
                {fact.consensus_value}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
