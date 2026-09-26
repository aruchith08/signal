import { request } from './client';
import { User, RelevanceScoreResult } from '../../types/user';

export async function getActiveUser(): Promise<User> {
  return await request<User>('/users/active');
}

export async function getUser(userId: string): Promise<User> {
  return await request<User>(`/users/${userId}`);
}

export async function listUsers(): Promise<User[]> {
  return await request<User[]>('/users');
}

export async function updateUserProfile(userId: string, data: any): Promise<any> {
  return await request<any>(`/users/${userId}/profile`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function updateUserPreferences(userId: string, data: any): Promise<any> {
  return await request<any>(`/users/${userId}/preferences`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function evaluateRelevance(userId: string, opportunityId: string): Promise<RelevanceScoreResult> {
  return await request<RelevanceScoreResult>(`/relevance/evaluate`, {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, opportunity_id: opportunityId }),
  });
}
