"""End-to-End Test Suite for Part 3: GIS Engine, Spatial Analysis, Validation, Output Generation, and Pipeline Integration."""

import pytest
import json
from app.schemas.query_schema import (
    QueryUnderstanding,
    WhatSchema,
    WhereSchema,
    WhenSchema,
    TargetSchema,
    MeasurementSchema,
    OutputFormatSchema,
)
from app.services.query_planner import QueryPlanner
from tests.test_query_planner_part1 import MockGroqService
from app.services.feature_matcher import FeatureMatcher
from app.services.spatial_engine import SpatialEngine
from app.services.validation_engine import ValidationEngine
from app.services.output_engine import OutputEngine
from app.services.end_to_end_engine import EndToEndEngine


@pytest.fixture
def planner():
    return QueryPlanner(service=MockGroqService())


@pytest.fixture
def e2e_engine(planner):
    return EndToEndEngine(planner=planner)


# -----------------------------------------------------------------------------
# 1. Mandatory End-to-End Drainage Query Test
# -----------------------------------------------------------------------------
def test_end_to_end_pune_drainage_and_building_proximity(e2e_engine):
    """
    Query: 'Find open drainage channels in Pune and identify buildings within 200 metres of them.
            Show the results on a map and export GeoJSON.'

    Tests complete end-to-end pipeline (Parts 1, 2, and 3):
    - Retrieve Pune boundary, drainage data, and building footprints
    - Execute vision adapters (SAM 2 & Grounding DINO)
    - Match AI detections to mapped vector GIS features
    - Calculate building-to-drainage metric distance in projected EPSG:3857 CRS
    - Filter buildings within 200m buffer
    - Validate geometry integrity & CRS EPSG:4326
    - Generate GeoJSON deliverable, CSV export, interactive map layers
    """
    understanding = QueryUnderstanding(
        what=WhatSchema(value="building proximity analysis to open drainage channels", confidence=1.0, provided_by_user=True),
        where=WhereSchema(value="Pune", confidence=1.0, provided_by_user=True),
        when=WhenSchema(value="Latest available", confidence=1.0, provided_by_user=True),
        target=TargetSchema(values=["open drainage channels", "buildings"], confidence=1.0, provided_by_user=True),
        measurement=MeasurementSchema(value="buildings within 200 metres of open drainage channels", confidence=1.0, provided_by_user=True),
        output_format=OutputFormatSchema(values=["interactive map", "GeoJSON", "CSV"], confidence=1.0, provided_by_user=True)
    )

    payload = e2e_engine.execute_end_to_end(understanding)
    data = payload.model_dump()

    assert data["status"] in ["completed", "partial_success"]
    assert data["plan_id"].startswith("plan_")

    # 1. Part 1 Plan Verification
    plan_data = data["plan"]
    assert plan_data["where"] == "Pune"
    assert "five_plans" in plan_data
    assert len(plan_data["five_plans"]["spatial_analysis_plan"]) > 0

    # 2. Part 2 Retrieval & Vision Verification
    retrieval_data = data["retrieval_result"]
    assert retrieval_data["total_assets_retrieved"] > 0

    visual_data = data["visual_detection_result"]
    assert visual_data["total_detections"] > 0
    assert len(visual_data["selected_models"]) > 0

    # 3. Part 3 GIS Engine & Feature Matching Verification
    spatial_data = data["spatial_engine_result"]
    assert spatial_data["total_features_processed"] > 0
    assert len(spatial_data["matched_features"]) > 0

    # Verify matching evidence details
    matched_item = spatial_data["matched_features"][0]
    assert "match_id" in matched_item
    assert "detection_confidence" in matched_item
    assert "matching_confidence" in matched_item
    assert matched_item["detection_confidence"] > 0.0

    # Verify Proximity Buffer Layer
    analysis_layers = spatial_data["analysis_layers"]
    assert len(analysis_layers) > 0

    buffer_layer = next(l for l in analysis_layers if l["operation"] == "distance_buffer_filter")
    assert buffer_layer["projected_crs_used"] == "EPSG:3857"
    assert buffer_layer["crs"] == "EPSG:4326"
    assert buffer_layer["item_count"] > 0

    # 4. Part 3 Validation Report Verification
    val_report = data["validation_report"]
    assert val_report["is_valid"] is True
    assert val_report["crs_validated"] == "EPSG:4326"
    assert val_report["geometry_validity_passed"] is True
    assert "average_detection_confidence" in val_report["confidence_summary"]

    # 5. Part 3 Deliverables Verification (GeoJSON & CSV Exports)
    deliverable = data["final_deliverable"]
    assert deliverable["status"] == "completed"

    geojson_exp = deliverable["geojson_export"]
    assert geojson_exp is not None
    assert geojson_exp["type"] == "FeatureCollection"
    assert len(geojson_exp["features"]) > 0

    csv_exp = deliverable["csv_export"]
    assert csv_exp is not None
    assert "feature_id" in csv_exp
    assert "detection_confidence" in csv_exp

    map_layers = deliverable["map_layers"]
    assert len(map_layers) >= 3
    layer_titles = [m["title"] for m in map_layers]
    assert any("Proximity Buffer" in t for t in layer_titles)


