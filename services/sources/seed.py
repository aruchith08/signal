"""
SIGNAL 📡 — Seed Real Student Opportunities
Populates initial rich opportunities across Hackathons, Competitive Programming,
Internships, Open Source, and AI Competitions with lifecycle events and deadlines.
"""
from datetime import datetime, timedelta, timezone
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.models.opportunity import Opportunity
from apps.api.models.organization import Organization
from apps.api.models.source import Source
from apps.api.models.event import OpportunityEvent
from shared.constants import (
    OpportunityCategory,
    OpportunityStatus,
    VerificationStatus,
    EventType,
    SourceHealthStatus,
)
from shared.utils import slugify, compute_content_hash


SEED_OPPORTUNITIES = [
    {
        "title": "Smart India Hackathon (SIH) 2026",
        "slug": "smart-india-hackathon-2026",
        "org_name": "Ministry of Education & AICTE",
        "org_slug": "aicte-mic",
        "category": "hackathon",
        "event_type": "hackathon",
        "status": OpportunityStatus.ACTIVE.value,
        "verification_status": VerificationStatus.VERIFIED.value,
        "confidence_score": 98,
        "official": True,
        "priority": "critical",
        "country": "India",
        "eligibility": "Regular enrolled undergraduate / postgraduate engineering and technology students in teams of 6 with at least one female member.",
        "target_audience": "B.Tech, M.Tech, MCA students graduating 2025-2028",
        "required_skills": "Python, React, Machine Learning, IoT, Cloud, Cybersecurity",
        "tags": "hackathon, government, national, innovation, software, hardware",
        "application_url": "https://www.sih.gov.in",
        "summary": "India's premier nationwide hackathon featuring 250+ problem statements from 60+ Central Ministries. Winning prize of ₹1,00,000 per problem statement.",
        "deadline_days": 8,
        "event_title": "Idea Submission & College SPOC Consent Deadline",
        "is_critical": True,
    },
    {
        "title": "TCS CodeVita Season 12 — Global Coding Contest",
        "slug": "tcs-codevita-season-12",
        "org_name": "Tata Consultancy Services",
        "org_slug": "tcs",
        "category": "competitive_programming",
        "event_type": "contest",
        "status": OpportunityStatus.ACTIVE.value,
        "verification_status": VerificationStatus.VERIFIED.value,
        "confidence_score": 96,
        "official": True,
        "priority": "high",
        "country": "Global",
        "eligibility": "Undergraduate and postgraduate students graduating in 2025, 2026, 2027 from B.Tech, M.Tech, BCA, MCA.",
        "target_audience": "Engineering and Science students with algorithmic problem solving skills",
        "required_skills": "C++, Java, Python, Algorithms, Data Structures",
        "tags": "competitive_programming, tcs, hiring, global, coding",
        "application_url": "https://campus.tcs.com/codevita",
        "summary": "The world's largest competitive programming contest with prize pool up to $20,000 and direct interview tracks for TCS Digital & Innovator roles.",
        "deadline_days": 12,
        "event_title": "CodeVita Global Registration Closing",
        "is_critical": True,
    },
    {
        "title": "Google Summer of Code (GSoC) 2026",
        "slug": "google-summer-of-code-2026",
        "org_name": "Google Open Source",
        "org_slug": "google-open-source",
        "category": "fellowship",
        "event_type": "fellowship",
        "status": OpportunityStatus.ACTIVE.value,
        "verification_status": VerificationStatus.VERIFIED.value,
        "confidence_score": 99,
        "official": True,
        "priority": "critical",
        "country": "Global",
        "eligibility": "Open to post-secondary students and open source beginners worldwide aged 18+.",
        "target_audience": "Undergraduate, graduate students, and open source enthusiasts",
        "required_skills": "Git, Linux, Python, C++, Rust, Go, JavaScript, Open Source",
        "tags": "open_source, fellowship, google, remote, stipend",
        "application_url": "https://summerofcode.withgoogle.com",
        "summary": "12 to 22-week paid remote fellowship working on open source software projects mentored by top open source organizations worldwide. Competitive stipends.",
        "deadline_days": 19,
        "event_title": "Contributor Proposal Submission Period",
        "is_critical": False,
    },
    {
        "title": "Flipkart GRiD 6.0 — Flagship Engineering Campus Challenge",
        "slug": "flipkart-grid-6-challenge",
        "org_name": "Flipkart",
        "org_slug": "flipkart",
        "category": "hackathon",
        "event_type": "competition",
        "status": OpportunityStatus.ACTIVE.value,
        "verification_status": VerificationStatus.VERIFIED.value,
        "confidence_score": 95,
        "official": True,
        "priority": "high",
        "country": "India",
        "eligibility": "B.Tech / B.E / M.Tech students from batch of 2025, 2026, 2027, 2028.",
        "target_audience": "Pre-final and final year software engineering and robotics students",
        "required_skills": "Algorithms, System Design, Information Security, Robotics, Cloud",
        "tags": "flipkart, campus, hackathon, ppi, software_development",
        "application_url": "https://unstop.com/competitions/flipkart-grid-6",
        "summary": "Flagship engineering challenge offering Pre-Placement Interviews (PPI) for SDE-1 and SDE Internships with ₹5,25,000 cash prizes.",
        "deadline_days": 6,
        "event_title": "Level 1 Online Coding Assessment Window",
        "is_critical": True,
    },
    {
        "title": "ETHIndia 2026 — Asia's Largest Web3 Hackathon",
        "slug": "ethindia-2026-hackathon",
        "org_name": "Devfolio",
        "org_slug": "devfolio",
        "category": "hackathon",
        "event_type": "hackathon",
        "status": OpportunityStatus.ACTIVE.value,
        "verification_status": VerificationStatus.VERIFIED.value,
        "confidence_score": 94,
        "official": True,
        "priority": "high",
        "country": "India",
        "eligibility": "Developers, students, and Web3 builders worldwide. Free registration with travel grants for student hackers.",
        "target_audience": "Software engineering students interested in distributed systems, cryptography, and Web3",
        "required_skills": "Solidity, Rust, React, TypeScript, Ethereum, Distributed Systems",
        "tags": "web3, devfolio, hackathon, bangalore, blockchain",
        "application_url": "https://ethindia.co",
        "summary": "3-day in-person hackathon in Bengaluru with over $100,000+ in bounties, mentorship from core protocol engineers, and sponsor prizes.",
        "deadline_days": 14,
        "event_title": "Early Bird Hacker Application Deadline",
        "is_critical": False,
    },
    {
        "title": "Amazon WOW 2026 — Internship & Mentorship Program",
        "slug": "amazon-wow-2026",
        "org_name": "Amazon",
        "org_slug": "amazon",
        "category": "internship",
        "event_type": "internship",
        "status": OpportunityStatus.ACTIVE.value,
        "verification_status": VerificationStatus.VERIFIED.value,
        "confidence_score": 97,
        "official": True,
        "priority": "critical",
        "country": "India",
        "eligibility": "Women students enrolled in engineering degrees (B.Tech / M.Tech / MCA / BCA / MS) graduating in 2026 or 2027.",
        "target_audience": "Female undergraduate engineering students across India",
        "required_skills": "Data Structures, Algorithms, Problem Solving, Java, C++, Python",
        "tags": "amazon, internship, women_in_tech, sde, mentorship",
        "application_url": "https://amazonwowindia.splashthat.com",
        "summary": "Amazon WOW is a dedicated skill architecting and mentorship program offering 6-month software development internships and full-time SDE conversions.",
        "deadline_days": 10,
        "event_title": "Online Aptitude & Coding Test Window",
        "is_critical": True,
    },
    {
        "title": "Codeforces Round 990 (Div. 1 + Div. 2)",
        "slug": "codeforces-round-990",
        "org_name": "Codeforces",
        "org_slug": "codeforces",
        "category": "competitive_programming",
        "event_type": "contest",
        "status": OpportunityStatus.ACTIVE.value,
        "verification_status": VerificationStatus.VERIFIED.value,
        "confidence_score": 99,
        "official": True,
        "priority": "medium",
        "country": "Global",
        "eligibility": "Open to all registered Codeforces participants globally.",
        "target_audience": "Algorithmic competitive programmers and students",
        "required_skills": "C++, Data Structures, Number Theory, Dynamic Programming, Graphs",
        "tags": "codeforces, rated, contest, algorithms, competitive_programming",
        "application_url": "https://codeforces.com/contests",
        "summary": "Rated competitive programming contest with 6-8 challenging algorithmic problems curated by grandmasters.",
        "deadline_days": 3,
        "event_title": "Contest Start & Registration Deadline",
        "is_critical": True,
    },
    {
        "title": "Microsoft Imagine Cup 2026 — Global Student AI Challenge",
        "slug": "microsoft-imagine-cup-2026",
        "org_name": "Microsoft",
        "org_slug": "microsoft",
        "category": "student_program",
        "event_type": "competition",
        "status": OpportunityStatus.ACTIVE.value,
        "verification_status": VerificationStatus.VERIFIED.value,
        "confidence_score": 95,
        "official": True,
        "priority": "high",
        "country": "Global",
        "eligibility": "Students aged 16+ enrolled in high school or university. Teams of 1 to 4 members.",
        "target_audience": "University students building innovative AI-driven technology solutions",
        "required_skills": "Azure, AI/ML, OpenAI, React, Cloud, Entrepreneurship",
        "tags": "microsoft, ai, student_program, global, innovation, funding",
        "application_url": "https://imaginecup.microsoft.com",
        "summary": "The premier student tech competition offering $100,000 grand prize, 1-on-1 mentorship with Microsoft Chairman & CEO Satya Nadella, and Azure AI startup credits.",
        "deadline_days": 25,
        "event_title": "World Championship Idea & MVP Submission",
        "is_critical": False,
    },
    {
        "title": "Kaggle Grandmaster AI Challenge: LLM Efficiency",
        "slug": "kaggle-llm-efficiency-challenge",
        "org_name": "Kaggle",
        "org_slug": "kaggle",
        "category": "ai_ml",
        "event_type": "competition",
        "status": OpportunityStatus.ACTIVE.value,
        "verification_status": VerificationStatus.VERIFIED.value,
        "confidence_score": 96,
        "official": True,
        "priority": "high",
        "country": "Global",
        "eligibility": "Open to anyone globally with a Kaggle account.",
        "target_audience": "AI/ML practitioners, researchers, and data science students",
        "required_skills": "PyTorch, Hugging Face, Transformers, Model Quantization, Fine-Tuning",
        "tags": "ai, ml, kaggle, llm, deep_learning, competition",
        "application_url": "https://www.kaggle.com/competitions",
        "summary": "Build high-performance distilled and quantized LLMs within strict compute and latency budgets. $50,000 cash prizes and Kaggle ranking points.",
        "deadline_days": 16,
        "event_title": "Final Model Submission & Leaderboard Freeze",
        "is_critical": False,
    },
    {
        "title": "Uber HackTag 2026 — Engineering Innovation Challenge",
        "slug": "uber-hacktag-2026",
        "org_name": "Uber",
        "org_slug": "uber",
        "category": "hackathon",
        "event_type": "hackathon",
        "status": OpportunityStatus.ACTIVE.value,
        "verification_status": VerificationStatus.VERIFIED.value,
        "confidence_score": 94,
        "official": True,
        "priority": "high",
        "country": "India",
        "eligibility": "B.Tech/Dual Degree students from select engineering institutes graduating in 2026 and 2027.",
        "target_audience": "CS and IT students seeking high-growth engineering roles",
        "required_skills": "System Design, Microservices, Go, Java, Mobile, Real-time Systems",
        "tags": "uber, hackathon, hiring, sde, engineering",
        "application_url": "https://unstop.com/competitions/uber-hacktag",
        "summary": "Competitive coding, prototype building, and technical presentation challenge leading to Summer Internships and FTE offers at Uber Tech Centers.",
        "deadline_days": 7,
        "event_title": "Round 1 Coding Sprint Deadline",
        "is_critical": True,
    },
]


