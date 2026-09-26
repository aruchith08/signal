"""
SIGNAL 📡 — Ingestion Connectors Package
"""
from connectors.base_connector import BaseConnector, RawItem
from connectors.mock_connector import MockConnector
from connectors.competitive_programming.codeforces import CodeforcesConnector
from connectors.competitive_programming.codechef import CodeChefConnector
from connectors.competitive_programming.hackerrank import HackerRankConnector
from connectors.competitive_programming.leetcode import LeetCodeConnector
from connectors.companies.github_blog import GitHubBlogConnector
from connectors.government.sih import SIHConnector
from connectors.government.mygov import MyGovConnector
from connectors.open_source.gsoc import GSoCConnector
from connectors.hackathons.mlh import MLHConnector
from connectors.unstop import UnstopConnector
from connectors.devfolio import DevfolioConnector

__all__ = [
    "BaseConnector",
    "RawItem",
    "MockConnector",
    "CodeforcesConnector",
    "CodeChefConnector",
    "HackerRankConnector",
    "LeetCodeConnector",
    "GitHubBlogConnector",
    "SIHConnector",
    "MyGovConnector",
    "GSoCConnector",
    "MLHConnector",
    "UnstopConnector",
    "DevfolioConnector",
]

