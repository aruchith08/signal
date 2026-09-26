"""
Unstop (formerly Dare2Compete) Live Source Connector
Fetches public student competitions, hackathons, and opportunities from Unstop's official public API.
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

logger = logging.getLogger("signal.connectors.unstop")

UNSTOP_PUBLIC_API_URL = "https://unstop.com/api/public/opportunity/search-result"


def clean_text(raw: Optional[str]) -> str:
    """Remove HTML markup, decode entities, and normalize whitespace."""
    if not raw:
        return ""
    clean = re.sub(r"<[^>]+>", " ", str(raw))
    clean = html.unescape(clean)
    return re.sub(r"\s+", " ", clean).strip()


DEFAULT_OPPORTUNITY_TYPES: List[str] = [
    "hackathons",
    "competitions",
    "internships",
    "scholarships",
]


class UnstopConnector(BaseConnector):
    """Live connector for Unstop hackathons, competitions, internships, and opportunities."""

    def __init__(
        self,
        base_url: str = "https://unstop.com",
        api_url: str = UNSTOP_PUBLIC_API_URL,
        opportunity_types: Optional[List[str]] = None,
        max_items_per_type: int = 15,
        max_pages_per_type: int = 1,
        is_active: bool = True,
    ):
        super().__init__(
            name="Unstop",
            category=OpportunityCategory.TECH_COMPETITION,
            source_type=SourceType.API,
            trust_level=TrustLevel.HIGH,
            base_url=base_url,
            is_active=is_active,
        )
        self.api_url = api_url
        self.opportunity_types = list(opportunity_types) if opportunity_types is not None else list(DEFAULT_OPPORTUNITY_TYPES)
        self.max_items_per_type = max_items_per_type
        self.max_pages_per_type = max_pages_per_type

    def _get_request_headers(self) -> Dict[str, str]:
        """Headers required by Unstop public endpoints."""
        return {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://unstop.com",
        }

    async def health_check(self) -> bool:
        """Verify Unstop public search API responsiveness."""
        try:
            params = {
                "opportunity": "hackathons",
                "page": 1,
                "per_page": 1,
            }
            async with ResilientHTTPClient(timeout=12.0, headers=self._get_request_headers()) as client:
                res = await client.get(self.api_url, params=params)
                if res.status_code != 200:
                    return False
                payload = res.json()
                return isinstance(payload, dict) and "data" in payload
        except Exception as exc:
            logger.warning(f"[UnstopConnector] Health check failed: {exc}")
            return False

    async def fetch_raw_items(self) -> List[RawItem]:
        """Fetch opportunities across configured opportunity types from Unstop with pagination."""
        raw_items: List[RawItem] = []
        seen_ids = set()

        for opp_type in self.opportunity_types:
            for page in range(1, self.max_pages_per_type + 1):
                try:
                    params = {
                        "opportunity": opp_type,
                        "page": page,
                        "per_page": self.max_items_per_type,
                    }
                    async with ResilientHTTPClient(timeout=15.0, headers=self._get_request_headers()) as client:
                        response = await client.get(self.api_url, params=params)
                        if response.status_code != 200:
                            logger.warning(
                                f"[UnstopConnector] Failed to fetch '{opp_type}' page {page}: HTTP {response.status_code}"
                            )
                            break
                        payload = response.json()

                    items_data = payload.get("data", {}).get("data", [])
                    if not isinstance(items_data, list) or not items_data:
                        break

                    new_items_count = 0
                    for raw_entry in items_data:
                        if not isinstance(raw_entry, dict):
                            continue
                        entry_id = raw_entry.get("id")
                        if not entry_id or entry_id in seen_ids:
                            continue
                        seen_ids.add(entry_id)

                        item = self._parse_item(raw_entry, opp_type)
                        if item:
                            raw_items.append(item)
                            new_items_count += 1

                    # Break pagination early if end of results reached
                    if len(items_data) < self.max_items_per_type or new_items_count == 0:
                        break

                except httpx.TimeoutException as exc:
                    logger.warning(f"[UnstopConnector] Timeout fetching '{opp_type}' page {page}: {exc}")
                    break
                except httpx.NetworkError as exc:
                    logger.warning(f"[UnstopConnector] Network error fetching '{opp_type}' page {page}: {exc}")
                    break
                except Exception as exc:
                    logger.warning(f"[UnstopConnector] Error fetching '{opp_type}' page {page}: {exc}", exc_info=True)
                    break

        return raw_items

    def _parse_item(self, item: Dict[str, Any], opp_type: str = "general") -> Optional[RawItem]:
        """Parse an individual Unstop opportunity record into a normalized RawItem."""
        entry_id = item.get("id")
        if not entry_id:
            return None

        title = clean_text(item.get("title"))
        if not title:
            return None

        # Stable external identity
        external_id = f"unstop-{entry_id}"

        # Resolve primary URL
        raw_url = item.get("seo_url") or item.get("public_url")
        if raw_url and str(raw_url).startswith("http"):
            url = str(raw_url)
        elif raw_url:
            clean_path = str(raw_url).lstrip("/")
            url = f"https://unstop.com/{clean_path}"
        else:
            url = f"https://unstop.com/o/{entry_id}"

        canonical_url = canonicalize_url(url)

        # Organization
        org_dict = item.get("organisation") or {}
        if not isinstance(org_dict, dict):
            org_dict = {}
        org_name = clean_text(org_dict.get("name") or item.get("organisation_name")) or "Unstop"

        # Registration requirements & dates
        regn = item.get("regnRequirements") or {}
        if not isinstance(regn, dict):
            regn = {}

        start_regn_dt = regn.get("start_regn_dt") or item.get("start_date")
        end_regn_dt = regn.get("end_regn_dt") or item.get("end_date")

        deadline_str: Optional[str] = None
        deadline_date: Optional[datetime] = None
        if end_regn_dt:
            deadline_str = str(end_regn_dt)
            deadline_date = parse_iso_datetime(deadline_str)


        # Category mapping
        type_str = (item.get("type") or opp_type or "").lower()
        subtype_str = (item.get("subtype") or "").lower()
        title_lower = title.lower()

        if "hackathon" in type_str or "hackathon" in subtype_str or "hackathon" in title_lower:
            category = OpportunityCategory.HACKATHON
        elif any(k in title_lower for k in ["coding", "programming", "algorithm", "competitive programming"]):
            category = OpportunityCategory.COMPETITIVE_PROGRAMMING
        elif "intern" in type_str or "intern" in subtype_str or "job" in type_str:
            category = OpportunityCategory.INTERNSHIP
        elif "scholarship" in type_str or "scholarship" in subtype_str:
            category = OpportunityCategory.SCHOLARSHIP_FELLOWSHIP
        else:
            category = OpportunityCategory.TECH_COMPETITION

        # Description / Details
        raw_details = item.get("details")
        clean_details = clean_text(raw_details) if raw_details else ""
        if not clean_details:
            clean_details = f"Opportunity on Unstop: {title} organized by {org_name}."

        # Region & Mode
        region = item.get("region")
        mode = str(region).lower() if region else "online"

        locations = item.get("locations") or []
        location_names = []
        if isinstance(locations, list):
            for loc in locations:
                if isinstance(loc, dict) and loc.get("city"):
                    location_names.append(loc["city"])
                elif isinstance(loc, str):
                    location_names.append(loc)
        location_str = ", ".join(location_names) if location_names else ("Online" if mode == "online" else "Not specified")

        # Eligibility & Team Size
        eligibility = clean_text(regn.get("eligibility"))
        min_team = regn.get("min_team_size")
        max_team = regn.get("max_team_size")
        team_str = f"Team Size: {min_team}-{max_team}" if min_team and max_team else ""
        if eligibility and team_str:
            eligibility_str = f"{eligibility}. {team_str}"
        elif eligibility:
            eligibility_str = eligibility
        elif team_str:
            eligibility_str = team_str
        else:
            eligibility_str = "Open to students and developers"

        # Skills
        req_skills = item.get("required_skills") or []
        skills = []
        if isinstance(req_skills, list):
            for s in req_skills:
                if isinstance(s, dict):
                    skill_name = s.get("skill_name") or s.get("skill")
                    if skill_name:
                        skills.append(clean_text(str(skill_name)))
                elif isinstance(s, str):
                    skills.append(clean_text(s))

        # Tags
        tags_data = item.get("tags") or []
        tags = []
        if isinstance(tags_data, list):
            for t in tags_data:
                if isinstance(t, dict):
                    name = t.get("name") or t.get("tag")
                    if name:
                        tags.append(clean_text(str(name)))
                elif isinstance(t, str):
                    tags.append(clean_text(t))

        # Image URL
        image_url = item.get("thumb") or org_dict.get("logoUrl2") or org_dict.get("logoUrl") or item.get("banner_mobile")

        # Prizes
        prizes_data = item.get("prizes") or []
        prize_descriptions = []
        if isinstance(prizes_data, list):
            for p in prizes_data:
                if isinstance(p, dict) and p.get("cash"):
                    prize_descriptions.append(f"{p.get('rank', 'Prize')}: INR {p.get('cash')}")
                elif isinstance(p, dict) and p.get("others"):
                    prize_descriptions.append(str(p.get("others")))
        prizes_str = "; ".join(prize_descriptions) if prize_descriptions else "Not specified"

        # Published date
        published_at: Optional[datetime] = None
        for date_key in ["updated_at", "approved_date", "start_date"]:
            val = item.get(date_key)
            if val:
                published_at = parse_iso_datetime(val)
                if published_at:
                    break
        if not published_at:
            published_at = datetime.now(timezone.utc)


        # Formatted content string containing extracted signals for classification and change detection
        formatted_deadline = deadline_date.strftime("%B %d, %Y") if deadline_date else (deadline_str or "TBD")
        content = (
            f"Unstop Opportunity: {title}\n"
            f"Organization: {org_name}\n"
            f"Category: {category.value}\n"
            f"Registration Deadline: {formatted_deadline}\n"
            f"Registration Dates: {start_regn_dt or 'TBD'} to {end_regn_dt or 'TBD'}\n"
            f"Mode: {mode}\n"
            f"Location: {location_str}\n"
            f"Eligibility: {eligibility_str}\n"
            f"Required Skills: {', '.join(skills) if skills else 'General'}\n"
            f"Prizes: {prizes_str}\n"
            f"Application URL: {url}\n"
            f"Official Registration: {url}\n\n"
            f"Description:\n{clean_details}"
        )

        metadata: Dict[str, Any] = {
            "external_id": external_id,
            "unstop_id": entry_id,
            "title": title,
            "description": clean_details,
            "organization": org_name,
            "category": category.value if hasattr(category, "value") else str(category),
            "application_url": url,
            "canonical_url": canonical_url,
            "deadline": deadline_str,
            "deadline_date": deadline_date.isoformat() if deadline_date else None,
            "registration_start": str(start_regn_dt) if start_regn_dt else None,
            "registration_end": str(end_regn_dt) if end_regn_dt else None,
            "location": location_str,
            "mode": mode,
            "eligibility": eligibility_str,
            "skills": skills,
            "tags": tags,
            "image_url": str(image_url) if image_url else None,
            "source_url": url,
            "prizes": prizes_str,
            "connector_name": "unstop",
            "source_type": SourceType.API.value,
        }

        return RawItem(
            title=title,
            url=url,
            content=content,
            source_name=self.name,
            source_identifier=external_id,
            published_at=published_at,
            metadata=metadata,
        )
