"""
Devfolio Live Source Connector
Fetches public student hackathons and community competitions from Devfolio's official search API.
"""
from datetime import datetime, timezone
import html
import logging
import re
from typing import Any, Dict, List, Optional
import httpx

from connectors.base_connector import BaseConnector, RawItem
from services.ingestion.http_client import DEFAULT_USER_AGENT, ResilientHTTPClient
from shared.constants import OpportunityCategory, SourceType, TrustLevel
from shared.utils import canonicalize_url, parse_iso_datetime

logger = logging.getLogger("signal.connectors.devfolio")

DEVFOLIO_SEARCH_API_URL = "https://api.devfolio.co/api/search/hackathons"

DEFAULT_HACKATHON_TYPES: List[str] = [
    "application_open",
    "upcoming",
    "live",
]


def clean_text(raw: Optional[str]) -> str:
    """Remove HTML markup, decode entities, and normalize whitespace."""
    if not raw:
        return ""
    clean = re.sub(r"<[^>]+>", " ", str(raw))
    clean = html.unescape(clean)
    return re.sub(r"\s+", " ", clean).strip()


class DevfolioConnector(BaseConnector):
    """Live connector for Devfolio hackathons and builder competitions."""

    def __init__(
        self,
        base_url: str = "https://devfolio.co",
        api_url: str = DEVFOLIO_SEARCH_API_URL,
        hackathon_types: Optional[List[str]] = None,
        max_items_per_type: int = 15,
        max_pages_per_type: int = 1,
        is_active: bool = True,
    ):
        super().__init__(
            name="Devfolio",
            category=OpportunityCategory.HACKATHON,
            source_type=SourceType.API,
            trust_level=TrustLevel.HIGH,
            base_url=base_url,
            is_active=is_active,
        )
        self.api_url = api_url
        self.hackathon_types = list(hackathon_types) if hackathon_types is not None else list(DEFAULT_HACKATHON_TYPES)
        self.max_items_per_type = max_items_per_type
        self.max_pages_per_type = max_pages_per_type

    def _get_request_headers(self) -> Dict[str, str]:
        """Headers required by Devfolio public search API endpoints."""
        return {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://devfolio.co/hackathons",
            "Origin": "https://devfolio.co",
        }

    async def health_check(self) -> bool:
        """Verify Devfolio search API responsiveness."""
        try:
            body = {"type": "application_open", "size": 1}
            async with ResilientHTTPClient(timeout=12.0, headers=self._get_request_headers()) as client:
                res = await client.post(self.api_url, json=body)
                if res.status_code != 200:
                    return False
                payload = res.json()
                return isinstance(payload, dict) and "hits" in payload
        except Exception as exc:
            logger.warning(f"[DevfolioConnector] Health check failed: {exc}")
            return False

    async def fetch_raw_items(self) -> List[RawItem]:
        """Fetch hackathons across configured search filter types from Devfolio with pagination."""
        raw_items: List[RawItem] = []
        seen_ids = set()
        page_size = min(self.max_items_per_type, 50)

        for opp_type in self.hackathon_types:
            for page in range(1, self.max_pages_per_type + 1):
                offset = (page - 1) * page_size
                try:
                    body = {
                        "type": opp_type,
                        "size": page_size,
                    }
                    if offset > 0:
                        body["from"] = offset

                    async with ResilientHTTPClient(timeout=15.0, headers=self._get_request_headers()) as client:
                        response = await client.post(self.api_url, json=body)
                        if response.status_code != 200:
                            logger.warning(
                                f"[DevfolioConnector] Failed to fetch '{opp_type}' page {page}: HTTP {response.status_code}"
                            )
                            break
                        payload = response.json()

                    hits = payload.get("hits", {}).get("hits", [])
                    if not isinstance(hits, list) or not hits:
                        break

                    new_items_count = 0
                    for hit in hits:
                        if not isinstance(hit, dict):
                            continue
                        source_data = hit.get("_source")
                        if not isinstance(source_data, dict):
                            continue

                        entry_id = source_data.get("uuid") or source_data.get("slug")
                        if not entry_id or entry_id in seen_ids:
                            continue
                        seen_ids.add(entry_id)

                        item = self._parse_item(source_data, opp_type)
                        if item:
                            raw_items.append(item)
                            new_items_count += 1

                    # Break early if end of page results reached
                    if len(hits) < page_size or new_items_count == 0:
                        break

                except httpx.TimeoutException as exc:
                    logger.warning(f"[DevfolioConnector] Timeout fetching '{opp_type}' page {page}: {exc}")
                    break
                except httpx.NetworkError as exc:
                    logger.warning(f"[DevfolioConnector] Network error fetching '{opp_type}' page {page}: {exc}")
                    break
                except Exception as exc:
                    logger.warning(f"[DevfolioConnector] Error fetching '{opp_type}' page {page}: {exc}", exc_info=True)
                    break

        return raw_items

    def _parse_item(self, item: Dict[str, Any], opp_type: str = "hackathon") -> Optional[RawItem]:
        """Parse an individual Devfolio hackathon record into a normalized RawItem."""
        entry_uuid = item.get("uuid")
        slug = item.get("slug")
        if not entry_uuid and not slug:
            return None

        name = clean_text(item.get("name"))
        if not name:
            return None

        # Stable external identity
        external_id = f"devfolio-{entry_uuid}" if entry_uuid else f"devfolio-{slug}"

        # Resolve primary URL: Devfolio hosts hackathon microsites at {slug}.devfolio.co
        if slug:
            url = f"https://{slug}.devfolio.co"
        else:
            url = f"https://devfolio.co/hackathons/{entry_uuid}"

        canonical_url = canonicalize_url(url)

        # Organizer / Host
        hosted_by = item.get("hosted_by")
        if isinstance(hosted_by, str) and hosted_by.strip():
            org_name = clean_text(hosted_by)
        else:
            org_name = "Devfolio Community"

        # Description and Tagline
        tagline = clean_text(item.get("tagline"))
        raw_desc = item.get("desc")
        clean_desc = clean_text(raw_desc) if raw_desc else ""
        if tagline and clean_desc:
            full_description = f"{tagline}. {clean_desc}"
        elif tagline:
            full_description = tagline
        elif clean_desc:
            full_description = clean_desc
        else:
            full_description = f"Devfolio Hackathon: {name} hosted by {org_name}."

        # Dates & Deadline
        starts_at_str = item.get("starts_at")
        ends_at_str = item.get("ends_at")
        reg_start_str = item.get("registrations_start")
        reg_end_str = item.get("registrations_end")

        # Deadline resolution: registrations_end takes priority; fallback to starts_at
        effective_deadline_str: Optional[str] = reg_end_str or starts_at_str
        deadline_date: Optional[datetime] = None
        if effective_deadline_str:
            deadline_date = parse_iso_datetime(effective_deadline_str)


        # Mode & Location
        is_online = item.get("is_online", False)
        apply_mode = str(item.get("apply_mode", "")).lower()
        if is_online:
            mode = "online"
        elif apply_mode == "both":
            mode = "hybrid"
        else:
            mode = "in-person"

        loc_parts = []
        for loc_key in ["city", "state", "country"]:
            val = item.get(loc_key)
            if val and str(val).strip():
                loc_parts.append(str(val).strip())
        location_raw = item.get("location")
        if loc_parts:
            location_str = ", ".join(loc_parts)
        elif location_raw and str(location_raw).strip():
            location_str = str(location_raw).strip()
        elif is_online:
            location_str = "Online"
        else:
            location_str = "Not specified"

        # Team requirements
        team_min = item.get("team_min")
        team_max = item.get("team_size")
        if team_min and team_max:
            team_str = f"Team Size: {team_min}-{team_max}"
        elif team_max:
            team_str = f"Max Team Size: {team_max}"
        else:
            team_str = "Open to individual and team participation"

        # Themes & Tags
        themes_data = item.get("themes") or []
        tags: List[str] = []
        if isinstance(themes_data, list):
            for t in themes_data:
                if isinstance(t, dict) and t.get("name"):
                    tags.append(clean_text(str(t["name"])))
                elif isinstance(t, str):
                    tags.append(clean_text(t))

        hashtags_data = item.get("hashtags") or []
        if isinstance(hashtags_data, list):
            for h in hashtags_data:
                if isinstance(h, str) and h.strip():
                    tags.append(clean_text(h))

        # Prizes summary
        prizes_data = item.get("prizes") or []
        prize_lines = []
        if isinstance(prizes_data, list):
            for p in prizes_data:
                if isinstance(p, dict):
                    p_name = p.get("name") or "Prize"
                    p_desc = clean_text(p.get("desc"))
                    if p_desc:
                        prize_lines.append(f"{p_name}: {p_desc[:60]}")
                    else:
                        prize_lines.append(p_name)
        prizes_summary = "; ".join(prize_lines) if prize_lines else "See hackathon page for prize details"

        # Formatted content string
        formatted_deadline = deadline_date.strftime("%B %d, %Y") if deadline_date else (effective_deadline_str or "TBD")
        content = (
            f"Devfolio Hackathon: {name}\n"
            f"Organizer: {org_name}\n"
            f"Category: {OpportunityCategory.HACKATHON.value}\n"
            f"Registration Deadline: {formatted_deadline}\n"
            f"Hackathon Dates: {starts_at_str or 'TBD'} to {ends_at_str or 'TBD'}\n"
            f"Mode: {mode}\n"
            f"Location: {location_str}\n"
            f"Eligibility: {team_str}\n"
            f"Themes & Skills: {', '.join(tags) if tags else 'General'}\n"
            f"Prizes: {prizes_summary}\n"
            f"Application URL: {url}\n"
            f"Official Registration: {url}\n\n"
            f"Description:\n{full_description}"
        )

        metadata: Dict[str, Any] = {
            "external_id": external_id,
            "devfolio_uuid": entry_uuid,
            "devfolio_slug": slug,
            "title": name,
            "description": full_description,
            "organization": org_name,
            "category": OpportunityCategory.HACKATHON.value,
            "deadline": effective_deadline_str,
            "deadline_date": deadline_date.isoformat() if deadline_date else None,
            "event_start": starts_at_str,
            "event_end": ends_at_str,
            "registrations_start": reg_start_str,
            "registrations_end": reg_end_str,
            "mode": mode,
            "location": location_str,
            "skills": tags,
            "prizes": prizes_summary,
            "url": url,
            "canonical_url": canonical_url,
            "source_type": SourceType.API.value,
            "is_online": is_online,
        }

        published_at: Optional[datetime] = None
        if reg_start_str or starts_at_str:
            published_at = parse_iso_datetime(reg_start_str or starts_at_str)
        if not published_at:
            published_at = datetime.now(timezone.utc)


        return RawItem(
            source_identifier=external_id,
            source_name=self.name,
            title=name,
            url=url,
            content=content,
            published_at=published_at,
            metadata=metadata,
        )
