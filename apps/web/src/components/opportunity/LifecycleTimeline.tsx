import React from 'react';
import { OpportunityEvent } from '../../types/opportunity';
import { Calendar, Clock, AlertCircle, CheckCircle2 } from 'lucide-react';
import { Badge } from '../common/Badge';

interface LifecycleTimelineProps {
  events: OpportunityEvent[];
}

export const LifecycleTimeline: React.FC<LifecycleTimelineProps> = ({ events }) => {
  if (!events || events.length === 0) {
    return (
      <div className="p-4 rounded-lg bg-slate-900/60 border border-slate-800 text-xs text-slate-400">
        No schedule or milestone events tracked for this opportunity yet.
      </div>
    );
  }

  // Sort events by start date or deadline
  const sortedEvents = [...events].sort((a, b) => {
    const dateA = a.deadline_date || a.start_date || a.created_at || '';
    const dateB = b.deadline_date || b.start_date || b.created_at || '';
    return dateA.localeCompare(dateB);
  });

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return null;
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
    } catch {
      return dateStr;
    }
  };

  const calculateDaysRemaining = (deadlineStr: string | null) => {
    if (!deadlineStr) return null;
    try {
      const now = new Date();
      const target = new Date(deadlineStr);
      const diffTime = target.getTime() - now.getTime();
      return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    } catch {
      return null;
    }
  };

  return (
    <div className="space-y-4">
      <div className="relative pl-6 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-800">
        {sortedEvents.map((evt, idx) => {
          const daysLeft = calculateDaysRemaining(evt.deadline_date);
          const isCurrent = evt.is_current;
          const isPassed = daysLeft !== null && daysLeft < 0;

          return (
            <div key={evt.id || idx} className="relative mb-6 last:mb-0 group">
              {/* Timeline Marker Dot */}
              <div
                className={`absolute -left-[19px] top-1.5 w-4 h-4 rounded-full border-2 transition-colors flex items-center justify-center ${
                  isCurrent
                    ? 'bg-emerald-500 border-emerald-300 ring-4 ring-emerald-500/20'
                    : isPassed
                    ? 'bg-slate-800 border-slate-700 text-slate-500'
                    : 'bg-slate-900 border-sky-500 ring-2 ring-sky-500/20'
                }`}
              >
                {isCurrent && <div className="w-1.5 h-1.5 bg-white rounded-full animate-pulse" />}
              </div>

              {/* Event Content Box */}
              <div
                className={`p-3.5 rounded-lg border transition-all ${
                  isCurrent
                    ? 'bg-slate-900/90 border-emerald-500/50 shadow-md shadow-emerald-950/30'
                    : 'bg-slate-900/40 border-slate-800/80 hover:border-slate-750'
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sm text-slate-200">
                      {evt.event_name}
                    </span>
                    <Badge variant="slate" size="xs" className="font-mono uppercase text-[10px]">
                      {evt.event_type}
                    </Badge>
                  </div>

                  <div className="flex items-center gap-2">
                    {isCurrent && (
                      <Badge variant="success" size="xs">
                        <CheckCircle2 className="w-3 h-3" />
                        Active Phase
                      </Badge>
                    )}
                    {daysLeft !== null && (
                      <span
                        className={`text-xs font-mono font-medium ${
                          daysLeft < 0
                            ? 'text-slate-500'
                            : daysLeft <= 3
                            ? 'text-rose-400 font-bold'
                            : daysLeft <= 7
                            ? 'text-amber-400'
                            : 'text-emerald-400'
                        }`}
                      >
                        {daysLeft < 0
                          ? 'Passed'
                          : daysLeft === 0
                          ? 'Closes Today!'
                          : `${daysLeft}d left`}
                      </span>
                    )}
                  </div>
                </div>

                {/* Dates Row */}
                <div className="mt-2 flex flex-wrap items-center gap-4 text-xs text-slate-400 font-mono">
                  {evt.start_date && (
                    <div className="flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5 text-slate-500" />
                      <span>Start: {formatDate(evt.start_date)}</span>
                    </div>
                  )}

                  {evt.deadline_date && (
                    <div className="flex items-center gap-1.5 text-amber-300/90 font-medium">
                      <Clock className="w-3.5 h-3.5 text-amber-400" />
                      <span>Deadline: {formatDate(evt.deadline_date)}</span>
                    </div>
                  )}

                  {evt.end_date && !evt.deadline_date && (
                    <div className="flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5 text-slate-500" />
                      <span>End: {formatDate(evt.end_date)}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
