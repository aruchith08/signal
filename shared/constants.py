"""
Domain Enums and System Constants for SIGNAL 📡
"""
from enum import Enum


class ContentClassification(str, Enum):
    OPPORTUNITY = "opportunity"
    EVENT_UPDATE = "event_update"
    DEADLINE_UPDATE = "deadline_update"
    RESULT = "result"
    INFORMATIONAL = "informational"
    IRRELEVANT = "irrelevant"
    UNKNOWN = "unknown"


class MatchReason(str, Enum):
    EXACT_EXTERNAL_ID = "exact_external_id"
    CANONICAL_URL = "canonical_url"
    EXACT_TITLE_ORGANIZATION = "exact_title_organization"
    ALIAS = "alias"
    DETERMINISTIC_SIMILARITY = "deterministic_similarity"
    NEW_ENTITY = "new_entity"


class OpportunityCategory(str, Enum):
    # Core Requested Categories
    COMPETITION = "competition"
    HACKATHON = "hackathon"
    INTERNSHIP = "internship"
    SCHOLARSHIP = "scholarship"
    FELLOWSHIP = "fellowship"
    JOB = "job"
    OPEN_SOURCE = "open_source"
    CERTIFICATION = "certification"
    CONFERENCE = "conference"
    WORKSHOP = "workshop"
    EXAM = "exam"
    GOVERNMENT_PROGRAM = "government_program"
    STUDENT_PROGRAM = "student_program"
    OTHER = "other"

    # Backward compatibility mappings for existing records
    COMPETITIVE_PROGRAMMING = "competitive_programming"
    MAJOR_COMPANY_PROGRAM = "major_company_program"
    AI_ML = "ai_ml"
    GOVERNMENT = "government"
    EDUCATION_RESEARCH = "education_research"
    SCHOLARSHIP_FELLOWSHIP = "scholarship_fellowship"
    OPEN_SOURCE_PROGRAM = "open_source_program"
    TECH_COMPETITION = "tech_competition"


class EventType(str, Enum):
    ANNOUNCEMENT = "announcement"
    ANNOUNCED = "announced"
    REGISTRATION_OPEN = "registration_open"
    REGISTRATION_CLOSING = "registration_closing"
    REGISTRATION_CLOSED = "registration_closed"
    APPLICATION_OPEN = "application_open"
    APPLICATION_CLOSING = "application_closing"
    APPLICATION_DEADLINE = "application_deadline"
    DEADLINE_CHANGED = "deadline_changed"
    DEADLINE_EXTENDED = "deadline_extended"
    DEADLINE_SHORTENED = "deadline_shortened"
    DEADLINE_ANNOUNCED = "deadline_announced"
    CONTEST_SCHEDULED = "contest_scheduled"
    EVENT_STARTED = "event_started"
    ROUND_STARTED = "round_started"
    ROUND_COMPLETED = "round_completed"
    PROBLEM_STATEMENTS_RELEASED = "problem_statements_released"
    SHORTLIST_RELEASED = "shortlist_released"
    RESULTS_RELEASED = "results_released"
    RESULTS_ANNOUNCED = "results_announced"
    WINNERS_ANNOUNCED = "winners_announced"
    UPDATED = "updated"
    CANCELLED = "cancelled"
    POSTPONED = "postponed"


class OpportunityStatus(str, Enum):
    DISCOVERED = "discovered"
    OPEN = "open"
    UPCOMING = "upcoming"
    ACTIVE = "active"
    CLOSING_SOON = "closing_soon"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    POSTPONED = "postponed"
    RESULTS_AVAILABLE = "results_available"
    REGISTRATION_OPEN = "registration_open"
    REGISTRATION_CLOSED = "registration_closed"
    ONGOING = "ongoing"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class VerificationStatus(str, Enum):
    DISCOVERED = "discovered"
    UNVERIFIED = "unverified"
    LIKELY_VERIFIED = "likely_verified"
    VERIFIED = "verified"
    CONFLICTING = "conflicting"
    REVIEW_REQUIRED = "review_required"
    REJECTED = "rejected"


class SourceTrustTier(float, Enum):
    GOVERNMENT_OFFICIAL = 1.00
    ORGANIZATION_OFFICIAL = 0.95
    OFFICIAL_PLATFORM = 0.90
    VERIFIED_PARTNER = 0.80
    REPUTABLE_PLATFORM = 0.70
    NEWS_SOURCE = 0.60
    COMMUNITY_SOURCE = 0.40
    UNKNOWN = 0.20


class FieldVerificationStatus(str, Enum):
    VERIFIED = "verified"
    LIKELY = "likely"
    CONFLICTING = "conflicting"
    UNVERIFIED = "unverified"


class ConflictStatus(str, Enum):
    OPEN = "open"
    RESOLVED_OFFICIAL = "resolved_official"
    RESOLVED_MANUAL = "resolved_manual"
    DISMISSED = "dismissed"


class CandidateStatus(str, Enum):
    PENDING = "pending"
    MERGED = "merged"
    REJECTED = "rejected"
    REVIEW_REQUIRED = "review_required"


