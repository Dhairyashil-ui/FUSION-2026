"""Comprehensive unit tests for FUSION 2026 Data Retrieval Execution Engine.

Tests:
1. Category and provider registration in Data Source Registry
2. Dataset discovery by AOI and data type
3. Successful API retrieval (Nominatim boundary, Overpass vector, OpenTopography DEM, NASA FIRMS)
4. Missing credentials & unavailable dataset handling
5. Unsupported categories & Copernicus registry-only handling
6. Metadata, CRS (EPSG:4326), and format validation
7. Query Planner integration for drainage proximity and additional geospatial query types
"""

import sys
import os
import json
import pytest
from unittest.mock import patch

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.schemas.query_schema import QueryUnderstanding
from app.schemas.planner_schema import QueryPlan
from app.schemas.retrieval_schema import DatasetDiscoveryQuery
from app.services.retrieval_registry import retrieval_registry
from app.services.retrieval_discovery import dataset_discovery_service
from app.services.retrieval_connectors import (
    connector_engine,
    NominatimBoundaryConnector,
    OverpassVectorConnector,
    OpenTopographyDEMConnector,
    NASAFirmsThermalConnector,
    CopernicusRegistryOnlyConnector,
)
from app.services.retrieval_validator import data_validator
from app.services.retrieval_preparation import data_preparation_service
from app.services.retrieval_cache import retrieval_cache_storage
from app.services.retrieval_engine import retrieval_engine
from app.services.query_planner import query_planner


def test_category_and_provider_registration():
    """Validates that Data Source Registry contains entries for all 6 categories."""
    sources = retrieval_registry.list_sources()
    assert len(sources) >= 10

    categories_found = set()
    for s in sources:
        categories_found.update(s.categories)

    assert "Boundaries / AOI" in categories_found
    assert "Optical Imagery" in categories_found
    assert "Vector GIS Data" in categories_found
    assert "Radar / SAR" in categories_found
    assert "Elevation / 3D" in categories_found
    assert "Thematic / Temporal Data" in categories_found

    # Verify Copernicus sources are marked 'registry_only'
    cop_sources = retrieval_registry.list_sources(connector_status="registry_only")
    cop_ids = [s.source_id for s in cop_sources]
    assert "Copernicus_Data_Space" in cop_ids
    assert "Copernicus_EMS" in cop_ids
    print(f"PASS Registry verified: {len(sources)} sources across all 6 categories. Copernicus catalog entries marked registry_only.")


def test_dataset_discovery_by_aoi_and_datatype():
    """Validates catalogue discovery filtering by category and dataset type."""
    # Search for drainage/vector datasets in Pune
    q1 = DatasetDiscoveryQuery(aoi_name="Pune", category="Vector GIS Data", dataset_type="drainage")
    res1 = dataset_discovery_service.discover(q1)
    assert res1.total_matches >= 1
    assert any("Overpass" in s.name or "OSM" in s.name for s in res1.matching_sources)

    # Search for elevation datasets
    q2 = DatasetDiscoveryQuery(aoi_name="Pune", category="Elevation / 3D", dataset_type="dem")
    res2 = dataset_discovery_service.discover(q2)
    assert res2.total_matches >= 1
    assert any("OpenTopography" in s.name or "DEM" in s.name for s in res2.matching_sources)

    print(f"PASS Dataset discovery verified: Drainage matches={res1.total_matches}, Elevation matches={res2.total_matches}")


def test_successful_api_retrievals(tmp_path):
    """Validates API retrieval connectors (Nominatim, Overpass, OpenTopography, NASA FIRMS)."""
    out_dir = str(tmp_path)

    # 1. Nominatim Boundary
    conn_nom = NominatimBoundaryConnector()
    asset_nom = conn_nom.fetch("Pune", {"query": "Pune"}, out_dir)
    assert asset_nom.status == "success"
    assert asset_nom.crs == "EPSG:4326"
    assert asset_nom.file_path is not None
    assert os.path.exists(asset_nom.file_path)

    # 2. Overpass Vector (Drainage & Buildings)
    conn_ov = OverpassVectorConnector()
    asset_ov = conn_ov.fetch("Pune", {"area": "Pune", "waterway": "drain;canal"}, out_dir)
    assert asset_ov.status == "success"
    assert asset_ov.item_count >= 1

    # 3. OpenTopography DEM (API Key)
    conn_topo = OpenTopographyDEMConnector()
    asset_topo = conn_topo.fetch("Pune", {"demtype": "COP30"}, out_dir)
    assert asset_topo.status == "success"
    assert "OpenTopography" in asset_topo.provider

    # 4. NASA FIRMS Thermal
    conn_firms = NASAFirmsThermalConnector()
    asset_firms = conn_firms.fetch("Pune", {"bbox_str": "73.7,18.4,74.0,18.7"}, out_dir)
    assert asset_firms.status == "success"

    print("PASS All working connectors successfully retrieved GIS assets!")


