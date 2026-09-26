import React from 'react';
import { OpportunitySourceRecord } from '../../types/opportunity';
import { ExternalLink, ShieldCheck, Globe, Clock, ShieldAlert } from 'lucide-react';
import { Badge } from '../common/Badge';

interface SourceEvidenceListProps {
  sources: OpportunitySourceRecord[];
}

export const SourceEvidenceList: React.FC<SourceEvidenceListProps> = ({ sources }) => {
  if (!sources || sources.length === 0) {
    return (
      <div className="p-4 rounded-lg bg-slate-900/60 border border-slate-800 text-xs text-slate-400">
        No provenance source records attached to this opportunity.
      </div>
    );
  }

  const formatTimestamp = (ts?: string) => {
    if (!ts) return null;
    try {
      return new Date(ts).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return ts;
    }
  };

  return (
    <div className="space-y-2.5">
      {sources.map((src, index) => {
        const reliability = Math.round((src.reliability_score || 0.8) * 100);

        return (
          <div
            key={src.id || index}
            className="flex flex-col sm:flex-row sm:items-center justify-between p-3 rounded-lg border border-slate-800/80 bg-slate-900/70 hover:border-slate-700 transition-colors gap-3"
          >
            <div className="flex items-start gap-3 min-w-0">
              <div className="mt-0.5 p-1.5 rounded-md bg-slate-800 border border-slate-700/60 text-slate-400">
                {src.is_official ? (
                  <ShieldCheck className="w-4 h-4 text-sky-400" />
                ) : (
                  <Globe className="w-4 h-4 text-slate-400" />
                )}
              </div>

              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-slate-200 truncate">
                    {src.source_name || 'Web Ingestion Source'}
                  </span>
                  {src.is_official ? (
                    <Badge variant="info" size="xs">
                      Official
                    </Badge>
                  ) : (
                    <Badge variant="slate" size="xs">
                      Aggregator
                    </Badge>
                  )}
                </div>

                {src.source_url && (
                  <a
                    href={src.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-0.5 inline-flex items-center gap-1 text-[11px] text-slate-400 hover:text-emerald-400 transition-colors truncate max-w-xs sm:max-w-md font-mono"
                  >
                    <span className="truncate">{src.source_url}</span>
                    <ExternalLink className="w-2.5 h-2.5 shrink-0" />
                  </a>
                )}
              </div>
            </div>

            <div className="flex items-center gap-4 text-xs shrink-0 self-end sm:self-center font-mono">
              <div className="flex flex-col items-end">
                <span className="text-[10px] text-slate-500 uppercase tracking-wider">
                  Reliability
                </span>
                <span
                  className={`font-bold ${
                    reliability >= 85
                      ? 'text-emerald-400'
                      : reliability >= 60
                      ? 'text-amber-400'
                      : 'text-rose-400'
                  }`}
                >
                  {reliability}%
                </span>
              </div>

              {src.extracted_at && (
                <div className="hidden md:flex flex-col items-end text-slate-500">
                  <span className="text-[10px] uppercase tracking-wider">Observed</span>
                  <span className="text-[11px] flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {formatTimestamp(src.extracted_at)}
                  </span>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};
