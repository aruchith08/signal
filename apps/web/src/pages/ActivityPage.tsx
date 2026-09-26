import React, { useState, useEffect } from 'react';
import { getRecentActivity, getRegisteredSources } from '../services/api/activities';
import { ActivityItem, SourceItem } from '../services/api/activities';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { 
  Activity, 
  Globe, 
  ExternalLink, 
  ShieldCheck, 
  Clock, 
  Cpu, 
  Database,
  Radio 
} from 'lucide-react';

export const ActivityPage: React.FC = () => {
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    async function load() {
      try {
        setLoading(true);
        const [srcs, acts] = await Promise.all([
          getRegisteredSources().catch(() => []),
          getRecentActivity(30).catch(() => []),
        ]);
        if (isMounted) {
          setSources(srcs);
          setActivities(acts);
        }
      } catch (err) {
        console.warn('Failed to load telemetry', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    load();
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-bold font-mono text-slate-100 tracking-tight">
          SYSTEM TELEMETRY & SOURCE REGISTRY
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Real-time crawler health, source reliability metrics, and opportunity lifecycle audit logs.
        </p>
      </div>

      {/* Source Health Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Radio className="w-4 h-4 text-emerald-400" />
            <h2 className="text-sm font-bold font-mono text-slate-200 uppercase tracking-wider">
              Monitored Sources ({sources.length})
            </h2>
          </div>
          <Badge variant="success" size="xs">
            Multi-Source Network
          </Badge>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {sources.map((src) => {
            const rel = Math.round(src.reliability_score * 100);

            return (
              <Card key={src.id} className="p-4 space-y-2.5 border-slate-800/80 bg-slate-900/60">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h4 className="text-xs font-bold text-slate-100 truncate">
                        {src.name}
                      </h4>
                      <span className="w-2 h-2 rounded-full bg-emerald-400 shrink-0" title="Active" />
                    </div>
                    <span className="text-[10px] font-mono text-slate-500 uppercase">
                      {src.source_type}
                    </span>
                  </div>

                  <span
                    className={`text-xs font-mono font-bold px-1.5 py-0.5 rounded ${
                      rel >= 85
                        ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                        : 'bg-amber-950 text-amber-400 border border-amber-800'
                    }`}
                  >
                    {rel}%
                  </span>
                </div>

                <div className="pt-2 border-t border-slate-800/60 flex items-center justify-between text-[11px] font-mono">
                  <a
                    href={src.base_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-slate-400 hover:text-emerald-400 flex items-center gap-1 truncate max-w-[180px]"
                  >
                    <Globe className="w-3 h-3 shrink-0" />
                    <span className="truncate">{src.base_url}</span>
                  </a>

                  {src.last_polled_at && (
                    <span className="text-slate-500 text-[10px]">
                      {new Date(src.last_polled_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      </div>

      {/* Audit Log Stream */}
      <Card className="space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Database className="w-4 h-4 text-emerald-400" />
            <h3 className="text-xs font-bold font-mono text-slate-200 uppercase tracking-wider">
              Discovery & Lifecycle Event Stream
            </h3>
          </div>
          <span className="text-xs font-mono text-slate-500">
            {activities.length} recent entries
          </span>
        </div>

        {activities.length === 0 ? (
          <p className="text-xs text-slate-500 font-mono py-4 text-center">
            No audit log entries recorded in this window.
          </p>
        ) : (
          <div className="space-y-2 divide-y divide-slate-800/60 font-mono">
            {activities.map((act) => (
              <div key={act.id} className="pt-2.5 first:pt-0 flex items-start justify-between gap-4 text-xs">
                <div className="space-y-0.5 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 text-[10px] font-semibold uppercase">
                      {act.action}
                    </span>
                    <span className="text-slate-400 text-xs truncate">
                      {act.entity_type} {act.entity_id ? `(${act.entity_id.slice(0, 8)})` : ''}
                    </span>
                  </div>
                  {act.details && (
                    <p className="text-[11px] text-slate-500 truncate max-w-xl">
                      {JSON.stringify(act.details)}
                    </p>
                  )}
                </div>

                <span className="text-[10px] text-slate-500 shrink-0">
                  {new Date(act.created_at).toLocaleTimeString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
};
