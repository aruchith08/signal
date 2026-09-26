"""
Abstract Base Class and Exceptions for AI Providers in SIGNAL
"""
from abc import ABC, abstractmethod
from typing import Optional
from services.intelligence.models import (
    ClassificationResult,
    ExtractionResult,
    SummarizationResult,
)


class AIProviderError(Exception):
    """Base exception for all AI provider-level errors."""
    def __init__(self, provider: str, message: str, original_error: Optional[Exception] = None):
        super().__init__(f"[{provider}] {message}")
        self.provider = provider
        self.original_error = original_error


class AITimeoutError(AIProviderError):
    """Raised when an AI provider call times out."""
    pass


class AIRateLimitError(AIProviderError):
    """Raised when an AI provider exceeds rate limits or quotas."""
    pass


class AIResponseValidationError(AIProviderError):
    """Raised when an AI provider returns malformed or invalid response data."""
    pass


class BaseAIProvider(ABC):
    """Abstract interface that all AI providers (NVIDIA, Gemini, OpenAI, Mock) must implement."""

    def __init__(self, name: str, default_timeout_seconds: float = 15.0):
        self.name = name
        self.default_timeout_seconds = default_timeout_seconds

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if provider credentials/endpoints are reachable and ready."""
        pass

    @abstractmethod
    async def classify(self, content: str) -> ClassificationResult:
        """Classify raw content to determine if it is an opportunity and its category."""
        pass

    @abstractmethod
    async def extract(self, content: str) -> ExtractionResult:
        """Extract normalized structured opportunity data from content."""
        pass

    @abstractmethod
    async def summarize(self, content: str) -> SummarizationResult:
        """Generate human-readable summary, key highlights, and action items."""
        pass
