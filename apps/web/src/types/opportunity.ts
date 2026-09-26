export type OpportunityCategory = 
  | 'HACKATHON'
  | 'CONTEST'
  | 'INTERNSHIP'
  | 'STUDENT_PROGRAM'
  | 'SCHOLARSHIP'
  | 'FELLOWSHIP'
  | 'GRANT'
  | 'GOVERNMENT_SCHEME'
  | 'AI_COMPETITION'
  | 'CONFERENCE'
  | 'WORKSHOP'
  | 'OTHER'
  | string;

export type OpportunityStatus = 
  | 'DISCOVERED'
  | 'VERIFIED'
  | 'ACTIVE'
  | 'EXPIRED'
  | 'ARCHIVED'
  | 'REJECTED'
  | string;

export type VerificationStatus = 
  | 'UNVERIFIED'
  | 'OFFICIAL'
  | 'COMMUNITY_VERIFIED'
  | 'CROSS_SOURCE_VERIFIED'
  | 'SUSPICIOUS'
  | 'CONFLICTING'
  | 'REJECTED'
  | string;

export type OpportunityPriority = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';

export interface OpportunityEvent {
  id: string;
  opportunity_id?: string;
  event_name: string;
  event_type: string;
  status: string;
  start_date: string | null;
  end_date: string | null;
  deadline_date: string | null;
  is_current: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface OpportunitySourceRecord {
  id: string;
  opportunity_id: string;
  source_id?: string;
  source_name?: string;
  source_url?: string;
  source_type?: string;
  is_official?: boolean;
  reliability_score?: number;
  extracted_at?: string;
}

export interface FactConsensus {
  id: string;
  opportunity_id: string;
  field_name: string;
  consensus_value: string;
  agreement_ratio: number;
  agreeing_sources_count: number;
  total_reporting_sources: number;
  status: 'AGREED' | 'DISPUTED' | 'UNKNOWN' | string;
  created_at?: string;
}

export interface SourceConflict {
  id: string;
  opportunity_id: string;
  field_name: string;
  values_by_source: Record<string, any>;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | string;
  resolution_status: 'OPEN' | 'RESOLVED_BY_OFFICIAL' | 'RESOLVED_BY_AI' | 'DISCARDED' | string;
  resolved_value?: string | null;
  created_at?: string;
}

export interface CrossSourceVerification {
  id: string;
  opportunity_id: string;
  verification_status: VerificationStatus;
  confidence_score: number;
  agreeing_source_count: number;
  disagreeing_source_count: number;
  has_official_source: boolean;
  evidence_summary?: string | null;
  verified_at?: string;
}

export interface Opportunity {
  id: string;
  title: string;
  canonical_name: string | null;
  slug: string | null;
  season: string | null;
  year: number | null;
  current_state: string | null;
  category: OpportunityCategory;
  event_type: string | null;
  status: OpportunityStatus;
  verification_status: VerificationStatus;
  confidence_score: number;
  official: boolean;
  priority: OpportunityPriority;
  country: string | null;
  eligibility: string | null;
  target_audience: string | null;
  required_skills: string[] | null;
  tags: string[] | null;
  application_url: string | null;
  summary: string | null;
  raw_content?: string | null;
  verification_confidence: number | null;
  source_count: number;
  official_source_present: boolean;
  last_verified_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface OpportunityDetail extends Opportunity {
  events: OpportunityEvent[];
  sources: OpportunitySourceRecord[];
  verifications: CrossSourceVerification[];
  conflicts: SourceConflict[];
  consensus: FactConsensus[];
}
