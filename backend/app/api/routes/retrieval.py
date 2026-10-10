"""FastAPI routes for GEOAI-05 Data Retrieval Engine."""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Body
from app.schemas.retrieval_schema import (
    DataSourceRegistryEntry,
    DatasetDiscoveryQuery,
    DatasetDiscoveryResult,
    RetrievalExecutionResult,
)
from app.schemas.planner_schema import QueryPlan
from app.services.retrieval_registry import retrieval_registry
from app.services.retrieval_discovery import dataset_discovery_service
from app.services.retrieval_engine import retrieval_engine

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.get("/registry", response_model=List[DataSourceRegistryEntry])
def list_registry(
    category: Optional[str] = Query(None, description="Filter by category"),
    connector_status: Optional[str] = Query(None, description="Filter by status: implemented, requires_credentials, registry_only, unsupported")
):
    """Returns all verified data sources in the Data Source Registry."""
    return retrieval_registry.list_sources(category=category, connector_status=connector_status)


@router.post("/discover", response_model=DatasetDiscoveryResult)
def discover_datasets(query: DatasetDiscoveryQuery):
    """Searches catalogues for matching registered sources using AOI, dataset type, and category."""
    return dataset_discovery_service.discover(query)


@router.post("/execute", response_model=RetrievalExecutionResult)
def execute_retrieval(plan: QueryPlan):
    """
    Executes a structured QueryPlan via provider-specific connectors,
    validating CRS/formats and saving assets to local cache storage.
    """
    try:
        return retrieval_engine.execute_retrieval_plan(plan)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Retrieval Engine execution failed: {str(exc)}")


@router.get("/models")
def list_models():
    """Returns all machine-readable vision, foundation, and change detection models in Model Registry."""
    from app.services.model_registry import list_registered_models
    return [m.model_dump() for m in list_registered_models()]


@router.get("/tools")
def list_tools():
    """Returns all machine-readable GIS tools and spatial database engines in Tool Registry."""
    from app.services.model_registry import list_registered_tools
    return [t.model_dump() for t in list_registered_tools()]


@router.post("/part2/execute")
def execute_part2(plan: QueryPlan):
    """
    Executes Part 2 Data Retrieval Engine and Visual Detection Engine pipelines for a QueryPlan.
    Returns dual structured outputs (Data Retrieval Result + Visual Detection Result).
    """
    from app.services.part2_engine import part2_engine
    try:
        res = part2_engine.execute_part2(plan)
        return res.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Part 2 integrated engine execution failed: {str(exc)}")


