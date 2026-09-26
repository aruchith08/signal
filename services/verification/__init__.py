"""
Verification & Cross-Source Intelligence Subsystem Exports
"""
from services.verification.source_trust import SourceTrustService
from services.verification.merge_guardrails import MergeGuardrails, MergeDecision
from services.verification.semantic_matcher import (
    SemanticMatcher,
    EmbeddingProvider,
    MockEmbeddingProvider,
    cosine_similarity,
)
from services.verification.conflict_detector import ConflictDetector, FieldConflict
from services.verification.cross_source_resolution import (
    CrossSourceResolver,
    CrossSourceMatchResult,
)
from services.verification.ai_verification import (
    AIVerificationService,
    AIVerificationResponse,
)
from services.verification.review_queue import ReviewQueueService
from services.verification.engine import VerificationEngine, VerificationResult

__all__ = [
    "SourceTrustService",
    "MergeGuardrails",
    "MergeDecision",
    "SemanticMatcher",
    "EmbeddingProvider",
    "MockEmbeddingProvider",
    "cosine_similarity",
    "ConflictDetector",
    "FieldConflict",
    "CrossSourceResolver",
    "CrossSourceMatchResult",
    "AIVerificationService",
    "AIVerificationResponse",
    "ReviewQueueService",
    "VerificationEngine",
    "VerificationResult",
]
