import { Opportunity, OpportunityEvent } from './opportunity';

export interface DashboardStats {
  total_tracked: number;
  active_events: number;
  verified_sources: number;
  critical_deadlines: number;
}

export interface TopPriorityItem {
  opportunity: Opportunity;
  top_event?: OpportunityEvent | null;
  event?: OpportunityEvent | null;
  priority_score?: number;
  relevance_score?: number;
  reason?: string;
  why_it_matters?: string;
  urgency_label?: string;
}

export interface PersonalizedOpportunityItem {
  opportunity: Opportunity;
  score?: number;
  relevance_score?: number;
  is_eligible?: boolean;
  eligibility?: string;
  tier?: 'HIGH' | 'MEDIUM' | 'LOW' | string;
  matched_skills?: string[];
  matched_interests?: string[];
  match_factors?: string[];
  nearest_deadline?: string | null;
  urgency_label?: string | null;
}

export interface DeadlineApproachingItem {
  opportunity?: Opportunity;
  opportunity_id?: string;
  opportunity_title?: string;
  organization_name?: string | null;
  category?: string;
  event?: OpportunityEvent;
  deadline_date?: string;
  days_remaining?: number;
  urgency?: 'CRITICAL' | 'WARNING' | 'UPCOMING' | string;
  urgency_label?: string;
  is_critical?: boolean;
}

export interface DashboardOverview {
  stats: DashboardStats;
  top_priority: TopPriorityItem | null;
  for_you: PersonalizedOpportunityItem[];
  deadlines_approaching: DeadlineApproachingItem[];
  recent_announcements: Opportunity[];
  recent_updates: any[];
}

