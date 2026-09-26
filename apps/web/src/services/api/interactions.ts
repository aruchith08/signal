import { request, buildQueryString } from './client';
import { UserInteractionsOverview, UserInteraction } from '../../types/user';
import { Opportunity } from '../../types/opportunity';

export async function getUserInteractions(userId: string): Promise<UserInteractionsOverview> {
  return await request<UserInteractionsOverview>(`/users/${userId}/interactions`);
}

export async function saveOpportunity(userId: string, opportunityId: string, notes?: string): Promise<UserInteraction> {
  return await request<UserInteraction>(`/users/${userId}/opportunities/${opportunityId}/save`, {
    method: 'POST',
    body: JSON.stringify({ notes }),
  });
}

export async function unsaveOpportunity(userId: string, opportunityId: string): Promise<UserInteraction> {
  return await request<UserInteraction>(`/users/${userId}/opportunities/${opportunityId}/save`, {
    method: 'DELETE',
  });
}

export async function followOpportunity(userId: string, opportunityId: string, notes?: string): Promise<UserInteraction> {
  return await request<UserInteraction>(`/users/${userId}/opportunities/${opportunityId}/follow`, {
    method: 'POST',
    body: JSON.stringify({ notes }),
  });
}

export async function unfollowOpportunity(userId: string, opportunityId: string): Promise<UserInteraction> {
  return await request<UserInteraction>(`/users/${userId}/opportunities/${opportunityId}/follow`, {
    method: 'DELETE',
  });
}

export async function getSavedOpportunities(userId: string, limit = 50, offset = 0): Promise<Opportunity[]> {
  const page = Math.floor(offset / limit) + 1;
  const qs = buildQueryString({ page, page_size: limit, limit, offset });
  const data = await request<any>(`/users/${userId}/saved${qs}`);
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.items)) return data.items;
  return [];
}

export async function getFollowedOpportunities(userId: string, limit = 50, offset = 0): Promise<Opportunity[]> {
  const page = Math.floor(offset / limit) + 1;
  const qs = buildQueryString({ page, page_size: limit, limit, offset });
  const data = await request<any>(`/users/${userId}/followed${qs}`);
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.items)) return data.items;
  return [];
}
