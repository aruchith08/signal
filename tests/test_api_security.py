"""
Unit & Integration Tests for Priority 11: API Security Audit
Validates:
- Standard security headers (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy)
- Request payload size protection (HTTP 413 on oversized requests)
- CORS header configuration
"""
from pathlib import Path
import sys
import unittest
import pytest
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apps.api.main import app


class TestAPISecurity(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.transport = ASGITransport(app=app)

    async def test_security_headers_present(self):
        """All responses must include standard security headers."""
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            res = await client.get("/api/v1/health")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
            self.assertEqual(res.headers.get("X-Frame-Options"), "DENY")
            self.assertEqual(res.headers.get("X-XSS-Protection"), "1; mode=block")
            self.assertEqual(res.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")

    async def test_payload_size_limit_rejection(self):
        """Requests with content-length exceeding 10MB are rejected with 413."""
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            # Send a request with a Content-Length header exceeding 10MB
            res = await client.post(
                "/api/v1/health",
                headers={"Content-Length": str(15 * 1024 * 1024)},
                content=b"",
            )
            self.assertEqual(res.status_code, 413)
            data = res.json()
            self.assertIn("payload too large", data["detail"].lower())

    async def test_cors_headers_on_allowed_origin(self):
        """CORS headers are returned for allowed origins."""
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            res = await client.options(
                "/api/v1/health",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "GET",
                },
            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.headers.get("access-control-allow-origin"), "http://localhost:3000")
