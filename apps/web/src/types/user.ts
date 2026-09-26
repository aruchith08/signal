export interface UserSkill {
  id: string;
  user_id: string;
  skill_id: string;
  proficiency_level?: string;
}

export interface UserProfile {
  id: string;
  user_id: string;
  headline?: string;
  bio?: string;
  github_username?: string;
  linkedin_url?: string;
  portfolio_url?: string;
  location?: string;
  preferred_roles?: string[];
  interests?: string[];
}

export interface UserPreferences {
  id: string;
  user_id: string;
  notify_email?: boolean;
  notify_telegram?: boolean;
  min_relevance_score?: number;
  critical_only?: boolean;
  quiet_hours_enabled?: boolean;
  quiet_hours_start?: string;
  quiet_hours_end?: string;
  subscribed_categories?: string[];
  tracked_countries?: string[];
  interest_weights?: Record<string, number>;
}

export interface User {
  id: string;
  name: string;
  email: string | null;
  telegram_chat_id: string | null;
  education_level: string | null;
  graduation_year: number | null;
  country: string | null;
  primary_domain: string | null;
  relevance_threshold: number;
  profile?: UserProfile | null;
  preferences?: UserPreferences | null;
  skills: UserSkill[];
}

export interface UserInteraction {
  id: string;
  user_id: string;
  opportunity_id: string;
  is_saved: boolean;
  is_followed: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserInteractionsOverview {
  user_id: string;
  saved_count: number;
  followed_count: number;
  saved_opportunity_ids: string[];
  followed_opportunity_ids: string[];
}

export interface RelevanceScoreResult {
  opportunity_id: string;
  overall_score: number;
  normalized_score: number;
  is_eligible: boolean;
  relevance_tier: 'HIGH' | 'MEDIUM' | 'LOW' | 'NEGLIGIBLE';
  breakdown: {
    domain_score: number;
    skill_score: number;
    interest_score: number;
    education_score: number;
    country_score: number;
    freshness_boost: number;
  };
  matched_skills: string[];
  matched_interests: string[];
  matched_domains: string[];
  eligibility_notes: string[];
}
