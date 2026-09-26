# SIGNAL Application Codebase Analysis

## API Backend (FastAPI)

### __init__.py (3 lines)

### config.py (68 lines)
- **Classes**: Settings

### database.py (53 lines)
- **Functions/Endpoints**: def, def

### main.py (141 lines)
- **Functions/Endpoints**: def, def

### models\__init__.py (70 lines)

### models\alias.py (28 lines)
- **Classes**: OpportunityAlias
- **Functions/Endpoints**: 

### models\base.py (38 lines)
- **Classes**: TimestampMixin, UUIDPrimaryKeyMixin
- **Functions/Endpoints**: utc_now

### models\change_set.py (52 lines)
- **Classes**: ChangeSet
- **Functions/Endpoints**: 

### models\discovery.py (63 lines)
- **Classes**: RawDiscovery
- **Functions/Endpoints**: 

### models\event.py (50 lines)
- **Classes**: OpportunityEvent
- **Functions/Endpoints**: 

### models\interaction.py (38 lines)
- **Classes**: UserOpportunityInteraction
- **Functions/Endpoints**: 

### models\notification.py (65 lines)
- **Classes**: Notification
- **Functions/Endpoints**: 

### models\notification_delivery.py (42 lines)
- **Classes**: NotificationDelivery
- **Functions/Endpoints**: 

### models\opportunity.py (113 lines)
- **Classes**: Opportunity
- **Functions/Endpoints**: 

### models\organization.py (39 lines)
- **Classes**: Organization
- **Functions/Endpoints**: 

### models\organization_alias.py (32 lines)
- **Classes**: OrganizationAlias
- **Functions/Endpoints**: 

### models\preference.py (42 lines)
- **Classes**: UserNotificationPreference
- **Functions/Endpoints**: 

### models\program_watch.py (160 lines)
- **Classes**: ProgramWatch, ProgramWatchAlias, ProgramWatchKeyword, ProgramWatchSource, ProgramWatchMatch
- **Functions/Endpoints**: , , , , 

### models\scheduled_job.py (43 lines)
- **Classes**: ScheduledJob
- **Functions/Endpoints**: 

### models\skill.py (52 lines)
- **Classes**: Skill, UserSkill
- **Functions/Endpoints**: , 

### models\snapshot.py (44 lines)
- **Classes**: SourceSnapshot
- **Functions/Endpoints**: 

### models\source.py (70 lines)
- **Classes**: Source
- **Functions/Endpoints**: 

### models\user.py (93 lines)
- **Classes**: User, UserProfile, UserInterest
- **Functions/Endpoints**: , , 

### models\verification.py (164 lines)
- **Classes**: OpportunitySource, VerifiedField, VerificationConflict, SemanticMatchCandidate, VerificationReview

### routers\__init__.py (30 lines)

### routers\dashboard.py (389 lines)
- **Classes**: DashboardSourcesSummary, ActivityItem
- **Functions/Endpoints**: _to_utc, _format_urgency_label, def, def, def

### routers\discoveries.py (75 lines)
- **Functions/Endpoints**: def, def

### routers\events.py (80 lines)
- **Functions/Endpoints**: def, def

### routers\health.py (40 lines)
- **Functions/Endpoints**: def

### routers\ingestion.py (120 lines)
- **Functions/Endpoints**: def, def, def

### routers\notifications.py (241 lines)
- **Classes**: TestNotificationPayload, TelegramWebhookUpdate
- **Functions/Endpoints**: def, def, def, def, def

### routers\opportunities.py (208 lines)
- **Functions/Endpoints**: def, def, def, def

### routers\organizations.py (87 lines)
- **Functions/Endpoints**: def, def, def

### routers\program_watches.py (313 lines)
- **Functions/Endpoints**: def, def, def, def, def, def

### routers\scheduler.py (254 lines)
- **Functions/Endpoints**: def, def, def, def

### routers\sources.py (170 lines)
- **Functions/Endpoints**: def, def, def, def, def

### routers\users.py (623 lines)
- **Functions/Endpoints**: def, def, def, def, def, def, def, def, def, def, def, def, def, def, def, def, def, def, def, def, def, def, def, def, def, def

### routers\verification.py (152 lines)
- **Functions/Endpoints**: def, def, def, def, def, def

### schemas\__init__.py (179 lines)

### schemas\common.py (22 lines)
- **Classes**: BaseResponse, PaginatedResponse

### schemas\dashboard.py (44 lines)
- **Classes**: TopPriorityItem, PersonalizedOpportunityItem, DeadlineApproachingItem, DashboardOverviewResponse

### schemas\discovery.py (35 lines)
- **Classes**: RawDiscoveryRead

### schemas\event.py (43 lines)
- **Classes**: EventBase, EventCreate, EventUpdate, EventRead

### schemas\interaction.py (34 lines)
- **Classes**: UserOpportunityInteractionBase, UserOpportunityInteractionRead, UserInteractionsOverviewResponse, UserInteractionStatusResponse

### schemas\notification.py (77 lines)
- **Classes**: NotificationBase, NotificationCreate, NotificationRead, NotificationDeliveryRead, ProviderStatusRead, ProviderStatusListResponse, DeliveryListResponse, DeliveryRetryResponse

### schemas\opportunity.py (82 lines)
- **Classes**: OpportunityBase, OpportunityCreate, OpportunityUpdate, OpportunityAliasRead, OpportunityRead, OpportunityDetailRead

