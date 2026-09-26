import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getUserNotifications, NotificationItem } from '../services/api/activities';
import { useAuth } from '../contexts/AuthContext';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { EmptyState } from '../components/common/EmptyState';
import { Bell, Send, Clock, ChevronRight, ExternalLink } from 'lucide-react';

export const NotificationsPage: React.FC = () => {
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const { user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    let isMounted = true;
    async function load() {
      if (!user?.id) return;
      try {
        setLoading(true);
        const data = await getUserNotifications(user.id);
        if (isMounted) setNotifications(data);
      } catch (err) {
        console.warn('Failed to load notifications', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    load();
    return () => {
      isMounted = false;
    };
  }, [user?.id]);

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-xl font-bold font-mono text-slate-100 tracking-tight">
          INTELLIGENCE NOTIFICATIONS & ALERTS
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Historical log of priority alerts delivered to your profile and Telegram channel.
        </p>
      </div>

      {loading ? (
        <div className="space-y-3 animate-pulse">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-20 bg-slate-900 rounded-xl border border-slate-800" />
          ))}
        </div>
      ) : notifications.length === 0 ? (
        <EmptyState
          icon={<Bell className="w-10 h-10 text-slate-600" />}
          title="No alerts logged yet"
          description="When high-priority opportunities or deadline countdowns meet your relevance threshold, alerts appear here."
        />
      ) : (
        <div className="space-y-3">
          {notifications.map((notif) => {
            const isCritical = notif.priority === 'CRITICAL';
            const isTelegram = notif.channel === 'TELEGRAM';

            return (
              <div
                key={notif.id}
                onClick={() => {
                  if (notif.opportunity_id) navigate(`/opportunities/${notif.opportunity_id}`);
                }}
                className="p-4 rounded-xl border border-slate-800 bg-slate-900/80 hover:border-slate-700 hover:bg-[#131D33] transition-all cursor-pointer flex items-start justify-between gap-4 group"
              >
                <div className="flex items-start gap-3 min-w-0">
                  <div
                    className={`mt-0.5 p-2 rounded-lg border ${
                      isTelegram
                        ? 'bg-sky-950/60 border-sky-800/60 text-sky-400'
                        : 'bg-emerald-950/60 border-emerald-800/60 text-emerald-400'
                    }`}
                  >
                    {isTelegram ? <Send className="w-4 h-4" /> : <Bell className="w-4 h-4" />}
                  </div>

                  <div className="space-y-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-semibold text-slate-200 group-hover:text-emerald-300 transition-colors">
                        {notif.title}
                      </span>
                      <Badge
                        variant={isCritical ? 'error' : 'info'}
                        size="xs"
                        className="font-mono"
                      >
                        {notif.priority || 'NORMAL'}
                      </Badge>
                      <Badge variant="slate" size="xs" className="font-mono">
                        {notif.channel}
                      </Badge>
                    </div>

                    <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
                      {notif.message}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0 self-center text-slate-500 font-mono text-[11px]">
                  <span>{new Date(notif.created_at).toLocaleDateString()}</span>
                  <ChevronRight className="w-4 h-4 text-slate-600 group-hover:text-emerald-400 transition-colors" />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
