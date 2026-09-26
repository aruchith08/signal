"""
AI Gateway Router — Multi-provider task routing with automatic fallback, timeouts, and telemetry
"""
import asyncio
import logging
import time
from typing import Dict, List, Optional
from apps.api.config import settings
from services.intelligence.base_provider import (
    BaseAIProvider,
    AIProviderError,
    AITimeoutError,
    AIResponseValidationError,
)
from services.intelligence.models import (
    ClassificationResult,
    ExtractionResult,
    SummarizationResult,
)
from services.intelligence.providers.mock_provider import MockAIProvider
from services.intelligence.providers.nvidia_provider import NvidiaAIProvider
from services.intelligence.providers.gemini_provider import GeminiAIProvider
from services.intelligence.providers.openai_provider import OpenAIAIProvider

logger = logging.getLogger("signal.ai_router")


class AIRouter:
    """Intelligent task-based router with cascading fallback mechanisms and timeout guards."""

    def __init__(self, task_timeout_seconds: float = 15.0):
        self.task_timeout_seconds = task_timeout_seconds
        self._providers: Dict[str, BaseAIProvider] = {}
        self._init_default_providers()

    def _init_default_providers(self) -> None:
        """Register default providers based on configuration."""
        self.register_provider(MockAIProvider(name="mock"))
        self.register_provider(NvidiaAIProvider(api_key=settings.NVIDIA_API_KEY))
        self.register_provider(GeminiAIProvider(api_key=settings.GEMINI_API_KEY))
        self.register_provider(OpenAIAIProvider(api_key=settings.OPENAI_API_KEY))

    def register_provider(self, provider: BaseAIProvider) -> None:
        """Register or override a provider implementation."""
        self._providers[provider.name.lower()] = provider
        logger.info(f"Registered AI Provider: {provider.name}")

    def get_provider(self, name: str) -> Optional[BaseAIProvider]:
        return self._providers.get(name.lower())

    def _get_fallback_chain(self, primary_override: Optional[str] = None) -> List[BaseAIProvider]:
        """Build an ordered chain of available providers for failover."""
        candidate_names = [
            primary_override or settings.AI_PRIMARY_PROVIDER,
            settings.AI_SECONDARY_PROVIDER,
            settings.AI_FALLBACK_PROVIDER,
            "mock",  # Guaranteed terminal fallback
        ]
        chain: List[BaseAIProvider] = []
        seen = set()
        for name in candidate_names:
            if name and name.lower() not in seen:
                provider = self.get_provider(name)
                if provider:
                    chain.append(provider)
                    seen.add(name.lower())
        return chain

    async def _execute_with_timeout(self, provider: BaseAIProvider, task_name: str, coro):
        """Execute a provider coroutine with strict timeout and error normalization."""
        timeout = getattr(provider, "default_timeout_seconds", self.task_timeout_seconds)
        start_time = time.perf_counter()
        try:
            result = await asyncio.wait_for(coro, timeout=timeout)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
            logger.info(
                f"[AI Gateway] Task '{task_name}' succeeded via provider '{provider.name}' in {duration_ms}ms"
            )
            return result
        except asyncio.TimeoutError as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
            logger.warning(
                f"[AI Gateway] Task '{task_name}' timed out on provider '{provider.name}' after {duration_ms}ms (limit: {timeout}s)"
            )
            raise AITimeoutError(provider.name, f"Timed out after {timeout}s", original_error=exc)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
            logger.warning(
                f"[AI Gateway] Task '{task_name}' failed on provider '{provider.name}' after {duration_ms}ms: {exc}"
            )
            raise AIProviderError(provider.name, str(exc), original_error=exc)

    async def classify(self, content: str) -> ClassificationResult:
        """Execute classification task through fallback chain with timeout guard."""
        chain = self._get_fallback_chain(settings.AI_ROUTING_CLASSIFICATION)
        errors = []
        for idx, provider in enumerate(chain, 1):
            try:
                if await provider.is_available():
                    logger.debug(f"[AI Gateway] [Attempt {idx}] Routing 'classify' to provider '{provider.name}'")
                    result = await self._execute_with_timeout(provider, "classify", provider.classify(content))
                    if not isinstance(result, ClassificationResult):
                        raise AIResponseValidationError(provider.name, "Invalid ClassificationResult schema")
                    return result
            except Exception as exc:
                errors.append(f"{provider.name}: {str(exc)}")
                logger.info(f"[AI Gateway] Activating fallback from '{provider.name}' to next available provider...")
        raise RuntimeError(f"All AI providers in fallback chain failed for 'classify': {errors}")

    async def extract(self, content: str) -> ExtractionResult:
        """Execute extraction task through fallback chain with timeout guard."""
        chain = self._get_fallback_chain(settings.AI_ROUTING_EXTRACTION)
        errors = []
        for idx, provider in enumerate(chain, 1):
            try:
                if await provider.is_available():
                    logger.debug(f"[AI Gateway] [Attempt {idx}] Routing 'extract' to provider '{provider.name}'")
                    result = await self._execute_with_timeout(provider, "extract", provider.extract(content))
                    if not isinstance(result, ExtractionResult):
                        raise AIResponseValidationError(provider.name, "Invalid ExtractionResult schema")
                    return result
            except Exception as exc:
                errors.append(f"{provider.name}: {str(exc)}")
                logger.info(f"[AI Gateway] Activating fallback from '{provider.name}' to next available provider...")
        raise RuntimeError(f"All AI providers in fallback chain failed for 'extract': {errors}")

    async def summarize(self, content: str) -> SummarizationResult:
        """Execute summarization task through fallback chain with timeout guard."""
        chain = self._get_fallback_chain(settings.AI_ROUTING_SUMMARIZATION)
        errors = []
        for idx, provider in enumerate(chain, 1):
            try:
                if await provider.is_available():
                    logger.debug(f"[AI Gateway] [Attempt {idx}] Routing 'summarize' to provider '{provider.name}'")
                    result = await self._execute_with_timeout(provider, "summarize", provider.summarize(content))
                    if not isinstance(result, SummarizationResult):
                        raise AIResponseValidationError(provider.name, "Invalid SummarizationResult schema")
                    return result
            except Exception as exc:
                errors.append(f"{provider.name}: {str(exc)}")
                logger.info(f"[AI Gateway] Activating fallback from '{provider.name}' to next available provider...")
        raise RuntimeError(f"All AI providers in fallback chain failed for 'summarize': {errors}")


# Global singleton instance
ai_router = AIRouter()
