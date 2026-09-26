"""
Pydantic Schemas export for SIGNAL API
"""
from apps.api.schemas.common import BaseResponse, PaginatedResponse
from apps.api.schemas.organization import (
    OrganizationBase,
    OrganizationCreate,
    OrganizationRead,
    OrganizationUpdate,
)
from apps.api.schemas.source import (
    SourceBase,
    SourceCreate,
    SourceRead,
    SourceUpdate,
    SourceHealthRead,
)
from apps.api.schemas.snapshot import (
    SourceSnapshotBase,
    SourceSnapshotCreate,
    SourceSnapshotRead,
)
from apps.api.schemas.organization_alias import (
    OrganizationAliasBase,
    OrganizationAliasCreate,
    OrganizationAliasRead,
)
from apps.api.schemas.event import (
    EventBase,
    EventCreate,
    EventRead,
    EventUpdate,
)
from apps.api.schemas.opportunity import (
    OpportunityBase,
    OpportunityCreate,
    OpportunityRead,
    OpportunityDetailRead,
    OpportunityUpdate,
)
from apps.api.schemas.discovery import RawDiscoveryRead
from apps.api.schemas.program_watch import (
    ProgramWatchBase,
    ProgramWatchCreate,
    ProgramWatchUpdate,
    ProgramWatchRead,
    ProgramWatchDetailRead,
    ProgramWatchMatchRead,
    ProgramWatchMatchDetailRead,
    ProgramWatchAliasRead,
    ProgramWatchKeywordRead,
    ProgramWatchSourceRead,
)
from apps.api.schemas.user import (
    UserBase,
    UserCreate,
    UserRead,
    UserUpdate,
    UserProfileBase,
    UserProfileCreate,
    UserProfileRead,
    UserProfileUpdate,
    UserInterestBase,
    UserInterestCreate,
    UserInterestRead,
    UserInterestUpdate,
)
from apps.api.schemas.preference import (
    UserNotificationPreferenceBase,
    UserNotificationPreferenceRead,
    UserNotificationPreferenceUpdate,
)
from apps.api.schemas.skill import (
    SkillBase,
    SkillCreate,
    SkillRead,
    UserSkillBase,
    UserSkillCreate,
    UserSkillRead,
)
from apps.api.schemas.notification import (
    NotificationBase,
    NotificationCreate,
    NotificationRead,
)
from apps.api.schemas.relevance import (
    RelevanceResultRead,
    NotificationDecisionRead,
)

__all__ = [
    "BaseResponse",
    "PaginatedResponse",
    "OrganizationBase",
    "OrganizationCreate",
    "OrganizationRead",
    "OrganizationUpdate",
    "OrganizationAliasBase",
    "OrganizationAliasCreate",
    "OrganizationAliasRead",
    "SourceBase",
    "SourceCreate",
    "SourceRead",
    "SourceUpdate",
    "SourceHealthRead",
    "SourceSnapshotBase",
    "SourceSnapshotCreate",
    "SourceSnapshotRead",
    "EventBase",
    "EventCreate",
    "EventRead",
    "EventUpdate",
    "OpportunityBase",
    "OpportunityCreate",
    "OpportunityRead",
    "OpportunityDetailRead",
    "OpportunityUpdate",
    "RawDiscoveryRead",
    "ProgramWatchBase",
    "ProgramWatchCreate",
    "ProgramWatchUpdate",
    "ProgramWatchRead",
    "ProgramWatchDetailRead",
    "ProgramWatchMatchRead",
    "ProgramWatchMatchDetailRead",
    "ProgramWatchAliasRead",
    "ProgramWatchKeywordRead",
    "ProgramWatchSourceRead",
    "UserBase",
    "UserCreate",
    "UserRead",
    "UserUpdate",
    "UserProfileBase",
    "UserProfileCreate",
    "UserProfileRead",
    "UserProfileUpdate",
    "UserInterestBase",
    "UserInterestCreate",
    "UserInterestRead",
    "UserInterestUpdate",
    "UserNotificationPreferenceBase",
    "UserNotificationPreferenceRead",
    "UserNotificationPreferenceUpdate",
    "SkillBase",
    "SkillCreate",
    "SkillRead",
    "UserSkillBase",
    "UserSkillCreate",
    "UserSkillRead",
    "NotificationBase",
    "NotificationCreate",
    "NotificationRead",
    "RelevanceResultRead",
    "NotificationDecisionRead",
    "UserOpportunityInteractionRead",
    "UserInteractionsOverviewResponse",
    "UserInteractionStatusResponse",
]

from apps.api.schemas.interaction import (
    UserOpportunityInteractionRead,
    UserInteractionsOverviewResponse,
    UserInteractionStatusResponse,
)
from apps.api.schemas.scheduler import (
    ScheduledJobRead,
    SchedulerSourcesStatus,
    SchedulerStatusResponse,
    PollTriggerResponse,
    PollAllTriggerResponse,
)

__all__.extend([
    "ScheduledJobRead",
    "SchedulerSourcesStatus",
    "SchedulerStatusResponse",
    "PollTriggerResponse",
    "PollAllTriggerResponse",
])