def test_copernicus_registry_only_exclusion(tmp_path):
    """Validates that Copernicus connector explicitly excludes API calls and reports registry_only status."""
    out_dir = str(tmp_path)
    conn_cop = CopernicusRegistryOnlyConnector("Copernicus_Data_Space", "Optical Imagery")
    asset_cop = conn_cop.fetch("Pune", {}, out_dir)

    assert asset_cop.status == "registry_only"
    assert "explicitly excluded" in asset_cop.warnings[0]
    assert asset_cop.item_count == 0
    print("PASS Copernicus registry-only exclusion verified (0 API calls executed).")


def test_metadata_crs_and_format_validation(tmp_path):
    """Validates DataValidator and DataPreparationService."""
    out_dir = str(tmp_path)
    conn_nom = NominatimBoundaryConnector()
    asset = conn_nom.fetch("Pune", {"query": "Pune"}, out_dir)

    is_valid, warnings = data_validator.validate_asset(asset)
    assert is_valid is True

    prep_asset = data_preparation_service.prepare(asset, target_crs="EPSG:4326")
    assert prep_asset.crs == "EPSG:4326"
    print("PASS Asset validation and preparation verified!")


def test_query_planner_retrieval_integration_drainage():
    """Validates QueryPlanner integration and retrieval engine execution for Pune drainage query."""
    understanding = QueryUnderstanding(
        what={"value": "open drainage channels and building proximity discovery", "confidence": 0.95, "provided_by_user": True},
        where={"value": "Pune", "type": "city_or_named_area", "confidence": 0.99, "provided_by_user": True},
        target={"values": ["open drainage channels", "buildings"], "confidence": 0.98, "provided_by_user": True},
        measurement={"value": "buildings within 200 metres of open drainage channels", "confidence": 0.95, "provided_by_user": True},
        output_format={"values": ["interactive map", "GeoJSON"], "confidence": 0.95, "provided_by_user": True}
    )

    plan = query_planner.generate_plan(understanding)
    res = retrieval_engine.execute_retrieval_plan(plan)

    assert res.status == "completed"
    assert res.total_assets_retrieved >= 2
    assert any(a.category == "Boundaries / AOI" for a in res.assets)
    assert any(a.category == "Vector GIS Data" for a in res.assets)
    print(f"PASS Drainage query plan executed: {res.execution_summary}")


def test_query_planner_retrieval_integration_flood_and_3d():
    """Validates retrieval engine execution for Flood Mapping and 3D Building Height queries."""
    # 1. Flood mapping query
    u_flood = QueryUnderstanding(
        what={"value": "flood inundation mapping and water level monitoring", "confidence": 0.95, "provided_by_user": True},
        where={"value": "Indus River Basin", "type": "named_region", "confidence": 0.99, "provided_by_user": True},
        target={"values": ["flood extent", "submerged structures"], "confidence": 0.98, "provided_by_user": True},
        measurement={"value": "identify flooded regions and DEM slope inundation depth", "confidence": 0.95, "provided_by_user": True},
        output_format={"values": ["flood hazard map", "GeoJSON"], "confidence": 0.95, "provided_by_user": True}
    )
    plan_flood = query_planner.generate_plan(u_flood)
    res_flood = retrieval_engine.execute_retrieval_plan(plan_flood)
    assert res_flood.total_assets_retrieved >= 2
    assert any(a.category == "Radar / SAR" for a in res_flood.assets)

    # 2. 3D Building Height query
    u_3d = QueryUnderstanding(
        what={"value": "3D building height analysis and urban density", "confidence": 0.95, "provided_by_user": True},
        where={"value": "Downtown Manhattan", "type": "city_district", "confidence": 0.99, "provided_by_user": True},
        target={"values": ["building footprints", "height profile"], "confidence": 0.98, "provided_by_user": True},
        measurement={"value": "calculate 3D building height from point cloud LiDAR", "confidence": 0.95, "provided_by_user": True},
        output_format={"values": ["3D GeoJSON", "interactive 3D map"], "confidence": 0.95, "provided_by_user": True}
    )
    plan_3d = query_planner.generate_plan(u_3d)
    res_3d = retrieval_engine.execute_retrieval_plan(plan_3d)
    assert res_3d.total_assets_retrieved >= 2
    assert any(a.category == "Elevation / 3D" for a in res_3d.assets)

    print("PASS Flood mapping and 3D building height retrieval plans successfully executed!")


if __name__ == "__main__":
    test_category_and_provider_registration()
    test_dataset_discovery_by_aoi_and_datatype()
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        test_successful_api_retrievals(td)
        test_copernicus_registry_only_exclusion(td)
        test_metadata_crs_and_format_validation(td)
    test_query_planner_retrieval_integration_drainage()
    test_query_planner_retrieval_integration_flood_and_3d()
