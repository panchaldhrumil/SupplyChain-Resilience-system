"""
Processors package — deduplication, filtering, and tagging.
"""
from .deduplicator import _deduplicate_day_group
from .impact_mapper import _get_impact
from .corridor_tagger import apply_corridor_impact
from .relevance_filter import (
    _is_relevant,
    _passes_outcome_gate,
    _is_official,
    _source_score,
)

__all__ = [
    "_deduplicate_day_group",
    "_get_impact",
    "apply_corridor_impact",
    "_is_relevant",
    "_passes_outcome_gate",
    "_is_official",
    "_source_score",
]
