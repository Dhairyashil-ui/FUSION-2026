"""Unit and Integration Tests for Part 2: Data Retrieval and Visual Detection Engines."""

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
from app.schemas.planner_schema import QueryPlan, VisualSearchStep, DataRetrievalStep
from app.schemas.vision_schema import VisualDetectionResult, Part2ExecutionResult
from app.services.query_planner import QueryPlanner
from tests.test_query_planner_part1 import MockGroqService
from app.services.retrieval_engine import RetrievalEngine
from app.services.vision_engine import VisionEngine, vision_engine
from app.services.part2_engine import Part2Engine, part2_engine
from app.services.retrieval_connectors import CopernicusRegistryOnlyConnector



@pytest.fixture
def planner():
    return QueryPlanner(service=MockGroqService())


@pytest.fixture
def part2():
    return Part2Engine()


# -----------------------------------------------------------------------------
# 1. Test Model Loading & Lazy Initialization across All 7 Vision Models
# -----------------------------------------------------------------------------
def test_all_seven_vision_models_loading_and_inference():
    """Verifies lazy model loading, CPU/CUDA device selection, and prediction for all 7 registered vision models."""
    ve = VisionEngine()
    models_to_test = [
        "grounding_dino",
        "yolo_world",
        "sam_2",
        "segformer",
        "prithvi",
        "changeformer",
        "remote_clip",
    ]

    for model_id in models_to_test:
        adapter = ve.get_adapter(model_id)
        assert adapter is not None
        assert adapter.model_id == model_id

        # Verify lazy loading
        assert adapter.load_model() is True

        # Run prediction
        items = adapter.predict(
            image_input="test_image.tif",
            target_entity="test_feature",
            text_prompt="detect test feature",
            confidence_threshold=0.75,
            aoi_bbox=[73.80, 18.45, 73.95, 18.60]
        )

        assert len(items) > 0
        for item in items:
            assert item.model_id == model_id
            assert item.confidence >= 0.70
            assert item.crs == "EPSG:4326"
            assert item.georeferencing_status == "verified"
            assert item.geometry_type in ["Polygon", "MultiPolygon", "BoundingBox"]
            assert "coordinates" in item.georeferenced_geometry


# -----------------------------------------------------------------------------
# 2. Test Copernicus API Call Exclusion (Must be registry_only)
# -----------------------------------------------------------------------------
def test_copernicus_no_api_calls_enforcement():
    """Confirms Copernicus API connectors remain registry_only and DO NOT perform direct API calls."""
    connector = CopernicusRegistryOnlyConnector()
    assert connector.source_id == "Copernicus_Data_Space"


    asset = connector.fetch(spatial_coverage="Pune", search_parameters={}, output_dir="./storage")
    assert asset.status == "registry_only"
    assert "Copernicus API integration is explicitly excluded by specification" in asset.warnings[0]


# -----------------------------------------------------------------------------
# 3. Query-Specific Model Selection & Execution
# -----------------------------------------------------------------------------
def test_query_specific_model_selection_execution(planner, part2):
    """
    Verifies Part 2 integrated engine executes specific vision models tailored to query intent:
    - Drainage & Buildings -> Grounding DINO & SAM 2
    - Satellite Image Search -> RemoteCLIP
    - Urban Green Space -> SegFormer
    - Urban Change Detection -> ChangeFormer
    """
    # 1. Drainage Query (Grounding DINO & SAM 2)
    u_drain = QueryUnderstanding(
        what=WhatSchema(value="drainage analysis", confidence=1.0, provided_by_user=True),
        where=WhereSchema(value="Pune", confidence=1.0, provided_by_user=True),
        target=TargetSchema(values=["open drainage channels", "buildings"], confidence=1.0, provided_by_user=True),
        measurement=MeasurementSchema(value="buildings within 200m", confidence=1.0, provided_by_user=True),
        output_format=OutputFormatSchema(values=["GeoJSON"], confidence=1.0, provided_by_user=True)
    )
    plan_drain = planner.generate_plan(u_drain)
    res_drain = part2.execute_part2(plan_drain)

    assert res_drain.status in ["completed", "partial_success"]
    assert res_drain.visual_detection_result.total_detections > 0
    models_drain = res_drain.visual_detection_result.selected_models
    assert any(m in ["grounding_dino", "sam_2"] for m in models_drain)

    # 2. Image Search Query (RemoteCLIP)
    u_search = QueryUnderstanding(
        what=WhatSchema(value="satellite image search", confidence=1.0, provided_by_user=True),
        where=WhereSchema(value="Mumbai", confidence=1.0, provided_by_user=True),
        when=WhenSchema(value="January 2024", confidence=1.0, provided_by_user=True),
        target=TargetSchema(values=["Sentinel-2 satellite imagery"], confidence=1.0, provided_by_user=True),
        measurement=MeasurementSchema(value="cloud cover < 10%", confidence=1.0, provided_by_user=True),
        output_format=OutputFormatSchema(values=["GeoTIFF"], confidence=1.0, provided_by_user=True)
    )
    plan_search = planner.generate_plan(u_search)
    res_search = part2.execute_part2(plan_search)

    models_search = res_search.visual_detection_result.selected_models
    assert "remote_clip" in models_search

    # 3. Change Detection Query (ChangeFormer)
    u_change = QueryUnderstanding(
        what=WhatSchema(value="urban change detection", confidence=1.0, provided_by_user=True),
        where=WhereSchema(value="Bangalore", confidence=1.0, provided_by_user=True),
        when=WhenSchema(value="2020 to 2024", confidence=1.0, provided_by_user=True),
        target=TargetSchema(values=["buildings", "urban expansion"], confidence=1.0, provided_by_user=True),
        measurement=MeasurementSchema(value="bitemporal change", confidence=1.0, provided_by_user=True),
        output_format=OutputFormatSchema(values=["change map"], confidence=1.0, provided_by_user=True)
    )
    plan_change = planner.generate_plan(u_change)
    res_change = part2.execute_part2(plan_change)

    models_change = res_change.visual_detection_result.selected_models
    assert "changeformer" in models_change


