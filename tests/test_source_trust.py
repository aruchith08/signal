"""
Unit Tests for SourceTrustService
"""
import unittest
from services.verification.source_trust import SourceTrustService
from shared.constants import SourceTrustTier


class TestSourceTrustService(unittest.TestCase):
    def setUp(self):
        self.service = SourceTrustService()

    def test_government_official_domains(self):
        urls = [
            "https://sih.gov.in/problem-statements",
            "https://innovateindia.mygov.in/challenges",
            "https://www.aicte-india.org/schemes",
            "https://meity.gov.in/initiatives",
            "https://subdomain.nic.in/portal",
        ]
        for url in urls:
            trust, is_official = self.service.evaluate_url(url)
            self.assertEqual(trust, SourceTrustTier.GOVERNMENT_OFFICIAL.value, f"Failed for {url}")
            self.assertTrue(is_official, f"Expected official for {url}")

    def test_organization_official_domains(self):
        urls = [
            "https://codevita.tcs.com/registration",
            "https://summerofcode.withgoogle.com/archive",
            "https://opensource.googleblog.com/2026/03/gsoc.html",
            "https://github.blog/news",
            "https://codeforces.com/contests",
        ]
        for url in urls:
            trust, is_official = self.service.evaluate_url(url)
            self.assertEqual(trust, SourceTrustTier.ORGANIZATION_OFFICIAL.value, f"Failed for {url}")
            self.assertTrue(is_official, f"Expected official for {url}")

    def test_curated_platforms(self):
        trust, is_official = self.service.evaluate_url("https://unstop.com/hackathons/codevita-2026")
        self.assertEqual(trust, SourceTrustTier.VERIFIED_PARTNER.value)
        self.assertFalse(is_official)

        trust, is_official = self.service.evaluate_url("https://devfolio.co/hackathons")
        self.assertEqual(trust, SourceTrustTier.VERIFIED_PARTNER.value)
        self.assertFalse(is_official)

    def test_news_and_community(self):
        trust, is_official = self.service.evaluate_url("https://thehindu.com/education/tcs-codevita")
        self.assertEqual(trust, SourceTrustTier.NEWS_SOURCE.value)
        self.assertFalse(is_official)

        trust, is_official = self.service.evaluate_url("https://medium.com/@dev/my-experience")
        self.assertEqual(trust, SourceTrustTier.COMMUNITY_SOURCE.value)
        self.assertFalse(is_official)

    def test_unknown_domain_fallback(self):
        trust, is_official = self.service.evaluate_url("https://random-unknown-blog-12345.xyz/post")
        self.assertEqual(trust, SourceTrustTier.UNKNOWN.value)
        self.assertFalse(is_official)


if __name__ == "__main__":
    unittest.main()
