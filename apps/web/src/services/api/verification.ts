import { request, buildQueryString } from './client';
import { SourceConflict } from '../../types/opportunity';

export interface VerificationQueueItem {
  id: string;
  opportunity_id: string;
  opportunity_title?: string;
  candidate_title?: string;
  match_confidence?: number;
  ambiguity_reason?: string;
  status: string;
  created_at: string;
}

export async function getVerificationQueue(status = 'PENDING'): Promise<VerificationQueueItem[]> {
  const qs = buildQueryString({ status });
  return await request<VerificationQueueItem[]>(`/verification/queue${qs}`);
}

export async function resolveReviewItem(reviewId: string, action: 'APPROVE' | 'REJECT' | 'MERGE', notes?: string): Promise<any> {
  return await request<any>(`/verification/queue/${reviewId}/resolve`, {
    method: 'POST',
    body: JSON.stringify({ action, notes }),
  });
}

export async function getOpenConflicts(): Promise<SourceConflict[]> {
  return await request<SourceConflict[]>('/verification/conflicts');
}

export async function resolveConflict(conflictId: string, resolution: { resolved_value: string; resolution_strategy: string }): Promise<any> {
  return await request<any>(`/verification/conflicts/${conflictId}/resolve`, {
    method: 'POST',
    body: JSON.stringify(resolution),
  });
}
