import { request, buildQueryString } from './client';
import { DashboardOverview } from '../../types/dashboard';

export async function getDashboardOverview(userId?: string): Promise<DashboardOverview> {
  const qs = buildQueryString({ user_id: userId });
  return await request<DashboardOverview>(`/dashboard/overview${qs}`);
}