# -----------------------------------------------------------------------------
# 2. End-to-End Object Discovery / Satellite Image Search Test
# -----------------------------------------------------------------------------
def test_end_to_end_mumbai_satellite_image_search(e2e_engine):
    """Query: 'Search for Sentinel-2 satellite imagery of Mumbai from January 2024 with cloud cover < 10%'"""
    u = QueryUnderstanding(
        what=WhatSchema(value="satellite imagery search", confidence=1.0, provided_by_user=True),
        where=WhereSchema(value="Mumbai", confidence=1.0, provided_by_user=True),
        when=WhenSchema(value="January 2024", confidence=1.0, provided_by_user=True),
        target=TargetSchema(values=["Sentinel-2 satellite imagery"], confidence=1.0, provided_by_user=True),
        measurement=MeasurementSchema(value="cloud cover < 10%", confidence=1.0, provided_by_user=True),
        output_format=OutputFormatSchema(values=["image_metadata", "GeoTIFF"], confidence=1.0, provided_by_user=True)
    )

    payload = e2e_engine.execute_end_to_end(u)
    data = payload.model_dump()

    assert data["status"] == "completed"
    assert data["plan"]["when"] == "January 2024"
    assert "remote_clip" in data["visual_detection_result"]["selected_models"]
    assert data["final_deliverable"]["geojson_export"] is not None


# -----------------------------------------------------------------------------
# 3. End-to-End Two-Date Change Detection Test
# -----------------------------------------------------------------------------
def test_end_to_end_bangalore_urban_change_detection(e2e_engine):
    """Query: 'Detect urban expansion and building changes in Bangalore between 2020 and 2024'"""
    u = QueryUnderstanding(
        what=WhatSchema(value="urban expansion and building change detection", confidence=1.0, provided_by_user=True),
        where=WhereSchema(value="Bangalore", confidence=1.0, provided_by_user=True),
        when=WhenSchema(value="2020 to 2024", confidence=1.0, provided_by_user=True),
        target=TargetSchema(values=["buildings", "urban expansion"], confidence=1.0, provided_by_user=True),
        measurement=MeasurementSchema(value="bi-temporal change between 2020 and 2024", confidence=1.0, provided_by_user=True),
        output_format=OutputFormatSchema(values=["change map", "GeoJSON", "summary statistics"], confidence=1.0, provided_by_user=True)
    )

    payload = e2e_engine.execute_end_to_end(u)
    data = payload.model_dump()

    assert data["status"] == "completed"
    assert data["plan"]["when"] == "2020 to 2024"
    assert "changeformer" in data["visual_detection_result"]["selected_models"]
    assert data["spatial_engine_result"]["total_features_processed"] > 0
    assert data["final_deliverable"]["summary_statistics"] is not None
