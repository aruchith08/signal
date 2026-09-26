"""
SIGNAL 📡 — Ingestion Service
"""
from services.ingestion.filter import FastFilter, fast_filter
from services.ingestion.pipeline import IngestionPipeline
from services.ingestion.deduplication import Deduplicator

__all__ = [
    "FastFilter",
    "fast_filter",
    "IngestionPipeline",
    "Deduplicator",
]
