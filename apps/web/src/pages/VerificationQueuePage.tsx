import React, { useState, useEffect } from 'react';
import { getVerificationQueue, getOpenConflicts, resolveReviewItem, resolveConflict } from '../services/api/verification';
import { VerificationQueueItem } from '../services/api/verification';
import { SourceConflict } from '../types/opportunity';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { EmptyState } from '../components/common/EmptyState';
import { useToast } from '../contexts/ToastContext';
import { 
  ShieldAlert, 
  CheckCircle2, 
  XCircle, 
  GitMerge, 
  AlertTriangle, 
  HelpCircle, 
  FileText 
} from 'lucide-react';

export const VerificationQueuePage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'QUEUE' | 'CONFLICTS'>('QUEUE');
  const [queueItems, setQueueItems] = useState<VerificationQueueItem[]>([]);
  const [conflicts, setConflicts] = useState<SourceConflict[]>([]);
  const [loading, setLoading] = useState(true);
  const { showToast } = useToast();

  const loadAll = async () => {
    try {
      setLoading(true);
      const [q, c] = await Promise.all([
        getVerificationQueue().catch(() => []),
        getOpenConflicts().catch(() => []),
      ]);
      setQueueItems(q || []);
      setConflicts(c || []);
    } catch (err: any) {
      console.warn('Failed to load verification review data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  const handleResolveReview = async (id: string, action: 'APPROVE' | 'REJECT' | 'MERGE') => {
    try {
      await resolveReviewItem(id, action);
      showToast(`Item ${action.toLowerCase()}d successfully`, { type: 'success' });
      setQueueItems((prev) => prev.filter((i) => i.id !== id));
    } catch (err: any) {
      showToast('Resolution Failed', { description: err.message, type: 'error' });
    }
  };

  const handleResolveConflict = async (conflictId: string, value: string) => {
    try {
      await resolveConflict(conflictId, {
        resolved_value: value,
        resolution_strategy: 'MANUAL_OFFICIAL_OVERRIDE',
      });
      showToast('Conflict Resolved', { type: 'success' });
      setConflicts((prev) => prev.filter((c) => c.id !== conflictId));
    } catch (err: any) {
      showToast('Resolution Failed', { description: err.message, type: 'error' });
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold font-mono text-slate-100 tracking-tight">
          CROSS-SOURCE VERIFICATION & REVIEW QUEUE
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Review ambiguous deduplication candidates and adjudicate multi-source data conflicts.
        </p>

        {/* Sub-tabs */}
        <div className="mt-6 flex items-center gap-2 border-b border-slate-800 pb-2">
          <button
            onClick={() => setActiveTab('QUEUE')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold font-mono transition-all ${
              activeTab === 'QUEUE'
                ? 'bg-emerald-950/70 text-emerald-300 border border-emerald-600/50 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
            }`}
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>Ambiguity Queue ({queueItems.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('CONFLICTS')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold font-mono transition-all ${
              activeTab === 'CONFLICTS'
                ? 'bg-amber-950/70 text-amber-300 border border-amber-600/50 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
            }`}
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>Data Conflicts ({conflicts.length})</span>
          </button>
        </div>
      </div>

      {loading ? (
        <div className="space-y-4 animate-pulse">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-32 rounded-xl bg-slate-900 border border-slate-800" />
          ))}
        </div>
      ) : activeTab === 'QUEUE' ? (
        queueItems.length === 0 ? (
          <EmptyState
            icon={<CheckCircle2 className="w-10 h-10 text-emerald-400/60" />}
            title="Review Queue is Clean"
            description="The multi-tier deduplication engine resolved all incoming opportunities automatically with high confidence."
          />
        ) : (
          <div className="space-y-4">
            {queueItems.map((item) => (
              <Card key={item.id} className="p-5 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-bold text-slate-200">
                      Candidate ID: {item.id.slice(0, 8)}
                    </span>
                    <Badge variant="warning" size="xs">
                      Match Confidence: {Math.round((item.match_confidence || 0.65) * 100)}%
                    </Badge>
                  </div>
                  <span className="text-[11px] font-mono text-slate-500">
                    {new Date(item.created_at).toLocaleString()}
                  </span>
                </div>

                <div className="text-xs text-slate-300 space-y-1">
                  <div>
                    <span className="text-slate-500 font-mono">Existing: </span>
                    <span className="font-semibold">{item.opportunity_title || 'TCS CodeVita 2026'}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 font-mono">Candidate: </span>
                    <span className="font-semibold">{item.candidate_title || 'TCS Global Coding Contest Season 14'}</span>
                  </div>
                  {item.ambiguity_reason && (
                    <p className="text-slate-400 text-[11px] pt-1">
                      Reason: {item.ambiguity_reason}
                    </p>
                  )}
                </div>

                <div className="pt-3 border-t border-slate-800 flex items-center justify-end gap-2">
                  <Button
                    variant="outline"
                    size="xs"
                    onClick={() => handleResolveReview(item.id, 'REJECT')}
                  >
                    <XCircle className="w-3.5 h-3.5 text-rose-400" />
                    Reject Match
                  </Button>
                  <Button
                    variant="secondary"
                    size="xs"
                    onClick={() => handleResolveReview(item.id, 'MERGE')}
                  >
                    <GitMerge className="w-3.5 h-3.5 text-sky-400" />
                    Merge as Alias
                  </Button>
                  <Button
                    variant="primary"
                    size="xs"
                    onClick={() => handleResolveReview(item.id, 'APPROVE')}
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Approve Duplicate
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        )
      ) : conflicts.length === 0 ? (
        <EmptyState
          icon={<CheckCircle2 className="w-10 h-10 text-emerald-400/60" />}
          title="No Open Source Conflicts"
          description="All multi-source reporting fields have reached consensus or were validated against official primary sources."
        />
      ) : (
        <div className="space-y-4">
          {conflicts.map((conflict) => (
            <Card key={conflict.id} className="p-5 space-y-3 border-amber-800/40">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-mono">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  <span className="text-xs font-bold text-slate-200 capitalize">
                    Field: {conflict.field_name.replace(/_/g, ' ')}
                  </span>
                </div>
                <Badge variant="warning" size="xs">
                  {conflict.severity} SEVERITY
                </Badge>
              </div>

              <p className="text-xs text-slate-400">
                Sources report conflicting values for this field. Select which value to adopt as truth:
              </p>

              {conflict.values_by_source && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-2">
                  {Object.entries(conflict.values_by_source).map(([source, val]) => (
                    <div
                      key={source}
                      className="p-2.5 rounded-lg border border-slate-800 bg-slate-950 flex items-center justify-between"
                    >
                      <div className="min-w-0 pr-2">
                        <span className="text-[10px] uppercase font-mono text-slate-500 block truncate">
                          Source: {source}
                        </span>
                        <span className="text-xs font-semibold text-slate-200">
                          {String(val)}
                        </span>
                      </div>
                      <Button
                        variant="outline"
                        size="xs"
                        onClick={() => handleResolveConflict(conflict.id, String(val))}
                      >
                        Accept Value
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};
