import { Opportunity, OpportunityEvent } from './opportunity';

export interface DashboardStats {
  total_tracked: number;
  active_events: number;
  verified_sources: number;
  critical_deadlines: number;
}

export interface TopPriorityItem {
  opportunity: Opportunity;
  top_event: OpportunityEvent | null;
  priority_score: number;
  reason: string;
}

export interface PersonalizedOpportunityItem {
  opportunity: Opportunity;
  score: number;
  is_eligible: boolean;
  tier: 'HIGH' | 'MEDIUM' | 'LOW' | string;
  matched_skills: string[];
  matched_interests: string[];
}

export interface DeadlineApproachingItem {
  opportunity: Opportunity;
  event: OpportunityEvent;
  days_remaining: number;
  urgency: 'CRITICAL' | 'WARNING' | 'UPCOMING' | string;
}

export interface DashboardOverview {
  stats: DashboardStats;
  top_priority: TopPriorityItem | null;
  for_you: PersonalizedOpportunityItem[];
  deadlines_approaching: DeadlineApproachingItem[];
  recent_announcements: Opportunity[];
  recent_updates: any[];
}
