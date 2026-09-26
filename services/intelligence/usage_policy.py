"""
AI Usage Policy & Telemetry Engine
Monitors AI calls, provider latency, cost control, task quotas, and enforces MAX_AI_CALLS budgets.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional

logger = logging.getLogger("signal.ai_usage_policy")


@dataclass
class AICallRecord:
    task: str
    provider: str
    latency_ms: float
    success: bool
    error: Optional[str] = None
    estimated_tokens: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AIUsagePolicy:
    """Tracks and enforces AI usage quotas and policies."""

    def __init__(self, max_verification_calls_per_run: int = 20):
        self.max_verification_calls = max_verification_calls_per_run
        self.history: List[AICallRecord] = []
        self._verification_call_count = 0

    def can_call_verification(self) -> bool:
        """Check if verification call budget is available."""
        return self._verification_call_count < self.max_verification_calls

    def record_call(
        self,
        task: str,
        provider: str,
        latency_ms: float,
        success: bool,
        error: Optional[str] = None,
        estimated_tokens: int = 0,
    ) -> None:
        """Log telemetry for an AI call."""
        if task == "verification":
            self._verification_call_count += 1

        rec = AICallRecord(
            task=task,
            provider=provider,
            latency_ms=latency_ms,
            success=success,
            error=error,
            estimated_tokens=estimated_tokens,
        )
        self.history.append(rec)
        logger.info(
            f"[AIUsagePolicy] Recorded call: task='{task}' provider='{provider}' "
            f"latency={latency_ms:.1f}ms success={success} (verification_calls={self._verification_call_count}/{self.max_verification_calls})"
        )

    def reset_run(self) -> None:
        """Reset counters for a new batch/run."""
        self._verification_call_count = 0

    @property
    def verification_calls_remaining(self) -> int:
        return max(0, self.max_verification_calls - self._verification_call_count)


# Global singleton policy tracker
ai_usage_policy = AIUsagePolicy()