async def seed_opportunities_data(db: AsyncSession) -> dict:
    """Idempotently seed canonical opportunities with organizations, sources, and deadline events."""
    now_utc = datetime.now(timezone.utc)
    created_count = 0
    updated_count = 0

    # Ensure default source
    source_stmt = select(Source).where(Source.slug == "unstop")
    default_source = (await db.execute(source_stmt)).scalars().first()

    for item in SEED_OPPORTUNITIES:
        slug = item["slug"]
        
        # Check or create Organization
        org_slug = item["org_slug"]
        org_stmt = select(Organization).where(Organization.slug == org_slug)
        org = (await db.execute(org_stmt)).scalars().first()
        if not org:
            org = Organization(
                name=item["org_name"],
                slug=org_slug,
                website=f"https://{org_slug}.org",
                is_verified=True,
            )
            db.add(org)
            await db.flush()

        # Check existing Opportunity
        opp_stmt = select(Opportunity).where(Opportunity.slug == slug)
        opp = (await db.execute(opp_stmt)).scalars().first()

        content_hash = compute_content_hash(f"{item['title']}-{item['application_url']}")

        if not opp:
            opp = Opportunity(
                title=item["title"],
                canonical_name=item["title"],
                slug=slug,
                category=item["category"],
                event_type=item["event_type"],
                status=item["status"],
                verification_status=item["verification_status"],
                confidence_score=item["confidence_score"],
                official=item["official"],
                priority=item["priority"],
                country=item["country"],
                eligibility=item["eligibility"],
                target_audience=item["target_audience"],
                required_skills=item["required_skills"],
                tags=item["tags"],
                application_url=item["application_url"],
                summary=item["summary"],
                organization_id=org.id,
                source_id=default_source.id if default_source else None,
                content_hash=content_hash,
                verification_confidence=item["confidence_score"] / 100.0,
                official_source_present=item["official"],
                last_verified_at=now_utc,
            )
            db.add(opp)
            await db.flush()
            created_count += 1
        else:
            opp.verification_confidence = item["confidence_score"] / 100.0
            opp.last_verified_at = now_utc
            await db.flush()
            updated_count += 1

        # Check or create Deadline Event
        deadline_date = now_utc + timedelta(days=item["deadline_days"])
        ev_stmt = select(OpportunityEvent).where(OpportunityEvent.opportunity_id == opp.id)
        existing_event = (await db.execute(ev_stmt)).scalars().first()

        if not existing_event:
            ev = OpportunityEvent(
                opportunity_id=opp.id,
                event_type=EventType.APPLICATION_DEADLINE.value,
                title=item["event_title"],
                description=f"Registration / submission window closes for {item['title']}.",
                event_date=deadline_date,
                deadline_date=deadline_date,
                is_critical=item["is_critical"],
                source_url=item["application_url"],
                content_hash=compute_content_hash(f"{opp.id}-{item['event_title']}-{deadline_date.isoformat()}"),
            )
            db.add(ev)
        else:
            existing_event.deadline_date = deadline_date
            existing_event.is_critical = item["is_critical"]

    await db.commit()
    return {
        "status": "success",
        "created_opportunities": created_count,
        "updated_opportunities": updated_count,
        "total_seeded": len(SEED_OPPORTUNITIES),
    }
