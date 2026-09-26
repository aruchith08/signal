"""
Google Gemini AI Provider Adapter
"""
import logging
from typing import Optional
from services.intelligence.base_provider import BaseAIProvider
from services.intelligence.models import (
    ClassificationResult,
    ExtractionResult,
    SummarizationResult,
)

logger = logging.getLogger(__name__)


class GeminiAIProvider(BaseAIProvider):
    """Google Gemini AI Provider Adapter (e.g. gemini-1.5-flash / gemini-1.5-pro)."""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(name="gemini")
        self.api_key = api_key

    async def is_available(self) -> bool:
        return bool(self.api_key)

    async def classify(self, content: str) -> ClassificationResult:
        if not await self.is_available():
            raise RuntimeError("Gemini API key not configured or unavailable")
        logger.info("Dispatching classification task to Gemini")
        raise NotImplementedError("Gemini live endpoint integration active in Phase 1")

    async def extract(self, content: str) -> ExtractionResult:
        if not await self.is_available():
            raise RuntimeError("Gemini API key not configured or unavailable")
        logger.info("Dispatching extraction task to Gemini")
        raise NotImplementedError("Gemini live endpoint integration active in Phase 1")

    async def summarize(self, content: str) -> SummarizationResult:
        if not await self.is_available():
            raise RuntimeError("Gemini API key not configured or unavailable")
        logger.info("Dispatching summarization task to Gemini")
        raise NotImplementedError("Gemini live endpoint integration active in Phase 1")
