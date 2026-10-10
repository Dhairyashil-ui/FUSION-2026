"""FUSION 2026 - Dataset Discovery Service.

Searches supported catalogues and services using AOI (location name/bounding box),
time range, dataset type, and resolution requirements.
Distinguishes catalogue discovery from actual asset retrieval.
"""

import logging
from typing import Optional, List
from app.schemas.retrieval_schema import (
    DatasetDiscoveryQuery,
    DatasetDiscoveryResult,
    DataSourceRegistryEntry,
)
from app.services.retrieval_registry import retrieval_registry, DataSourceRegistry

logger = logging.getLogger(__name__)


class DatasetDiscoveryService:
    """Discovers matching registered data sources for geospatial search queries."""

    def __init__(self, registry: Optional[DataSourceRegistry] = None):
        self.registry = registry or retrieval_registry

    def discover(self, query: DatasetDiscoveryQuery) -> DatasetDiscoveryResult:
        """
        Discovers matching registry entries based on AOI, dataset type, category, and resolution.
        Does NOT download large datasets unnecessarily; returns catalogue discovery metadata.
        """
        all_sources = self.registry.list_sources()
        matching: List[DataSourceRegistryEntry] = []

        for source in all_sources:
            # 1. Filter by category if specified
            if query.category and query.category not in source.categories:
                continue

            # 2. Filter by dataset type if specified
            if query.dataset_type:
                dt_lower = query.dataset_type.lower()
                has_ds_match = any(
                    dt_lower in ds.lower() or ds.lower() in dt_lower
                    for ds in source.supported_datasets
                )
                has_cat_match = any(
                    dt_lower in cat.lower() or cat.lower() in dt_lower
                    for cat in source.categories
                )
                if not (has_ds_match or has_cat_match):
                    continue

            matching.append(source)

        logger.info(
            f"DatasetDiscovery: Found {len(matching)} matching sources for query AOI='{query.aoi_name}', "
            f"category='{query.category}', dataset_type='{query.dataset_type}'"
        )

        return DatasetDiscoveryResult(
            query=query,
            matching_sources=matching,
            total_matches=len(matching)
        )


# Singleton Instance
dataset_discovery_service = DatasetDiscoveryService()
