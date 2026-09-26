"""
SIGNAL 📡 — Centralized Source Catalog & Registry
Maintains definitions, metadata, polling policies, and connector bindings for all monitored opportunity sources.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Type
from connectors.base_connector import BaseConnector
from connectors.competitive_programming.codeforces import CodeforcesConnector
from connectors.competitive_programming.codechef import CodeChefConnector
from connectors.competitive_programming.hackerrank import HackerRankConnector
from connectors.competitive_programming.leetcode import LeetCodeConnector
from connectors.competitive_programming.atcoder import AtCoderConnector
from connectors.ai_ml.kaggle import KaggleConnector
from connectors.ai_ml.huggingface import HuggingFaceConnector
from connectors.companies.github_blog import GitHubBlogConnector
from connectors.government.sih import SIHConnector
from connectors.government.mygov import MyGovConnector
from connectors.open_source.gsoc import GSoCConnector
from connectors.hackathons.mlh import MLHConnector
from connectors.unstop import UnstopConnector
from connectors.devfolio import DevfolioConnector
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.models.source import Source
from shared.constants import (
    OpportunityCategory,
    PollingPolicy,
    PriorityLevel,
    SourceHealthStatus,
    SourceType,
    TrustLevel,
)


@dataclass
class SourceDefinition:
    """Static catalog definition of a monitored opportunity source."""
    slug: str
    name: str
    organization: str
    organization_slug: str
    category: OpportunityCategory
    source_type: SourceType
    official_url: str
    connector_class: Optional[Type[BaseConnector]]
    polling_policy: PollingPolicy = PollingPolicy.MEDIUM_PRIORITY
    priority: PriorityLevel = PriorityLevel.HIGH
    trust_tier: TrustLevel = TrustLevel.HIGH
    enabled: bool = True
    description: str = ""
    supported_data: List[str] = field(default_factory=list)
    limitations: str = ""


# Default catalog of supported sources
DEFAULT_CATALOG: List[SourceDefinition] = [
    # Tier 1 — Competitive Programming
    SourceDefinition(
        slug="codeforces",
        name="Codeforces",
        organization="Codeforces",
        organization_slug="codeforces",
        category=OpportunityCategory.COMPETITIVE_PROGRAMMING,
        source_type=SourceType.API,
        official_url="https://codeforces.com",
        connector_class=CodeforcesConnector,
        polling_policy=PollingPolicy.HIGH_PRIORITY,
        priority=PriorityLevel.HIGH,
        trust_tier=TrustLevel.HIGHEST,
        enabled=True,
        description="Official competitive programming contest rounds, division challenges, and global competitions.",
        supported_data=["Upcoming contests", "Start time", "Duration", "Contest ID"],
        limitations="Rate limited to 1 request every 2 seconds by Codeforces API terms.",
    ),
    SourceDefinition(
        slug="codechef",
        name="CodeChef",
        organization="CodeChef",
        organization_slug="codechef",
        category=OpportunityCategory.COMPETITIVE_PROGRAMMING,
        source_type=SourceType.API,
        official_url="https://www.codechef.com",
        connector_class=CodeChefConnector,
        polling_policy=PollingPolicy.HIGH_PRIORITY,
        priority=PriorityLevel.HIGH,
        trust_tier=TrustLevel.HIGH,
        enabled=True,
        description="Monthly Starters, Cook-Offs, Lunchtimes, and campus engineering challenges.",
        supported_data=["Contest code", "Contest title", "Start date", "End date", "Duration"],
        limitations="Public contest API list.",
    ),
    SourceDefinition(
        slug="hackerrank",
        name="HackerRank",
        organization="HackerRank",
        organization_slug="hackerrank",
        category=OpportunityCategory.COMPETITIVE_PROGRAMMING,
        source_type=SourceType.API,
        official_url="https://www.hackerrank.com",
        connector_class=HackerRankConnector,
        polling_policy=PollingPolicy.HIGH_PRIORITY,
        priority=PriorityLevel.HIGH,
        trust_tier=TrustLevel.HIGH,
        enabled=True,
        description="HackerRank official university competitions, hackathons, and company contests.",
        supported_data=["Contest slug", "Contest name", "Epoch start time", "Epoch end time"],
        limitations="Public upcoming contest models only.",
    ),
    SourceDefinition(
        slug="leetcode",
        name="LeetCode",
        organization="LeetCode",
        organization_slug="leetcode",
        category=OpportunityCategory.COMPETITIVE_PROGRAMMING,
        source_type=SourceType.API,
        official_url="https://leetcode.com",
        connector_class=LeetCodeConnector,
        polling_policy=PollingPolicy.HIGH_PRIORITY,
        priority=PriorityLevel.HIGH,
        trust_tier=TrustLevel.HIGH,
        enabled=True,
        description="LeetCode official Weekly and Biweekly contests.",
        supported_data=["Contest title", "Title slug", "Start timestamp", "Duration seconds"],
        limitations="GraphQL public contest schema.",
    ),
    # Tier 1 — Hackathons
    SourceDefinition(
        slug="smart-india-hackathon",
        name="Smart India Hackathon",
        organization="Ministry of Education & AICTE",
        organization_slug="aicte",
        category=OpportunityCategory.HACKATHON,
        source_type=SourceType.OFFICIAL_WEBSITE,
        official_url="https://sih.gov.in",
        connector_class=SIHConnector,
        polling_policy=PollingPolicy.HIGH_PRIORITY,
        priority=PriorityLevel.CRITICAL,
        trust_tier=TrustLevel.HIGHEST,
        enabled=True,
        description="World's biggest open innovation hackathon by MoE / AICTE.",
        supported_data=["Problem statement ID", "Title", "Organization", "Category", "Description"],
        limitations="Scrapes official portal problem statements HTML table.",
    ),
    SourceDefinition(
        slug="mlh",
        name="Major League Hacking",
        organization="Major League Hacking",
        organization_slug="mlh",
        category=OpportunityCategory.HACKATHON,
        source_type=SourceType.OFFICIAL_WEBSITE,
        official_url="https://mlh.io",
        connector_class=MLHConnector,
        polling_policy=PollingPolicy.MEDIUM_PRIORITY,
        priority=PriorityLevel.HIGH,
        trust_tier=TrustLevel.HIGH,
        enabled=True,
        description="Official student hackathon league hosting global student events.",
        supported_data=["Hackathon title", "Dates", "Location", "Registration URL"],
        limitations="Parses season schedule HTML.",
    ),
    SourceDefinition(
        slug="unstop",
        name="Unstop",
        organization="Unstop",
        organization_slug="unstop",
        category=OpportunityCategory.TECH_COMPETITION,
        source_type=SourceType.API,
        official_url="https://unstop.com",
        connector_class=UnstopConnector,
        polling_policy=PollingPolicy.HIGH_PRIORITY,
        priority=PriorityLevel.HIGH,
        trust_tier=TrustLevel.HIGH,
        enabled=True,
        description="Official student competitions, hackathons, and hiring challenges from Unstop.",
        supported_data=["Hackathons", "Hiring challenges", "Competitions", "Application deadlines"],
        limitations="Public search-result API pagination.",
    ),
    # Tier 1 — Open Source Programs
    SourceDefinition(
        slug="gsoc",
        name="Google Summer of Code",
        organization="Google",
        organization_slug="google",
        category=OpportunityCategory.OPEN_SOURCE_PROGRAM,
        source_type=SourceType.JSON_FEED,
        official_url="https://opensource.googleblog.com",
        connector_class=GSoCConnector,
        polling_policy=PollingPolicy.HIGH_PRIORITY,
        priority=PriorityLevel.CRITICAL,
        trust_tier=TrustLevel.HIGHEST,
        enabled=True,
        description="Google open source programs, mentorship fellowships, and GSoC announcements.",
        supported_data=["Announcement title", "Published date", "Full text content", "Direct URL"],
        limitations="Official Google Open Source blog feed.",
    ),
    # Tier 1 — Government Initiatives
    SourceDefinition(
        slug="mygov-innovate",
        name="MyGov Innovate",
        organization="Government of India",
        organization_slug="government-of-india",
        category=OpportunityCategory.GOVERNMENT,
        source_type=SourceType.OFFICIAL_WEBSITE,
        official_url="https://innovateindia.mygov.in",
        connector_class=MyGovConnector,
        polling_policy=PollingPolicy.MEDIUM_PRIORITY,
        priority=PriorityLevel.HIGH,
        trust_tier=TrustLevel.HIGHEST,
        enabled=True,
        description="Official Indian Government Innovation challenges, national awards, and hackathons.",
        supported_data=["Challenge name", "Initiative details", "Application links"],
        limitations="HTML parsing of initiatives cards.",
    ),
    # Company Engineering Announcements
    SourceDefinition(
        slug="github-blog",
        name="GitHub Blog",
        organization="GitHub",
        organization_slug="github",
        category=OpportunityCategory.MAJOR_COMPANY_PROGRAM,
        source_type=SourceType.RSS,
        official_url="https://github.blog",
        connector_class=GitHubBlogConnector,
        polling_policy=PollingPolicy.LOW_PRIORITY,
        priority=PriorityLevel.LOW,
        trust_tier=TrustLevel.HIGH,
        enabled=True,
        description="Official GitHub engineering blog, security advisories, and student developer pack updates.",
        supported_data=["Post title", "Author", "Published date", "RSS content summary"],
        limitations="Informational content filtered out from opportunities.",
    ),
    # Future / Catalogued Sources (Documented limitations)
    SourceDefinition(
        slug="devfolio",
        name="Devfolio",
        organization="Devfolio",
        organization_slug="devfolio",
        category=OpportunityCategory.HACKATHON,
        source_type=SourceType.API,
        official_url="https://devfolio.co",
        connector_class=DevfolioConnector,
        polling_policy=PollingPolicy.HIGH_PRIORITY,
        priority=PriorityLevel.HIGH,
        trust_tier=TrustLevel.HIGH,
        enabled=True,
        description="Premier community hackathon and developer competition platform.",
        supported_data=["Hackathons", "Applications", "Deadlines", "Prizes"],
        limitations="Public search API endpoint pagination.",
    ),
    SourceDefinition(
        slug="atcoder",
        name="AtCoder",
        organization="AtCoder",
        organization_slug="atcoder",
        category=OpportunityCategory.COMPETITIVE_PROGRAMMING,
        source_type=SourceType.API,
        official_url="https://atcoder.jp",
        connector_class=AtCoderConnector,
        polling_policy=PollingPolicy.HIGH_PRIORITY,
        priority=PriorityLevel.HIGH,
        trust_tier=TrustLevel.HIGHEST,
        enabled=True,
        description="Official AtCoder global competitive programming contests (ABC, ARC, AGC).",
        supported_data=["Contest title", "Start epoch", "Duration", "Contest ID"],
        limitations="Public contest resource API.",
    ),
    SourceDefinition(
        slug="kaggle",
        name="Kaggle",
        organization="Kaggle",
        organization_slug="kaggle",
        category=OpportunityCategory.AI_ML,
        source_type=SourceType.API,
        official_url="https://www.kaggle.com",
        connector_class=KaggleConnector,
        polling_policy=PollingPolicy.HIGH_PRIORITY,
        priority=PriorityLevel.HIGH,
        trust_tier=TrustLevel.HIGH,
        enabled=True,
        description="Official Kaggle machine learning, data science, and benchmark competitions.",
        supported_data=["Competitions", "Rewards", "Categories", "Application deadlines"],
        limitations="Public competitions list endpoint.",
    ),
    SourceDefinition(
        slug="huggingface",
        name="Hugging Face",
        organization="Hugging Face",
        organization_slug="huggingface",
        category=OpportunityCategory.AI_ML,
        source_type=SourceType.API,
        official_url="https://huggingface.co",
        connector_class=HuggingFaceConnector,
        polling_policy=PollingPolicy.MEDIUM_PRIORITY,
        priority=PriorityLevel.HIGH,
        trust_tier=TrustLevel.HIGH,
        enabled=True,
        description="Open-source AI challenges, sprint hackathons, and foundation model benchmarks.",
        supported_data=["Model Challenges", "Sprint Hackathons", "Community Benchmarks"],
        limitations="Public competitions API.",
    ),
    SourceDefinition(
        slug="meity",
        name="MeitY What's New",
        organization="Ministry of Electronics and Information Technology",
        organization_slug="meity",
        category=OpportunityCategory.GOVERNMENT,
        source_type=SourceType.OFFICIAL_WEBSITE,
        official_url="https://www.meity.gov.in/whatsnew",
        connector_class=None,
        polling_policy=PollingPolicy.MEDIUM_PRIORITY,
        priority=PriorityLevel.MEDIUM,
        trust_tier=TrustLevel.HIGHEST,
        enabled=False,
        description="Official Ministry of Electronics & IT notifications and schemes.",
        supported_data=["Schemes", "Notices"],
        limitations="Next.js client-side SPA rendering required.",
    ),
]


class SourceRegistry:
    """Central manager for querying and instantiating source definitions and connectors."""

    def __init__(self, catalog: Optional[List[SourceDefinition]] = None):
        self._sources: Dict[str, SourceDefinition] = {}
        catalog = catalog or DEFAULT_CATALOG
        for item in catalog:
            self.register(item)

    def register(self, source_def: SourceDefinition) -> None:
        """Register or update a source definition in the catalog."""
        self._sources[source_def.slug] = source_def

    def get(self, slug: str) -> Optional[SourceDefinition]:
        """Retrieve source definition by slug."""
        return self._sources.get(slug)

    def list_sources(
        self,
        category: Optional[OpportunityCategory] = None,
        priority: Optional[PriorityLevel] = None,
        enabled: Optional[bool] = None,
    ) -> List[SourceDefinition]:
        """Filter sources by category, priority, or enabled status."""
        results = list(self._sources.values())
        if category is not None:
            results = [s for s in results if s.category == category]
        if priority is not None:
            results = [s for s in results if s.priority == priority]
        if enabled is not None:
            results = [s for s in results if s.enabled == enabled]
        return results

    def get_connector(self, slug: str, **kwargs) -> Optional[BaseConnector]:
        """Instantiate connector instance for a given source slug."""
        source_def = self.get(slug)
        if not source_def or not source_def.connector_class:
            return None
        return source_def.connector_class(**kwargs)


# Global singleton instance
source_registry = SourceRegistry()


async def ensure_unstop_source(db: AsyncSession) -> Source:
    """Idempotently ensure the Unstop Source row exists with production defaults."""
    stmt = select(Source).where(Source.slug == "unstop")
    result = await db.execute(stmt)
    source = result.scalars().first()
    if source is not None:
        return source

    source = Source(
        name="Unstop",
        slug="unstop",
        category=OpportunityCategory.TECH_COMPETITION.value,
        source_type=SourceType.API.value,
        base_url="https://unstop.com",
        api_endpoint="https://unstop.com/api/public/opportunity/search-result",
        monitor_frequency_minutes=60,
        priority=1,
        priority_level=PriorityLevel.HIGH.value,
        trust_level=TrustLevel.HIGH.value,
        is_active=True,
        scheduler_enabled=True,
        status=SourceHealthStatus.HEALTHY.value,
        polling_policy=PollingPolicy.HIGH_PRIORITY.value,
        notes="Unstop public student competitions, hackathons, internships, and scholarships.",
    )
    db.add(source)
    await db.flush()
    return source


async def ensure_devfolio_source(db: AsyncSession) -> Source:
    """Idempotently ensure the Devfolio Source row exists with production defaults."""
    stmt = select(Source).where(Source.slug == "devfolio")
    result = await db.execute(stmt)
    source = result.scalars().first()
    if source is not None:
        return source

    source = Source(
        name="Devfolio",
        slug="devfolio",
        category=OpportunityCategory.HACKATHON.value,
        source_type=SourceType.API.value,
        base_url="https://devfolio.co",
        api_endpoint="https://api.devfolio.co/api/search/hackathons",
        monitor_frequency_minutes=60,
        priority=1,
        priority_level=PriorityLevel.HIGH.value,
        trust_level=TrustLevel.HIGH.value,
        is_active=True,
        scheduler_enabled=True,
        status=SourceHealthStatus.HEALTHY.value,
        polling_policy=PollingPolicy.HIGH_PRIORITY.value,
        notes="Devfolio public student hackathons and community competitions.",
    )
    db.add(source)
    await db.flush()
    return source


async def ensure_source(slug: str, db: AsyncSession) -> Optional[Source]:
    """Ensure a source from the catalog exists in the database."""
    if slug == "unstop":
        return await ensure_unstop_source(db)
    if slug == "devfolio":
        return await ensure_devfolio_source(db)
    source_def = source_registry.get(slug)
    if not source_def:
        return None
    stmt = select(Source).where(Source.slug == slug)
    result = await db.execute(stmt)
    source = result.scalars().first()
    if source is not None:
        return source
    source = Source(
        name=source_def.name,
        slug=source_def.slug,
        category=source_def.category.value if hasattr(source_def.category, "value") else str(source_def.category),
        source_type=source_def.source_type.value if hasattr(source_def.source_type, "value") else str(source_def.source_type),
        base_url=source_def.official_url,
        monitor_frequency_minutes=60,
        priority=1,
        priority_level=source_def.priority.value if hasattr(source_def.priority, "value") else str(source_def.priority),
        trust_level=source_def.trust_tier.value if hasattr(source_def.trust_tier, "value") else str(source_def.trust_tier),
        is_active=source_def.enabled,
        scheduler_enabled=source_def.enabled,
        status=SourceHealthStatus.HEALTHY.value,
        polling_policy=source_def.polling_policy.value if hasattr(source_def.polling_policy, "value") else str(source_def.polling_policy),
        notes=source_def.description,
    )
    db.add(source)
    await db.flush()
    return source
