"""
Conflict Detection Engine — Identifies fact-level discrepancies between sources
Detects deadline, eligibility, URL, year, and season conflicts across contributing sources.
"""
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
from typing import Any, Dict, List, Optional
from shared.constants import ConflictStatus

logger = logging.getLogger("signal.conflict_detector")


@dataclass
class FieldConflict:
    field_name: str
    conflicting_values: List[Any]
    source_details: List[Dict[str, Any]]
    is_critical: bool = False


class ConflictDetector:
    """Detects discrepancies between existing canonical opportunity and an incoming discovery/source."""

    @staticmethod
    def detect_conflicts(
        canonical_data: Dict[str, Any],
        incoming_data: Dict[str, Any],
        incoming_source_info: Dict[str, Any],
    ) -> List[FieldConflict]:
        """
        Compare canonical fields with incoming source fields.
        Detects:
        - Deadline date differences
        - Eligibility requirements differences
        - Application URL differences
        - Year differences
        - Season differences
        """
        conflicts: List[FieldConflict] = []

        # 1. Deadline Conflict
        can_deadline = canonical_data.get("deadline_date") or canonical_data.get("deadline")
        inc_deadline = incoming_data.get("deadline_date") or incoming_data.get("deadline")

        if can_deadline and inc_deadline:
            # Normalize to string dates
            str_can = str(can_deadline).split("T")[0].split(" ")[0]
            str_inc = str(inc_deadline).split("T")[0].split(" ")[0]
            if str_can != str_inc:
                conflicts.append(
                    FieldConflict(
                        field_name="deadline",
                        conflicting_values=[str_can, str_inc],
                        source_details=[
                            {"type": "canonical", "value": str_can},
                            {"type": "incoming", "value": str_inc, **incoming_source_info},
                        ],
                        is_critical=True,
                    )
                )

        # 2. Year Conflict
        can_year = canonical_data.get("year")
        inc_year = incoming_data.get("year")
        if can_year and inc_year and int(can_year) != int(inc_year):
            conflicts.append(
                FieldConflict(
                    field_name="year",
                    conflicting_values=[int(can_year), int(inc_year)],
                    source_details=[
                        {"type": "canonical", "value": can_year},
                        {"type": "incoming", "value": inc_year, **incoming_source_info},
                    ],
                    is_critical=True,
                )
            )

        # 3. Season Conflict
        can_season = str(canonical_data.get("season") or "").strip().lower()
        inc_season = str(incoming_data.get("season") or "").strip().lower()
        if can_season and inc_season and can_season != inc_season:
            conflicts.append(
                FieldConflict(
                    field_name="season",
                    conflicting_values=[can_season, inc_season],
                    source_details=[
                        {"type": "canonical", "value": can_season},
                        {"type": "incoming", "value": inc_season, **incoming_source_info},
                    ],
                    is_critical=False,
                )
            )

        # 4. Application URL Conflict (Official portal vs Aggregator portal)
        can_url = canonical_data.get("application_url")
        inc_url = incoming_data.get("application_url") or incoming_data.get("canonical_url")
        if can_url and inc_url and str(can_url).rstrip("/") != str(inc_url).rstrip("/"):
            # Only record if neither is a sub-path of the other
            if str(can_url) not in str(inc_url) and str(inc_url) not in str(can_url):
                conflicts.append(
                    FieldConflict(
                        field_name="application_url",
                        conflicting_values=[can_url, inc_url],
                        source_details=[
                            {"type": "canonical", "value": can_url},
                            {"type": "incoming", "value": inc_url, **incoming_source_info},
                        ],
                        is_critical=False,
                    )
                )

        # 5. Eligibility Conflict
        can_elig = str(canonical_data.get("eligibility") or "").strip().lower()
        inc_elig = str(incoming_data.get("eligibility") or "").strip().lower()
        if can_elig and inc_elig and len(can_elig) > 5 and len(inc_elig) > 5:
            # Check for substantial disagreement in education degree mentions
            degree_tokens = {"b.tech", "m.tech", "bca", "mca", "b.sc", "m.sc", "ph.d"}
            can_degrees = {d for d in degree_tokens if d in can_elig}
            inc_degrees = {d for d in degree_tokens if d in inc_elig}
            if can_degrees and inc_degrees and not (can_degrees & inc_degrees):
                conflicts.append(
                    FieldConflict(
                        field_name="eligibility",
                        conflicting_values=[can_elig[:100], inc_elig[:100]],
                        source_details=[
                            {"type": "canonical", "value": can_elig},
                            {"type": "incoming", "value": inc_elig, **incoming_source_info},
                        ],
                        is_critical=True,
                    )
                )

        return conflicts
