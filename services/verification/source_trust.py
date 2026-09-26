"""
Source Trust System — Centralized, configurable domain-to-tier resolver
Assigns authoritative trust tiers, numerical trust weights, and official status.
"""
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse
from shared.constants import SourceTrustTier


class SourceTrustService:
    """Evaluates domain trust scores and official source authenticity."""

    # Centralized configurable domain trust patterns
    DEFAULT_DOMAIN_TIERS: Dict[str, SourceTrustTier] = {
        # Government Official (1.00)
        "sih.gov.in": SourceTrustTier.GOVERNMENT_OFFICIAL,
        "mygov.in": SourceTrustTier.GOVERNMENT_OFFICIAL,
        "innovateindia.mygov.in": SourceTrustTier.GOVERNMENT_OFFICIAL,
        "aicte-india.org": SourceTrustTier.GOVERNMENT_OFFICIAL,
        "meity.gov.in": SourceTrustTier.GOVERNMENT_OFFICIAL,
        "dst.gov.in": SourceTrustTier.GOVERNMENT_OFFICIAL,
        "drdo.gov.in": SourceTrustTier.GOVERNMENT_OFFICIAL,
        "isro.gov.in": SourceTrustTier.GOVERNMENT_OFFICIAL,
        "india.gov.in": SourceTrustTier.GOVERNMENT_OFFICIAL,
        "nptel.ac.in": SourceTrustTier.GOVERNMENT_OFFICIAL,

        # Organization Official (0.95)
        "tcs.com": SourceTrustTier.ORGANIZATION_OFFICIAL,
        "codevita.tcs.com": SourceTrustTier.ORGANIZATION_OFFICIAL,
        "summerofcode.withgoogle.com": SourceTrustTier.ORGANIZATION_OFFICIAL,
        "opensource.googleblog.com": SourceTrustTier.ORGANIZATION_OFFICIAL,
        "google.com": SourceTrustTier.ORGANIZATION_OFFICIAL,
        "microsoft.com": SourceTrustTier.ORGANIZATION_OFFICIAL,
        "amazon.jobs": SourceTrustTier.ORGANIZATION_OFFICIAL,
        "github.blog": SourceTrustTier.ORGANIZATION_OFFICIAL,
        "github.com": SourceTrustTier.ORGANIZATION_OFFICIAL,
        "codeforces.com": SourceTrustTier.ORGANIZATION_OFFICIAL,
        "codechef.com": SourceTrustTier.ORGANIZATION_OFFICIAL,
        "hackerrank.com": SourceTrustTier.ORGANIZATION_OFFICIAL,
        "leetcode.com": SourceTrustTier.ORGANIZATION_OFFICIAL,

        # Official Platform / Flagship Hackathon Ecosystem (0.90)
        "mlh.io": SourceTrustTier.OFFICIAL_PLATFORM,
        "hackerearth.com": SourceTrustTier.OFFICIAL_PLATFORM,
        "kaggle.com": SourceTrustTier.OFFICIAL_PLATFORM,

        # Verified Partner / Curated Student Platforms (0.80)
        "unstop.com": SourceTrustTier.VERIFIED_PARTNER,
        "devfolio.co": SourceTrustTier.VERIFIED_PARTNER,
        "dare2compete.com": SourceTrustTier.VERIFIED_PARTNER,

        # Reputable Platforms (0.70)
        "geeksforgeeks.org": SourceTrustTier.REPUTABLE_PLATFORM,
        "coursera.org": SourceTrustTier.REPUTABLE_PLATFORM,
        "edx.org": SourceTrustTier.REPUTABLE_PLATFORM,
        "internshala.com": SourceTrustTier.REPUTABLE_PLATFORM,

        # News Sources (0.60)
        "techcrunch.com": SourceTrustTier.NEWS_SOURCE,
        "thehindu.com": SourceTrustTier.NEWS_SOURCE,
        "indianexpress.com": SourceTrustTier.NEWS_SOURCE,
        "ndtv.com": SourceTrustTier.NEWS_SOURCE,
        "hindustantimes.com": SourceTrustTier.NEWS_SOURCE,
        "timesofindia.indiatimes.com": SourceTrustTier.NEWS_SOURCE,

        # Community Sources (0.40)
        "medium.com": SourceTrustTier.COMMUNITY_SOURCE,
        "dev.to": SourceTrustTier.COMMUNITY_SOURCE,
        "reddit.com": SourceTrustTier.COMMUNITY_SOURCE,
        "linkedin.com": SourceTrustTier.COMMUNITY_SOURCE,
    }

    def __init__(self, custom_tiers: Optional[Dict[str, SourceTrustTier]] = None):
        self.domain_tiers = dict(self.DEFAULT_DOMAIN_TIERS)
        if custom_tiers:
            self.domain_tiers.update(custom_tiers)

    @staticmethod
    def extract_domain(url: str) -> str:
        """Extract clean lowercase domain from URL."""
        if not url:
            return ""
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        parsed = urlparse(url)
        domain = (parsed.netloc or parsed.path).lower()
        # Strip port
        domain = domain.split(":")[0]
        # Strip leading www.
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    def evaluate_url(self, url: str) -> Tuple[float, bool]:
        """
        Evaluate a URL and return (trust_score, is_official_source).
        Trust score is between 0.20 and 1.00.
        """
        domain = self.extract_domain(url)
        if not domain:
            return SourceTrustTier.UNKNOWN.value, False

        # 1. Exact domain match
        if domain in self.domain_tiers:
            tier = self.domain_tiers[domain]
            is_official = tier in [SourceTrustTier.GOVERNMENT_OFFICIAL, SourceTrustTier.ORGANIZATION_OFFICIAL]
            return tier.value, is_official

        # 2. Subdomain check (e.g. news.google.com -> google.com)
        parts = domain.split(".")
        if len(parts) > 2:
            root_domain = ".".join(parts[-2:])
            if root_domain in self.domain_tiers:
                tier = self.domain_tiers[root_domain]
                is_official = tier in [SourceTrustTier.GOVERNMENT_OFFICIAL, SourceTrustTier.ORGANIZATION_OFFICIAL]
                return tier.value, is_official

        # 3. Government TLD heuristic (.gov.in, .gov, .nic.in, .ac.in, .edu)
        if domain.endswith((".gov.in", ".nic.in", ".gov")):
            return SourceTrustTier.GOVERNMENT_OFFICIAL.value, True
        if domain.endswith((".ac.in", ".edu")):
            return SourceTrustTier.ORGANIZATION_OFFICIAL.value, True

        return SourceTrustTier.UNKNOWN.value, False
