"""
Personalization Engine — Main orchestrator evaluating opportunity relevance for a user
"""
import logging
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from apps.api.models.user import User, UserProfile, UserInterest
from apps.api.models.opportunity import Opportunity
from apps.api.models.event import OpportunityEvent
from apps.api.models.discovery import RawDiscovery
from apps.api.models.program_watch import ProgramWatchMatch, ProgramWatch
from services.personalization.eligibility import EligibilityEvaluator
from services.personalization.scoring import RelevanceScorer
from services.personalization.explanations import ExplanationGenerator, RelevanceResult
from shared.constants import EligibilityStatus

logger = logging.getLogger("signal.personalization.engine")


class PersonalizationEngine:
    """
    Evaluates an Opportunity and its lifecycle context against a user's intelligence profile.
    Produces an explainable RelevanceResult.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def evaluate_relevance(
        self,
        user: User,
        opportunity: Opportunity,
        event: Optional[OpportunityEvent] = None,
    ) -> RelevanceResult:
        """
        Evaluate relevance for a given user and opportunity.
        """
        if user.id:
            from apps.api.models.skill import UserSkill
            user_stmt = (
                select(User)
                .where(User.id == user.id)
                .options(
                    selectinload(User.profile),
                    selectinload(User.interests),
                    selectinload(User.skills).selectinload(UserSkill.skill),
                    selectinload(User.preferences),
                )
            )
            loaded_user = (await self.db.execute(user_stmt)).scalars().first()
            if loaded_user:
                user = loaded_user

        # 1. Extract User Profile Data
        profile_dict = {}
        preferred_types: List[str] = []
        if user.profile:
            p = user.profile
            profile_dict = {
                "education_level": p.education_level,
                "degree": p.degree,
                "branch": p.branch,
                "current_year": p.current_year,
                "graduation_year": p.graduation_year,
                "country": p.country,
            }
            if p.preferred_opportunity_types:
                preferred_types = [t.strip() for t in p.preferred_opportunity_types.split(",") if t.strip()]

        # 2. Extract User Interests
        interests_data: List[Dict[str, Any]] = []
        for item in (user.interests or []):
            interests_data.append({
                "category": item.category,
                "tag": item.tag,
                "weight": item.weight,
            })

        # 3. Extract User Skills
        user_skills: List[str] = []
        for us in (user.skills or []):
            if us.skill and us.skill.name:
                user_skills.append(us.skill.name)

        # 4. Extract Program Watch Matches for Opportunity
        watch_matches_data: List[Dict[str, Any]] = []
        try:
            # Look up discoveries linked to this opportunity
            disc_stmt = select(RawDiscovery.id).where(RawDiscovery.opportunity_id == opportunity.id)
            disc_ids = (await self.db.execute(disc_stmt)).scalars().all()

            if disc_ids:
                wm_stmt = (
                    select(ProgramWatchMatch)
                    .where(ProgramWatchMatch.raw_discovery_id.in_(disc_ids))
                    .options(selectinload(ProgramWatchMatch.program_watch))
                )
                watch_matches = (await self.db.execute(wm_stmt)).scalars().all()
                for wm in watch_matches:
                    prog_name = wm.program_watch.name if wm.program_watch else "Watched Program"
                    watch_matches_data.append({
                        "program_name": prog_name,
                        "match_score": wm.match_score,
                        "match_level": wm.match_level,
                    })
        except Exception as e:
            logger.warning(f"[Personalization] Error fetching program watch matches for opp {opportunity.id}: {e}")

        # 5. Evaluate Academic Eligibility
        eligibility_status, eligibility_reason = EligibilityEvaluator.evaluate(
            user_profile=profile_dict,
            opportunity_eligibility=opportunity.eligibility,
            opportunity_target_audience=opportunity.target_audience,
            opportunity_title=opportunity.title,
        )

        # 6. Extract Opportunity Data
        opp_data = {
            "title": opportunity.title,
            "category": opportunity.category,
            "summary": opportunity.summary,
            "tags": opportunity.tags,
            "required_skills": opportunity.required_skills,
            "priority": opportunity.priority,
        }

        # 7. Compute Relevance Score
        (
            total_score,
            confidence,
            component_scores,
            matched_interests,
            matched_skills,
            matched_programs,
        ) = RelevanceScorer.calculate(
            opportunity_data=opp_data,
            user_interests=interests_data,
            user_skills=user_skills,
            user_preferred_types=preferred_types,
            eligibility_status=eligibility_status,
            program_watch_matches=watch_matches_data,
        )

        # 8. Generate Human-Readable Reasons
        reasons = ExplanationGenerator.generate(
            component_scores=component_scores,
            matched_interests=matched_interests,
            matched_skills=matched_skills,
            matched_programs=matched_programs,
            eligibility_status=eligibility_status,
            eligibility_reason=eligibility_reason,
            priority=opportunity.priority,
        )

        return RelevanceResult(
            score=total_score,
            confidence=confidence,
            eligibility_status=eligibility_status,
            reasons=reasons,
            matched_interests=matched_interests,
            matched_skills=matched_skills,
            matched_programs=matched_programs,
            component_scores=component_scores,
        )
