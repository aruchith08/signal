# SIGNAL 📡 — Source Trust System

## 1. Overview
Every internet source in SIGNAL is assigned a calibrated trust tier to govern fact consensus and conflict resolution.

## 2. Trust Tiers (`SourceTrustTier`)

| Tier | Trust Weight | Classification | Domain Examples |
|---|:---:|---|---|
| `GOVERNMENT_OFFICIAL` | 1.00 | Official Government Portals | `sih.gov.in`, `mygov.in`, `aicte-india.org`, `meity.gov.in`, `*.gov.in` |
| `ORGANIZATION_OFFICIAL`| 0.95 | Official Company / Host Websites | `tcs.com`, `summerofcode.withgoogle.com`, `github.blog`, `codeforces.com` |
| `OFFICIAL_PLATFORM` | 0.90 | Flagship Hackathon Ecosystems | `mlh.io`, `hackerearth.com`, `kaggle.com` |
| `VERIFIED_PARTNER` | 0.80 | Curated Student Platforms | `unstop.com`, `devfolio.co` |
| `REPUTABLE_PLATFORM` | 0.70 | Established Tech/Education Sites | `geeksforgeeks.org`, `coursera.org`, `internshala.com` |
| `NEWS_SOURCE` | 0.60 | Mainstream News Outlets | `thehindu.com`, `indianexpress.com`, `techcrunch.com` |
| `COMMUNITY_SOURCE` | 0.40 | Blogs & Social Platforms | `medium.com`, `dev.to`, `reddit.com`, `linkedin.com` |
| `UNKNOWN` | 0.20 | Unverified Third-Party Blogs | Any unrecognized domain |

## 3. Official Source Dominance Principle
When an official source (`GOVERNMENT_OFFICIAL` or `ORGANIZATION_OFFICIAL`) reports an attribute value (such as a deadline), it automatically **dominates** existing platform values in `VerifiedField` consensus.
