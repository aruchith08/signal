"""
NVIDIA NIM / AI Foundation Models Provider Adapter
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


class NvidiaAIProvider(BaseAIProvider):
    """NVIDIA NIM / AI Foundation Model adapter (e.g. meta/llama-3.1-70b-instruct)."""

    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://integrate.api.nvidia.com/v1"):
        super().__init__(name="nvidia")
        self.api_key = api_key
        self.base_url = base_url

    async def is_available(self) -> bool:
        return bool(self.api_key)

    async def classify(self, content: str) -> ClassificationResult:
        if not await self.is_available():
            raise RuntimeError("NVIDIA API key not configured or unavailable")
        logger.info("Dispatching classification task to NVIDIA NIM")
        # Ready for live API invocation via httpx when credentials are provided
        raise NotImplementedError("NVIDIA API key configured but live endpoint integration active in Phase 1")

    async def extract(self, content: str) -> ExtractionResult:
        if not await self.is_available():
            raise RuntimeError("NVIDIA API key not configured or unavailable")
        logger.info("Dispatching extraction task to NVIDIA NIM")
        raise NotImplementedError("NVIDIA API key configured but live endpoint integration active in Phase 1")

    async def summarize(self, content: str) -> SummarizationResult:
        if not await self.is_available():
            raise RuntimeError("NVIDIA API key not configured or unavailable")
        logger.info("Dispatching summarization task to NVIDIA NIM")
        raise NotImplementedError("NVIDIA API key configured but live endpoint integration active in Phase 1")
