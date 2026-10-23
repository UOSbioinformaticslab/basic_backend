"""
Filter Recommender Module for CRUK DataHub.
Loads and ingests filter rules from JSON to recommend taxonomy filters based on metadata.
"""
import os
import sys

# Ensure helpers can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers.filter_recommender import (
    FilterRecommender,
    recommend_filter,
    load_filter_rules,
)

__all__ = ["FilterRecommender", "recommend_filter", "load_filter_rules"]
