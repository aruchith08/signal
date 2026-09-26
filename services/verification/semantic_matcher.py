"""
Semantic Similarity Engine — Embeddings and Cosine Similarity
Generates candidate matches from normalized invariant representations of opportunities.
"""
from abc import ABC, abstractmethod
import math
import re
from typing import Dict, List, Optional, Set
import logging

logger = logging.getLogger("signal.semantic_matcher")


class EmbeddingProvider(ABC):
    """Abstract interface for text embedding models."""

    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        """Generate a dense vector embedding for text."""
        pass


class MockEmbeddingProvider(EmbeddingProvider):
    """
    Deterministic TF-IDF/n-gram hashing embedding provider.
    Requires zero external API keys or external dependencies.
    Produces a 64-dimensional normalized vector.
    """

    def __init__(self, dimension: int = 64):
        self.dimension = dimension

    async def embed(self, text: str) -> List[float]:
        if not text:
            return [0.0] * self.dimension

        # Simple normalized token hashing
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        vec = [0.0] * self.dimension
        for token in tokens:
            # Distribute token across dimensions using hash
            h = hash(token) % self.dimension
            vec[h] += 1.0

        # L2 Normalize
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [round(x / norm, 6) for x in vec]
        return vec


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Calculate cosine similarity between two float vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    sim = dot_product / (norm_a * norm_b)
    return round(max(0.0, min(1.0, sim)), 4)


class SemanticMatcher:
    """Computes semantic similarity across normalized invariant opportunity representations."""

    def __init__(self, embedding_provider: Optional[EmbeddingProvider] = None):
        self.provider = embedding_provider or MockEmbeddingProvider()

    @staticmethod
    def build_invariant_text(
        title: str,
        organization_name: Optional[str] = None,
        category: Optional[str] = None,
        year: Optional[int] = None,
        season: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> str:
        """
        Construct stable, invariant text representation for embedding.
        Strips volatile deadlines, registration statuses, and live dates.
        """
        parts = [f"Opportunity: {title}"]
        if organization_name:
            parts.append(f"Organization: {organization_name}")
        if category:
            parts.append(f"Category: {category}")
        if year:
            parts.append(f"Year: {year}")
        if season:
            parts.append(f"Season: {season}")
        if summary:
            # Strip dates/urls from summary for stable embeddings
            clean_summary = re.sub(r"https?://\S+", "", summary)
            clean_summary = re.sub(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", "", clean_summary)
            parts.append(f"Description: {clean_summary[:300].strip()}")
        return "\n".join(parts)

    async def compute_similarity(self, text_a: str, text_b: str) -> float:
        """Compute cosine similarity between two text snippets."""
        vec_a = await self.provider.embed(text_a)
        vec_b = await self.provider.embed(text_b)
        return cosine_similarity(vec_a, vec_b)
