"""
Unit Tests for Connector Pagination (Unstop and Devfolio)
"""
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from connectors.unstop.unstop import UnstopConnector
from connectors.devfolio.devfolio import DevfolioConnector
from connectors.base_connector import RawItem


class TestConnectorPagination(unittest.IsolatedAsyncioTestCase):
    async def test_unstop_pagination_multiple_pages(self):
        connector = UnstopConnector(
            opportunity_types=["hackathons"],
            max_items_per_type=2,
            max_pages_per_type=2,
        )

        page_1_data = {
            "data": {
                "data": [
                    {"id": 101, "title": "Hackathon 1", "public_url": "https://unstop.com/o/101"},
                    {"id": 102, "title": "Hackathon 2", "public_url": "https://unstop.com/o/102"},
                ]
            }
        }
        page_2_data = {
            "data": {
                "data": [
                    {"id": 103, "title": "Hackathon 3", "public_url": "https://unstop.com/o/103"},
                ]
            }
        }

        call_count = 0

        async def mock_get(url, params=None):
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            if params and params.get("page") == 1:
                mock_resp.json.return_value = page_1_data
            else:
                mock_resp.json.return_value = page_2_data
            return mock_resp

        with patch("connectors.unstop.unstop.ResilientHTTPClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            items = await connector.fetch_raw_items()

            self.assertEqual(call_count, 2)
            self.assertEqual(len(items), 3)
            self.assertEqual(items[0].source_identifier, "unstop-101")
            self.assertEqual(items[1].source_identifier, "unstop-102")
            self.assertEqual(items[2].source_identifier, "unstop-103")

    async def test_devfolio_pagination_multiple_pages(self):
        connector = DevfolioConnector(
            hackathon_types=["application_open"],
            max_items_per_type=2,
            max_pages_per_type=2,
        )

        page_1_hits = {
            "hits": {
                "hits": [
                    {"_source": {"uuid": "uuid-1", "slug": "hack-1", "name": "Hack 1"}},
                    {"_source": {"uuid": "uuid-2", "slug": "hack-2", "name": "Hack 2"}},
                ]
            }
        }
        page_2_hits = {
            "hits": {
                "hits": [
                    {"_source": {"uuid": "uuid-3", "slug": "hack-3", "name": "Hack 3"}},
                ]
            }
        }

        call_count = 0
        offsets = []

        async def mock_post(url, json=None):
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            offset = json.get("from", 0) if json else 0
            offsets.append(offset)
            if offset == 0:
                mock_resp.json.return_value = page_1_hits
            else:
                mock_resp.json.return_value = page_2_hits
            return mock_resp


        with patch("connectors.devfolio.devfolio.ResilientHTTPClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            items = await connector.fetch_raw_items()

            self.assertEqual(call_count, 2)
            self.assertEqual(offsets, [0, 2])
            self.assertEqual(len(items), 3)
            self.assertEqual(items[0].source_identifier, "devfolio-uuid-1")
            self.assertEqual(items[1].source_identifier, "devfolio-uuid-2")
            self.assertEqual(items[2].source_identifier, "devfolio-uuid-3")
