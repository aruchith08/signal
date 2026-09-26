"""
SIGNAL 📡 — Standardized Connector Contract Verification Helper
Reusable test suite for validating connector behavior against the BaseConnector contract.
"""
from typing import List, Type
import unittest
from connectors.base_connector import BaseConnector, RawItem
from shared.constants import OpportunityCategory, SourceType, TrustLevel


class ConnectorContractTestMixin:
    """Mixin containing standard contract test assertions for any BaseConnector subclass."""

    def assert_connector_initialization(self, connector: BaseConnector):
        """Validate standard fields on connector."""
        self.assertIsInstance(connector.name, str)
        self.assertTrue(len(connector.name) > 0)
        self.assertIsInstance(connector.category, OpportunityCategory)
        self.assertIsInstance(connector.source_type, SourceType)
        self.assertIsInstance(connector.trust_level, TrustLevel)
        self.assertIsInstance(connector.base_url, str)
        self.assertTrue(connector.base_url.startswith("http"))
        self.assertIsInstance(connector.is_active, bool)

    def assert_raw_items_contract(self, items: List[RawItem], source_name: str):
        """Validate that all items returned by connector satisfy normalization contract."""
        self.assertIsInstance(items, list)
        for item in items:
            self.assertIsInstance(item, RawItem)
            self.assertTrue(len(item.title.strip()) > 0, "Item title cannot be empty")
            self.assertTrue(item.url.startswith("http"), f"Invalid item URL: {item.url}")
            self.assertTrue(len(item.content.strip()) > 0, "Item content cannot be empty")
            self.assertEqual(item.source_name, source_name)
            self.assertTrue(len(item.source_identifier.strip()) > 0, "Missing source_identifier")
            canonical = item.canonical_url()
            self.assertTrue(canonical.startswith("http"), f"Invalid canonical URL: {canonical}")
            self.assertNotIn("utm_source", canonical, "Canonical URL should not have tracking params")
