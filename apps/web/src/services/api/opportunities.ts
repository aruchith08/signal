import { request, buildQueryString } from './client';
import { Opportunity, OpportunityDetail } from '../../types/opportunity';

export interface OpportunityFilterParams {
  category?: string;
  status?: string;
  verification_status?: string;
  official?: boolean;
  priority?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export interface OpportunityListResponse {
  items: Opportunity[];
  total: number;
  limit: number;
  offset: number;
}

export async function getOpportunities(params: OpportunityFilterParams = {}): Promise<OpportunityListResponse> {
  const qs = buildQueryString(params);
  // Backend returns OpportunityRead[] or paginated response
  const data = await request<Opportunity[] | OpportunityListResponse>(`/opportunities${qs}`);
  if (Array.isArray(data)) {
    return {
      items: data,
      total: data.length,
      limit: params.limit || 50,
      offset: params.offset || 0,
    };
  }
  return data;
}

export async function getOpportunityById(id: string): Promise<OpportunityDetail> {
  return await request<OpportunityDetail>(`/opportunities/${id}`);
}

export async function searchOpportunities(query: string, limit: number = 20): Promise<Opportunity[]> {
  const qs = buildQueryString({ query, limit });
  return await request<Opportunity[]>(`/opportunities/search${qs}`);
}