### schemas\organization.py (35 lines)
- **Classes**: OrganizationBase, OrganizationCreate, OrganizationUpdate, OrganizationRead

### schemas\organization_alias.py (23 lines)
- **Classes**: OrganizationAliasBase, OrganizationAliasCreate, OrganizationAliasRead

### schemas\preference.py (46 lines)
- **Classes**: UserNotificationPreferenceBase, UserNotificationPreferenceUpdate, UserNotificationPreferenceRead

### schemas\program_watch.py (124 lines)
- **Classes**: ProgramWatchAliasBase, ProgramWatchAliasCreate, ProgramWatchAliasRead, ProgramWatchKeywordBase, ProgramWatchKeywordCreate, ProgramWatchKeywordRead, ProgramWatchSourceBase, ProgramWatchSourceCreate, ProgramWatchSourceRead, ProgramWatchBase, ProgramWatchCreate, ProgramWatchUpdate, ProgramWatchRead, ProgramWatchDetailRead, ProgramWatchMatchRead, ProgramWatchMatchDetailRead

### schemas\relevance.py (25 lines)
- **Classes**: RelevanceResultRead, NotificationDecisionRead

### schemas\scheduler.py (59 lines)
- **Classes**: ScheduledJobRead, SchedulerSourcesStatus, SchedulerStatusResponse, PollTriggerResponse, PollAllTriggerResponse

### schemas\skill.py (45 lines)
- **Classes**: SkillBase, SkillCreate, SkillRead, UserSkillBase, UserSkillCreate, UserSkillRead

### schemas\snapshot.py (30 lines)
- **Classes**: SourceSnapshotBase, SourceSnapshotCreate, SourceSnapshotRead

### schemas\source.py (74 lines)
- **Classes**: SourceBase, SourceCreate, SourceUpdate, SourceRead, SourceHealthRead

### schemas\user.py (101 lines)
- **Classes**: UserProfileBase, UserProfileCreate, UserProfileUpdate, UserProfileRead, UserInterestBase, UserInterestCreate, UserInterestUpdate, UserInterestRead, UserBase, UserCreate, UserUpdate, UserRead

### schemas\verification.py (100 lines)
- **Classes**: OpportunitySourceResponse, VerifiedFieldResponse, VerificationConflictResponse, SemanticCandidateResponse, VerificationReviewResponse, ReviewActionRequest, OpportunityVerificationOverview

## Web Frontend (React/Vite)

### index.html (16 lines)

### package.json (29 lines)

### src\App.tsx (40 lines)
- **Components/Functions**: const

### src\components\common\Badge.tsx (46 lines)

### src\components\common\Button.tsx (74 lines)

### src\components\common\Card.tsx (26 lines)

### src\components\common\EmptyState.tsx (33 lines)

### src\components\common\Input.tsx (46 lines)

### src\components\layout\Layout.tsx (18 lines)
- **Components/Functions**: const

### src\components\layout\Navbar.tsx (75 lines)
- **Components/Functions**: const, 

### src\components\layout\Sidebar.tsx (122 lines)
- **Components/Functions**: const

### src\components\opportunity\ConflictAlert.tsx (58 lines)
- **Components/Functions**: const

### src\components\opportunity\ConsensusCard.tsx (66 lines)
- **Components/Functions**: const

### src\components\opportunity\EligibilityChips.tsx (73 lines)

### src\components\opportunity\LifecycleTimeline.tsx (152 lines)
- **Components/Functions**: const, , 

### src\components\opportunity\OpportunityCard.tsx (165 lines)
- **Components/Functions**: , 

### src\components\opportunity\RelevanceScoreBadge.tsx (71 lines)
- **Components/Functions**: 

### src\components\opportunity\SaveFollowButtons.tsx (65 lines)
- **Components/Functions**: , 

### src\components\opportunity\SourceEvidenceList.tsx (115 lines)
- **Components/Functions**: const, 

### src\components\opportunity\TrustIndicator.tsx (63 lines)
- **Components/Functions**: 

### src\components\opportunity\VerificationBadge.tsx (76 lines)

### src\contexts\AuthContext.tsx (197 lines)
- **Components/Functions**: const

### src\contexts\ToastContext.tsx (88 lines)
- **Components/Functions**: const

### src\main.tsx (10 lines)

### src\pages\ActivityPage.tsx (173 lines)
- **Components/Functions**: const

### src\pages\DashboardPage.tsx (350 lines)
- **Components/Functions**: const

### src\pages\FeedPage.tsx (222 lines)
- **Components/Functions**: const, , , 

### src\pages\NotificationsPage.tsx (118 lines)
- **Components/Functions**: const

### src\pages\OpportunityDetailPage.tsx (379 lines)
- **Components/Functions**: const

### src\pages\ProfilePage.tsx (375 lines)
- **Components/Functions**: const, , , 

### src\pages\SavedPage.tsx (122 lines)
- **Components/Functions**: const

### src\pages\VerificationQueuePage.tsx (243 lines)
- **Components/Functions**: const

### src\services\api\activities.ts (47 lines)

### src\services\api\client.ts (74 lines)

### src\services\api\dashboard.ts (7 lines)

### src\services\api\interactions.ts (43 lines)

### src\services\api\opportunities.ts (44 lines)

### src\services\api\users.ts (35 lines)

### src\services\api\verification.ts (36 lines)

### src\types\dashboard.ts (40 lines)

### src\types\opportunity.ts (135 lines)

### src\types\user.ts (88 lines)

### tsconfig.json (25 lines)

### vite.config.ts (16 lines)
