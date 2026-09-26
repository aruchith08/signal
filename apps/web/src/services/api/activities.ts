import { request, buildQueryString } from './client';

export interface ActivityItem {
  id: string;
  action: string;
  entity_type: string;
  entity_id?: string;
  details?: Record<string, any>;
  created_at: string;
}

export interface NotificationItem {
  id: string;
  user_id: string;
  opportunity_id?: string;
  title: string;
  message: string;
  channel: string;
  status: string;
  priority?: string;
  sent_at?: string;
  created_at: string;
}

export interface SourceItem {
  id: string;
  name: string;
  source_type: string;
  base_url: string;
  active: boolean;
  reliability_score: number;
  last_polled_at?: string;
}

export async function getRecentActivity(limit = 20): Promise<ActivityItem[]> {
  const qs = buildQueryString({ limit });
  return await request<ActivityItem[]>(`/dashboard/activity${qs}`);
}

export async function getUserNotifications(userId: string, limit = 50): Promise<NotificationItem[]> {
  const qs = buildQueryString({ limit });
  return await request<NotificationItem[]>(`/users/${userId}/notifications${qs}`);
}

export async function getRegisteredSources(): Promise<SourceItem[]> {
  return await request<SourceItem[]>('/sources');
}