# -----------------------------------------------------------------------------
# 4. Multi-Tile Georeferencing and Format Preservation
# -----------------------------------------------------------------------------
def test_multi_tile_georeferencing_and_metadata(planner, part2):
    """Verifies that DetectionResultItem objects accurately transform pixel coords to EPSG:4326 GeoJSON polygons."""
    u = QueryUnderstanding(
        what=WhatSchema(value="green space segmentation", confidence=1.0, provided_by_user=True),
        where=WhereSchema(value="Delhi", confidence=1.0, provided_by_user=True),
        target=TargetSchema(values=["urban green spaces"], confidence=1.0, provided_by_user=True),
        measurement=MeasurementSchema(value="segment green areas", confidence=1.0, provided_by_user=True),
        output_format=OutputFormatSchema(values=["GeoJSON"], confidence=1.0, provided_by_user=True)
    )

    plan = planner.generate_plan(u)
    res = part2.execute_part2(plan)

    det_result = res.visual_detection_result
    assert det_result.total_detections > 0

    for det in det_result.detections:
        assert det.crs == "EPSG:4326"
        assert det.georeferencing_status == "verified"
        assert det.geometry_type in ["Polygon", "MultiPolygon", "BoundingBox"]
        coords = det.georeferenced_geometry.get("coordinates", [])
        assert len(coords) > 0
        if det.geometry_type == "Polygon":
            ring = coords[0]
        elif det.geometry_type == "MultiPolygon":
            ring = coords[0][0]
        else:
            ring = coords[0] if isinstance(coords[0][0], (list, tuple)) else coords

        for pt in ring:
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                lon, lat = pt[0], pt[1]
                assert -180.0 <= lon <= 180.0
                assert -90.0 <= lat <= 90.0



# -----------------------------------------------------------------------------
# 5. Dual Output Structure for Part 3 Compatibility
# -----------------------------------------------------------------------------
def test_part2_dual_output_structure(planner, part2):
    """Validates that Part2Engine produces dual structured outputs compatible with Part 3 Spatial Analysis."""
    u = QueryUnderstanding(
        what=WhatSchema(value="building proximity analysis", confidence=1.0, provided_by_user=True),
        where=WhereSchema(value="Pune", confidence=1.0, provided_by_user=True),
        target=TargetSchema(values=["open drainage channels", "buildings"], confidence=1.0, provided_by_user=True),
        measurement=MeasurementSchema(value="buildings within 200m", confidence=1.0, provided_by_user=True),
        output_format=OutputFormatSchema(values=["interactive map", "GeoJSON"], confidence=1.0, provided_by_user=True)
    )

    plan = planner.generate_plan(u)
    part2_res = part2.execute_part2(plan)

    # 1. Data Retrieval Result
    retrieval_data = part2_res.retrieval_result
    assert "status" in retrieval_data
    assert "total_assets_retrieved" in retrieval_data
    assert "assets" in retrieval_data

    # 2. Visual Detection Result
    visual_data = part2_res.visual_detection_result
    assert visual_data.total_detections > 0
    assert len(visual_data.selected_models) > 0

    # 3. Overall Execution Summary
    assert part2_res.plan_id == plan.plan_id
    assert "Part 2 Execution Completed" in part2_res.execution_summary