class ReviewStatus(str, Enum):
    OPEN = "open"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_RESOLVED = "auto_resolved"


class ReviewPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MergeRejectionReason(str, Enum):
    ORGANIZATION_CONFLICT = "ORGANIZATION_CONFLICT"
    YEAR_CONFLICT = "YEAR_CONFLICT"
    SEASON_CONFLICT = "SEASON_CONFLICT"
    CATEGORY_CONFLICT = "CATEGORY_CONFLICT"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class SourceType(str, Enum):
    API = "api"
    REST_API = "rest_api"
    GRAPHQL = "graphql"
    RSS = "rss"
    HTML = "html"
    OFFICIAL_WEBSITE = "official_website"
    PUBLIC_FEED = "public_feed"
    JSON_FEED = "json_feed"
    SEARCH_DISCOVERY = "search_discovery"


class TrustLevel(str, Enum):
    HIGHEST = "highest"       # Official Government, Official Company
    HIGH = "high"             # Official University, Official Platforms (Devfolio, Kaggle)
    MEDIUM_HIGH = "med_high"  # Trusted Platforms (Unstop, HackerEarth)
    MEDIUM = "medium"         # Reputable News, tech portals
    LOWER = "lower"           # Social media, forum mentions
    LOW = "low"               # Unverified third-party blogs


class PriorityLevel(str, Enum):
    CRITICAL = "critical"     # Deadline < 24h, critical updates
    HIGH = "high"             # Flagship competition / registration opened
    MEDIUM = "medium"         # New relevant opportunity announced
    LOW = "low"               # General updates, minor changes


class NotificationChannel(str, Enum):
    TELEGRAM = "telegram"
    EMAIL = "email"
    WEB_PUSH = "web_push"
    DISCORD = "discord"
    MOCK = "mock"
    IN_APP = "in_app"


class NotificationStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    SKIPPED = "skipped"

# New enum for scheduler job status
class ScheduledJobStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"

# New enum for user‑visible notification read state
class UserNotificationStatus(str, Enum):
    UNREAD = "unread"
    READ = "read"
    DISMISSED = "dismissed"


class DeliveryMode(str, Enum):
    INSTANT = "instant"
    DIGEST = "digest"
    QUEUED = "queued"
    SKIPPED = "skipped"


class EligibilityStatus(str, Enum):
    ELIGIBLE = "eligible"
    LIKELY_ELIGIBLE = "likely_eligible"
    UNKNOWN = "unknown"
    LIKELY_INELIGIBLE = "likely_ineligible"
    INELIGIBLE = "ineligible"


class InterestCategory(str, Enum):
    AI_ML = "ai_ml"
    SOFTWARE_ENGINEERING = "software_engineering"
    COMPETITIVE_PROGRAMMING = "competitive_programming"
    OPEN_SOURCE = "open_source"
    HACKATHONS = "hackathons"
    INTERNSHIPS = "internships"
    SCHOLARSHIPS = "scholarships"
    RESEARCH = "research"
    GOVERNMENT_PROGRAMS = "government_programs"
    STARTUPS = "startups"


class UrgencyLevel(str, Enum):
    EXTREME = "extreme"    # < 6 hours
    CRITICAL = "critical"  # < 24 hours
    HIGH = "high"          # < 3 days
    MEDIUM = "medium"      # < 7 days
    NORMAL = "normal"      # > 7 days


class DiscoveryStatus(str, Enum):
    DISCOVERED = "discovered"
    FILTERED_OUT = "filtered_out"
    PROCESSING = "processing"
    PROCESSED = "processed"
    DUPLICATE = "duplicate"
    FAILED = "failed"


class WatchPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class WatchMatchLevel(str, Enum):
    EXACT_ALIAS = "exact_alias"
    EXACT_CANONICAL_NAME = "exact_canonical_name"
    EXACT_NAME = "exact_name"
    KEYWORD_COMBINATION = "keyword_combination"
    SOURCE_ASSOCIATION = "source_association"
    FUZZY_MATCH = "fuzzy_match"


class WatchConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SourceHealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILING = "failing"
    DISABLED = "disabled"


class PollingPolicy(str, Enum):
    HIGH_PRIORITY = "high_priority"       # e.g., Every 30 minutes
    MEDIUM_PRIORITY = "medium_priority"   # e.g., Every 2 hours
    LOW_PRIORITY = "low_priority"         # e.g., Every 6 hours
    ARCHIVAL = "archival"                 # e.g., Once per day
    ADAPTIVE = "adaptive"                 # Adaptive policy based on signals


class ChangeType(str, Enum):
    NO_CHANGE = "no_change"
    CONTENT_CHANGED = "content_changed"
    NEW_ITEM = "new_item"
    ITEM_REMOVED = "item_removed"
    DEADLINE_CHANGED = "deadline_changed"
    DEADLINE_EXTENDED = "deadline_extended"
    DEADLINE_SHORTENED = "deadline_shortened"
    DEADLINE_ANNOUNCED = "deadline_announced"
    STATUS_CHANGED = "status_changed"
    UNKNOWN_CHANGE = "unknown_change"



