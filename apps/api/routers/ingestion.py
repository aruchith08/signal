"""
Ingestion Control and Trigger API Router
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.schemas.opportunity import OpportunityRead
from connectors.base_connector import BaseConnector
from connectors.mock_connector import MockConnector
from connectors.competitive_programming.codeforces import CodeforcesConnector
from connectors.companies.github_blog import GitHubBlogConnector
from connectors.government.sih import SIHConnector
from connectors.unstop import UnstopConnector
from connectors.devfolio import DevfolioConnector
from connectors.open_source.gsoc import GSoCConnector
from connectors.competitive_programming.atcoder import AtCoderConnector
from connectors.ai_ml.kaggle import KaggleConnector
from connectors.ai_ml.huggingface import HuggingFaceConnector
from services.ingestion.pipeline import IngestionPipeline

router = APIRouter(prefix="/ingestion", tags=["Ingestion"])

CONNECTOR_REGISTRY: Dict[str, Any] = {
    "codeforces": CodeforcesConnector,
    "github-blog": GitHubBlogConnector,
    "smart-india-hackathon": SIHConnector,
    "sih": SIHConnector,
    "unstop": UnstopConnector,
    "devfolio": DevfolioConnector,
    "gsoc": GSoCConnector,
    "google-summer-of-code": GSoCConnector,
    "atcoder": AtCoderConnector,
    "kaggle": KaggleConnector,
    "huggingface": HuggingFaceConnector,
    "hugging-face": HuggingFaceConnector,
}


@router.get("/connectors", response_model=List[Dict[str, Any]], status_code=status.HTTP_200_OK)
async def list_available_connectors():
    """
    List all registered live and mock connectors with their configuration and health check.
    """
    results = []
    # Test instances
    instances = [
        ("codeforces", CodeforcesConnector()),
        ("github-blog", GitHubBlogConnector()),
        ("smart-india-hackathon", SIHConnector()),
        ("unstop", UnstopConnector()),
        ("devfolio", DevfolioConnector()),
        ("mock", MockConnector()),
    ]
    for slug, conn in instances:
        results.append({
            "slug": slug,
            "name": conn.name,
            "category": conn.category.value,
            "source_type": conn.source_type.value,
            "trust_level": conn.trust_level.value,
            "base_url": conn.base_url,
            "is_active": conn.is_active,
        })
    return results


@router.post("/trigger-mock", response_model=List[OpportunityRead], status_code=status.HTTP_200_OK)
async def trigger_mock_ingestion(db: AsyncSession = Depends(get_db)):
    """
    Trigger mock ingestion pipeline for development/demo.
    """
    pipeline = IngestionPipeline(db)
    connector = MockConnector()
    created = await pipeline.process_connector(connector)
    return created


@router.post("/trigger-live/{source_slug}", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def trigger_live_ingestion(source_slug: str, db: AsyncSession = Depends(get_db)):
    """
    Trigger on-demand live polling for a specific connector or 'all'.
    Supported slugs: 'codeforces', 'github-blog', 'smart-india-hackathon', 'sih', 'all'.
    """
    pipeline = IngestionPipeline(db)

    slug_lower = source_slug.lower().strip()
    connectors_to_run: List[BaseConnector] = []

    if slug_lower == "all":
        connectors_to_run = [
            CodeforcesConnector(),
            GitHubBlogConnector(),
            SIHConnector(),
        ]
    elif slug_lower in CONNECTOR_REGISTRY:
        connector_cls = CONNECTOR_REGISTRY[slug_lower]
        connectors_to_run = [connector_cls()]
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown source connector '{source_slug}'. Available: {list(CONNECTOR_REGISTRY.keys()) + ['all']}",
        )

    results = []
    total_opportunities = 0

    for conn in connectors_to_run:
        try:
            opportunities = await pipeline.process_connector(conn)
            total_opportunities += len(opportunities)
            results.append({
                "connector": conn.name,
                "status": "success",
                "opportunities_count": len(opportunities),
                "opportunities": [opp.title for opp in opportunities],
            })
        except Exception as exc:
            results.append({
                "connector": conn.name,
                "status": "error",
                "error": str(exc),
            })

    return {
        "status": "completed",
        "total_opportunities_created": total_opportunities,
        "runs": results,
    }
