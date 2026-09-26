"""
Opportunity Lifecycle & Event Engine
Coordinates content understanding, entity resolution, canonical opportunity tracking,
authoritative event history, and strict event idempotency.
"""
from datetime import datetime, timezone
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from apps.api.models.alias import OpportunityAlias
from apps.api.models.organization_alias import OrganizationAlias
from apps.api.models.discovery import RawDiscovery
from apps.api.models.event import OpportunityEvent
from apps.api.models.opportunity import Opportunity
from apps.api.models.organization import Organization
from services.intelligence.classifier import ContentUnderstanding
from services.intelligence.entity_resolution import EntityResolver
from services.verification.engine import VerificationEngine
from services.verification.cross_source_resolution import CrossSourceResolver
from services.notifications.change_set_router import ChangeSetNotificationRouter
from shared.constants import (
    DiscoveryStatus,
    EventType,
    MatchReason,
    OpportunityStatus,
    VerificationStatus,
)
from shared.utils import compute_content_hash, slugify

logger = logging.getLogger("signal.lifecycle")


class LifecycleEngine:
    """Manages opportunity lifecycle state transitions, entity matching, and event provenance."""

    def __init__(self, db: AsyncSession, notification_router: Optional[Any] = None):
        self.db = db
        self.resolver = EntityResolver(db)
        self.cross_resolver = CrossSourceResolver(db)
        self.verification_engine = VerificationEngine(db)
        from services.ingestion.opportunity_change_detection import OpportunityChangeDetector
        self.change_detector = OpportunityChangeDetector()
        self.notification_router = notification_router or ChangeSetNotificationRouter()

    async def get_or_create_organization(
        self,
        org_name: Optional[str],
        source_trust: str = "high",
    ) -> Optional[Organization]:
        """Resolve or automatically register an Organization, taking aliases into account."""
        if not org_name or not org_name.strip():
            return None
        clean_name = org_name.strip()
        org_slug = slugify(clean_name)

        # 1. Direct slug or name match
        stmt = select(Organization).where((Organization.slug == org_slug) | (Organization.name == clean_name))
        org = (await self.db.execute(stmt)).scalars().first()
        if org:
            return org

        # 2. Check OrganizationAlias
        alias_stmt = select(OrganizationAlias).where(
            (OrganizationAlias.normalized_alias == org_slug)
            | (OrganizationAlias.alias.ilike(clean_name))
        )
        alias_match = (await self.db.execute(alias_stmt)).scalars().first()
        if alias_match:
            org = (
                await self.db.execute(
                    select(Organization).where(Organization.id == alias_match.organization_id)
                )
            ).scalars().first()
            if org:
                logger.info(f"[Lifecycle] Resolved organization '{clean_name}' via alias -> '{org.name}' ({org.id})")
                return org

        # 3. Create new organization
        org = Organization(
            name=clean_name,
            slug=org_slug,
            is_verified=source_trust in ["highest", "high"],
        )
        self.db.add(org)
        await self.db.flush()
        return org

    async def process_discovery_lifecycle(
        self,
        discovery: RawDiscovery,
        understanding: ContentUnderstanding,
        source_id: Optional[str] = None,
        source_category: Optional[str] = None,
        source_trust: str = "high",
    ) -> Optional[Opportunity]:
        """
        Process classified discovery through entity resolution, opportunity creation/update,
        and idempotent event history logging.
        """
        discovery.content_classification = understanding.classification.value

        # Policy: Informational or Irrelevant content never creates opportunities
        if not understanding.is_actionable_opportunity:
            discovery.status = DiscoveryStatus.FILTERED_OUT.value
            discovery.processing_reason = (
                f"Classified as {understanding.classification.value.upper()}: {understanding.reasoning}"
            )
            discovery.opportunity_id = None
            discovery.matched_by = None
            await self.db.flush()
            logger.info(
                f"[Lifecycle] Informational item bypassed opportunity creation: '{discovery.raw_title}' "
                f"({understanding.reasoning})"
            )
            return None

        # 1. Resolve Organization
        org = await self.get_or_create_organization(understanding.organization_name, source_trust=source_trust)
        org_id = org.id if org else None

        # 2. Entity Resolution
        match_result = await self.resolver.resolve(
            title=understanding.opportunity_name or discovery.raw_title,
            canonical_name=understanding.canonical_name,
            canonical_url=discovery.canonical_url,
            external_id=discovery.external_id,
            organization_id=org_id,
            season=understanding.season,
            year=understanding.year,
        )

        event_type = understanding.lifecycle_event_type or EventType.ANNOUNCED
        event_title = understanding.event_title or f"{discovery.raw_title}"
        event_description: Optional[str] = None
        detected_changesets: list = []

        # 3. Handle Matched vs New Entity
        if match_result.matched and match_result.opportunity:
            opp = match_result.opportunity
            discovery.opportunity_id = opp.id
            discovery.matched_by = match_result.reason.value

            # Phase 5A: Structured Change Detection BEFORE updating existing Opportunity values
            incoming_change_data = {
                "title": understanding.opportunity_name or discovery.raw_title,
                "current_state": event_type.value if event_type else None,
                "season": understanding.season,
                "year": understanding.year,
                "deadline_date": understanding.deadline_date,
                "application_url": discovery.canonical_url,
                "eligibility": getattr(understanding, "target_audience", None),
            }
            detected_changesets = await self.change_detector.detect_and_record(
                session=self.db,
                existing_opp=opp,
                incoming_data=incoming_change_data,
                source_snapshot_id=None,
            )

            # If an existing deadline was altered, elevate event_type and record provenance
            event_description = None
            deadline_cs = next((cs for cs in detected_changesets if cs.field_name == "deadline_date"), None)
            if deadline_cs and deadline_cs.previous_value is not None:
                event_type = EventType.DEADLINE_CHANGED
                event_title = f"Deadline Changed: {opp.title}"
                event_description = f"Deadline updated from {deadline_cs.previous_value} to {deadline_cs.new_value}"

            # Update current state on opportunity: preserve explicit non-announcement lifecycle state
            if understanding.lifecycle_event_type and understanding.lifecycle_event_type != EventType.ANNOUNCED:
                opp.current_state = understanding.lifecycle_event_type.value
            elif event_type:
                opp.current_state = event_type.value

            # Update season and year if newly discovered
            if understanding.season and not opp.season:
                opp.season = understanding.season
            if understanding.year and not opp.year:
                opp.year = understanding.year

            # Add alias if candidate title differs and not already recorded
            candidate_alias = (understanding.canonical_name or discovery.raw_title).strip()
            if candidate_alias and candidate_alias.lower() != opp.title.lower():
                alias_check_stmt = select(OpportunityAlias).where(
                    OpportunityAlias.opportunity_id == opp.id,
                    OpportunityAlias.alias.ilike(candidate_alias),
                )
                existing_alias = (await self.db.execute(alias_check_stmt)).scalars().first()
                if not existing_alias:
                    new_alias = OpportunityAlias(
                        opportunity_id=opp.id,
                        alias=candidate_alias,
                        source="entity_resolution",
                    )
                    self.db.add(new_alias)

            await self.db.flush()
            logger.info(
                f"[Lifecycle] Matched existing Opportunity '{opp.title}' (ID: {opp.id}) "
                f"via {match_result.reason.value}"
            )
        else:
            # Create new Canonical Opportunity
            final_title = understanding.opportunity_name or discovery.raw_title
            title_slug = slugify(final_title) or "opportunity"
            opp_slug = f"{title_slug}-{discovery.content_hash[:8]}"

            opp = Opportunity(
                title=final_title,
                canonical_name=understanding.canonical_name or final_title,
                slug=opp_slug,
                organization_id=org_id,
                source_id=source_id,
                category=(understanding.category.value if understanding.category else (source_category or "other")),
                event_type="competition" if "contest" in final_title.lower() or "hackathon" in final_title.lower() else "announcement",
                status=OpportunityStatus.ACTIVE.value,
                current_state=event_type.value if event_type else EventType.ANNOUNCED.value,
                verification_status=(
                    VerificationStatus.VERIFIED.value
                    if source_trust in ["highest", "high"]
                    else VerificationStatus.UNVERIFIED.value
                ),
                confidence_score=int(min(100, max(60, understanding.confidence * 100))),
                official=source_trust in ["highest", "high"],
                season=understanding.season,
                year=understanding.year,
                eligibility="Students, Developers, Innovators",
                target_audience="Engineers, developers, and technology participants",
                application_url=discovery.canonical_url,
                raw_content=discovery.raw_content,
                summary=discovery.raw_content[:350].strip() + ("..." if len(discovery.raw_content) > 350 else ""),
                content_hash=discovery.content_hash,
            )
            self.db.add(opp)
            try:
                await self.db.flush()
            except IntegrityError:
                # Concurrent worker created the opportunity with same content_hash or slug
                opp_match = (
                    await self.db.execute(
                        select(Opportunity).where(
                            (Opportunity.content_hash == discovery.content_hash)
                            | (Opportunity.slug == opp_slug)
                        )
                    )
                ).scalars().first()
                if opp_match:
                    opp = opp_match
                else:
                    raise

            discovery.opportunity_id = opp.id
            discovery.matched_by = MatchReason.NEW_ENTITY.value

            # If canonical name differs, register alias
            if understanding.canonical_name and understanding.canonical_name.lower() != final_title.lower():
                alias_obj = OpportunityAlias(
                    opportunity_id=opp.id,
                    alias=understanding.canonical_name,
                    source="canonical_extractor",
                )
                self.db.add(alias_obj)
                await self.db.flush()

            logger.info(f"[Lifecycle] Created new Canonical Opportunity: '{opp.title}' (ID: {opp.id})")

        # 3.5 Phase 3 Verification & Multi-Source Contribution Tracking
        try:
            # Register contributing source
            contrib_source = await self.verification_engine.register_source_contribution(
                opportunity_id=opp.id,
                source_url=discovery.original_url,
                canonical_url=discovery.canonical_url,
                source_id=source_id,
                raw_discovery_id=discovery.id,
                source_title=discovery.raw_title,
                contributed_fields=["title", "deadline", "application_url"],
            )

            # Fact-level verification for key fields
            if opp.title:
                await self.verification_engine.verify_field(
                    opportunity_id=opp.id,
                    field_name="title",
                    new_value=opp.title,
                    source_is_official=contrib_source.is_official_source,
                    source_trust=contrib_source.trust_score,
                )
            if discovery.canonical_url:
                await self.verification_engine.verify_field(
                    opportunity_id=opp.id,
                    field_name="application_url",
                    new_value=discovery.canonical_url,
                    source_is_official=contrib_source.is_official_source,
                    source_trust=contrib_source.trust_score,
                )
            if understanding.deadline_date:
                await self.verification_engine.verify_field(
                    opportunity_id=opp.id,
                    field_name="deadline",
                    new_value=str(understanding.deadline_date),
                    source_is_official=contrib_source.is_official_source,
                    source_trust=contrib_source.trust_score,
                )

            # Evaluate consensus, detect conflicts, and update opportunity record
            incoming_data = {
                "deadline_date": understanding.deadline_date,
                "application_url": discovery.canonical_url,
                "eligibility": understanding.target_audience or opp.eligibility,
                "year": understanding.year,
                "season": understanding.season,
            }
            incoming_source_info = {
                "source_url": discovery.canonical_url,
                "trust_score": contrib_source.trust_score,
                "is_official": contrib_source.is_official_source,
            }
            await self.verification_engine.evaluate_and_update_opportunity(
                opportunity_id=opp.id,
                incoming_data=incoming_data,
                incoming_source_info=incoming_source_info,
            )
        except Exception as v_exc:
            logger.warning(f"[Lifecycle] Verification contribution error for {opp.id}: {v_exc}", exc_info=True)

        # 4. Idempotent Lifecycle Event Creation
        # Event hash binds opportunity, event type, canonical url, and title
        event_hash = compute_content_hash(
            f"{opp.id}:{event_type.value}:{discovery.canonical_url}:{event_title}"
        )

        existing_event_stmt = select(OpportunityEvent).where(
            OpportunityEvent.opportunity_id == opp.id,
            (OpportunityEvent.content_hash == event_hash) |
            ((OpportunityEvent.event_type == event_type.value) & (OpportunityEvent.title == event_title)),
        )
        existing_event = (await self.db.execute(existing_event_stmt)).scalars().first()

        if existing_event:
            discovery.created_event_id = existing_event.id
            discovery.status = DiscoveryStatus.PROCESSED.value
            discovery.processing_reason = (
                f"Opportunity {opp.id} updated via {discovery.matched_by}; "
                f"event '{event_title}' ({event_type.value}) already exists (idempotent skip)"
            )
            await self.db.flush()
            logger.info(
                f"[Lifecycle] Event idempotency: '{event_title}' already exists for Opportunity {opp.id}"
            )
            if self.notification_router and detected_changesets:
                try:
                    await self.notification_router.route_opportunity_activity(
                        session=self.db,
                        opportunity=opp,
                        change_sets=detected_changesets,
                        event=existing_event,
                    )
                except Exception as n_err:
                    logger.warning(f"[Lifecycle] Notification routing error for {opp.id}: {n_err}", exc_info=True)
            return opp

        is_critical = event_type in [
            EventType.DEADLINE_EXTENDED,
            EventType.DEADLINE_CHANGED,
            EventType.REGISTRATION_CLOSING,
            EventType.APPLICATION_DEADLINE,
        ]

        event = OpportunityEvent(
            opportunity_id=opp.id,
            source_discovery_id=discovery.id,
            content_hash=event_hash,
            source_url=discovery.canonical_url,
            event_type=event_type.value,
            title=event_title,
            description=event_description or f"Lifecycle update from {discovery.canonical_url}",
            event_date=understanding.event_date or discovery.published_at,
            deadline_date=understanding.deadline_date,
            is_critical=is_critical,
        )
        self.db.add(event)
        try:
            await self.db.flush()
        except IntegrityError:
            # Concurrent worker created the event
            existing_event = (await self.db.execute(existing_event_stmt)).scalars().first()
            if existing_event:
                discovery.created_event_id = existing_event.id
                discovery.status = DiscoveryStatus.PROCESSED.value
                return opp
            raise

        discovery.created_event_id = event.id
        discovery.status = DiscoveryStatus.PROCESSED.value
        discovery.processing_reason = (
            f"Opportunity {opp.id} processed via {discovery.matched_by}; "
            f"created lifecycle event '{event_title}' ({event_type.value})"
        )
        await self.db.flush()

        logger.info(
            f"[Lifecycle] Created event '{event.title}' ({event.event_type}) "
            f"for Opportunity {opp.id} (Discovery: {discovery.id})"
        )

        if self.notification_router and (detected_changesets or event):
            try:
                await self.notification_router.route_opportunity_activity(
                    session=self.db,
                    opportunity=opp,
                    change_sets=detected_changesets,
                    event=event,
                )
            except Exception as n_err:
                logger.warning(f"[Lifecycle] Notification routing error for {opp.id}: {n_err}", exc_info=True)

        return opp
