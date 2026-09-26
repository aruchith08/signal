"""
Resilient HTTP Client for SIGNAL Ingestion Pipeline
Provides connection pooling, respectful User-Agent, timeouts, and exponential backoff retry.
"""
import asyncio
import logging
from typing import Any, Dict, Optional
import httpx

logger = logging.getLogger("signal.http_client")

DEFAULT_TIMEOUT = 15.0
DEFAULT_USER_AGENT = "SIGNAL-Intelligence-Bot/1.0 (+https://github.com/signal-intelligence/signal; opportunity-monitor)"
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0
BACKOFF_FACTOR = 2.0


class ResilientHTTPClient:
    """Async HTTP Client wrapper with automatic retries and standard headers."""

    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        user_agent: str = DEFAULT_USER_AGENT,
        max_retries: int = MAX_RETRIES,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.timeout = timeout
        self.user_agent = user_agent
        self.max_retries = max_retries
        self._custom_headers = headers or {}
        self._client: Optional[httpx.AsyncClient] = None

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json, application/xml, text/xml, text/html, */*",
            "Accept-Language": "en-US,en;q=0.9",
        }
        headers.update(self._custom_headers)
        return headers

    async def __aenter__(self) -> "ResilientHTTPClient":
        limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
        self._client = httpx.AsyncClient(
            headers=self._get_headers(),
            timeout=httpx.Timeout(self.timeout, connect=10.0),
            limits=limits,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """Fetch a URL with exponential backoff on retryable status codes/exceptions."""
        client = self._client
        owns_client = False
        if client is None:
            owns_client = True
            client = httpx.AsyncClient(
                headers=self._get_headers(),
                timeout=httpx.Timeout(self.timeout, connect=10.0),
                follow_redirects=True,
            )

        attempt = 0
        backoff = INITIAL_BACKOFF
        last_exception = None

        try:
            while attempt < self.max_retries:
                attempt += 1
                try:
                    req_headers = self._get_headers()
                    if headers:
                        req_headers.update(headers)

                    response = await client.get(url, params=params, headers=req_headers)

                    # Retry on 5xx or 429
                    if response.status_code in [429, 500, 502, 503, 504]:
                        if attempt < self.max_retries:
                            retry_after_str = response.headers.get("Retry-After")
                            wait_time = backoff
                            if retry_after_str:
                                try:
                                    wait_time = max(float(retry_after_str), backoff)
                                except ValueError:
                                    pass
                            logger.warning(
                                f"[HTTP] Attempt {attempt}/{self.max_retries} received status {response.status_code} from {url}. Retrying in {wait_time}s..."
                            )
                            await asyncio.sleep(wait_time)
                            backoff *= BACKOFF_FACTOR
                            continue
                    response.raise_for_status()
                    return response

                except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
                    last_exception = exc
                    if attempt < self.max_retries:
                        logger.warning(
                            f"[HTTP] Attempt {attempt}/{self.max_retries} failed ({type(exc).__name__}) for {url}. Retrying in {backoff}s..."
                        )
                        await asyncio.sleep(backoff)
                        backoff *= BACKOFF_FACTOR
                    else:
                        logger.error(f"[HTTP] Max retries exceeded for {url}: {exc}")
                        raise
                except httpx.HTTPStatusError as exc:
                    logger.error(f"[HTTP] HTTP error {exc.response.status_code} for {url}: {exc}")
                    raise

            if last_exception:
                raise last_exception
            raise httpx.RequestError(f"Failed to fetch {url} after {self.max_retries} attempts")
        finally:
            if owns_client and client:
                await client.aclose()

    async def post(
        self,
        url: str,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """Post to a URL with exponential backoff on retryable status codes/exceptions."""
        client = self._client
        owns_client = False
        if client is None:
            owns_client = True
            client = httpx.AsyncClient(
                headers=self._get_headers(),
                timeout=httpx.Timeout(self.timeout, connect=10.0),
                follow_redirects=True,
            )

        attempt = 0
        backoff = INITIAL_BACKOFF
        last_exception = None

        try:
            while attempt < self.max_retries:
                attempt += 1
                try:
                    req_headers = self._get_headers()
                    if headers:
                        req_headers.update(headers)

                    response = await client.post(url, json=json, data=data, params=params, headers=req_headers)

                    # Retry on 5xx or 429
                    if response.status_code in [429, 500, 502, 503, 504]:
                        if attempt < self.max_retries:
                            retry_after_str = response.headers.get("Retry-After")
                            wait_time = backoff
                            if retry_after_str:
                                try:
                                    wait_time = max(float(retry_after_str), backoff)
                                except ValueError:
                                    pass
                            logger.warning(
                                f"[HTTP POST] Attempt {attempt}/{self.max_retries} received status {response.status_code} from {url}. Retrying in {wait_time}s..."
                            )
                            await asyncio.sleep(wait_time)
                            backoff *= BACKOFF_FACTOR
                            continue
                    response.raise_for_status()
                    return response

                except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
                    last_exception = exc
                    if attempt < self.max_retries:
                        logger.warning(
                            f"[HTTP POST] Attempt {attempt}/{self.max_retries} failed ({type(exc).__name__}) for {url}. Retrying in {backoff}s..."
                        )
                        await asyncio.sleep(backoff)
                        backoff *= BACKOFF_FACTOR
                    else:
                        logger.error(f"[HTTP POST] Max retries exceeded for {url}: {exc}")
                        raise
                except httpx.HTTPStatusError as exc:
                    logger.error(f"[HTTP POST] HTTP error {exc.response.status_code} for {url}: {exc}")
                    raise

            if last_exception:
                raise last_exception
            raise httpx.RequestError(f"Failed to post to {url} after {self.max_retries} attempts")
        finally:
            if owns_client and client:
                await client.aclose()


# Singleton default client helper
async def fetch_url(url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> httpx.Response:
    async with ResilientHTTPClient() as client:
        return await client.get(url, params=params, headers=headers)

