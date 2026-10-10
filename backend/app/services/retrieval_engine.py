"""FUSION 2026 - Main Data Retrieval Engine.

Coordinates the 6-component retrieval architecture:
1. Data Source Registry (Source capabilities & registered APIs)
2. Dataset Discovery (AOI, category, and dataset search)
3. Retrieval Connectors (Real API adapters: Nominatim, Overpass, OpenTopography, NASA FIRMS, STAC)
4. Data Validation (Status, CRS EPSG:4326, schema & file integrity)
5. Data Preparation (AOI clipping, CRS normalization, georeferencing)
6. Cache & Storage (Persistent asset storage and provenance manifest)

Executes structured instructions from AI Query Planner and returns actual retrieved assets and metadata.
"""

import logging
from typing import Optional, List, Dict, Any
from app.schemas.planner_schema import QueryPlan, DataRetrievalStep
from app.schemas.retrieval_schema import (
    RetrievalExecutionResult,
    RetrievedAssetMetadata,
)
from app.services.retrieval_registry import retrieval_registry, DataSourceRegistry
from app.services.retrieval_discovery import dataset_discovery_service, DatasetDiscoveryService
from app.services.retrieval_connectors import connector_engine, ConnectorEngine
from app.services.retrieval_validator import data_validator, DataValidator
from app.services.retrieval_preparation import data_preparation_service, DataPreparationService
from app.services.retrieval_cache import retrieval_cache_storage, RetrievalCacheStorage

logger = logging.getLogger(__name__)


class RetrievalEngine:
    """Executes structured data retrieval instructions from AI Query Planner."""

    def __init__(
        self,
        registry: Optional[DataSourceRegistry] = None,
        discovery: Optional[DatasetDiscoveryService] = None,
        connectors: Optional[ConnectorEngine] = None,
        validator: Optional[DataValidator] = None,
        prep: Optional[DataPreparationService] = None,
        cache: Optional[RetrievalCacheStorage] = None
    ):
        self.registry = registry or retrieval_registry
        self.discovery = discovery or dataset_discovery_service
        self.connectors = connectors or connector_engine
        self.validator = validator or data_validator
        self.prep = prep or data_preparation_service
        self.cache = cache or retrieval_cache_storage

    def execute_retrieval_plan(self, plan: QueryPlan) -> RetrievalExecutionResult:
        """
        Executes all required retrieval instructions in a QueryPlan.

        Args:
            plan: Validated QueryPlan Pydantic object.

        Returns:
            RetrievalExecutionResult: Summary of all retrieved asset artifacts & metadata.
        """
        logger.info(f"RetrievalEngine: Executing retrieval plan '{plan.plan_id}' for AOI '{plan.where}' ({len(plan.data_retrieval)} steps)")
        
        retrieved_assets: List[RetrievedAssetMetadata] = []
        all_warnings: List[str] = list(plan.validation_warnings)
        missing_flags: List[str] = list(plan.missing_data_flags)

        cache_dir = self.cache.get_cache_dir()

        for step in plan.data_retrieval:
            # Skip unnecessary datasets
            if step.requirement_level == "unnecessary":
                logger.info(f"RetrievalEngine: Skipping unnecessary dataset '{step.dataset_id}' ({step.category})")
                continue

            api_source_id = step.registered_source_api or "OSM_Overpass_API"
            cache_key = self.cache.compute_key(api_source_id, step.spatial_coverage, step.search_parameters)

            # 1. Check persistent cache
            cached_asset = self.cache.get(cache_key)
            if cached_asset:
                if step.category:
                    cached_asset.category = step.category
                retrieved_assets.append(cached_asset)
                continue

            # 2. Fetch using provider connector
            connector = self.connectors.get_connector(api_source_id)
            try:
                asset = connector.fetch(
                    spatial_coverage=step.spatial_coverage or plan.where,
                    search_parameters=step.search_parameters or {"query": plan.where},
                    output_dir=cache_dir
                )
                if step.category:
                    asset.category = step.category
            except Exception as exc:
                logger.error(f"RetrievalEngine: Connector '{api_source_id}' failed: {exc}")
                asset = RetrievedAssetMetadata(
                    asset_id=f"error_{step.dataset_id}",
                    source_id=api_source_id,
                    category=step.category or "Vector GIS Data",
                    provider=api_source_id,
                    format="None",
                    status="error",
                    warnings=[f"Connector execution failed: {str(exc)}"]
                )

            # 3. Validate
            is_valid, v_warnings = self.validator.validate_asset(asset)
            asset.warnings.extend(v_warnings)
            all_warnings.extend(v_warnings)

            # 4. Prepare / Normalize
            if is_valid and asset.status != "error":
                asset = self.prep.prepare(asset, target_crs="EPSG:4326")
                self.cache.put(cache_key, asset)

            retrieved_assets.append(asset)

        status = "completed"
        if any(a.status == "error" for a in retrieved_assets):
            status = "partial_success"
        if len(retrieved_assets) == 0:
            status = "completed"

        summary = f"Retrieved {len(retrieved_assets)} GIS assets across categories: {', '.join(set(a.category for a in retrieved_assets))}"

        return RetrievalExecutionResult(
            plan_id=plan.plan_id,
            status=status,
            total_assets_retrieved=len(retrieved_assets),
            assets=retrieved_assets,
            missing_data_flags=missing_flags,
            execution_summary=summary,
            warnings=all_warnings
        )


# Singleton Instance
retrieval_engine = RetrievalEngine()
