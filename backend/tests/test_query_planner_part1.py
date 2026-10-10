"""Unit and Integration Tests for Part 1: Query Planner and Execution Planning Architecture."""

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
from app.services.sufficiency_checker import SufficiencyChecker
from app.services.context_merger import ContextMerger
from app.services.model_registry import (
    get_registered_model,
    get_registered_tool,
    list_registered_models,
    list_registered_tools,
)


class MockGroqService:
    """Mock Groq service for fast deterministic unit testing without external API calls."""
    def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.0, response_format: dict = None) -> str:
        raise Exception("Mocked Groq Service - fallback to dynamic rule planner")


@pytest.fixture
def planner():
    return QueryPlanner(service=MockGroqService())



@pytest.fixture
def checker():
    return SufficiencyChecker()


@pytest.fixture
def merger():
    return ContextMerger()


# -----------------------------------------------------------------------------
# 1. Drainage Proximity Query
# -----------------------------------------------------------------------------
def test_drainage_proximity_query_plan(planner):
    """
    Query: 'Find open drainage channels in Pune and identify buildings within 200 metres of them.'
    Must generate 5 structured plans, specify vector datasets & Grounding DINO/SAM 2,
    and 200m buffer using GeoPandas/Shapely.
    """
    understanding = QueryUnderstanding(
        what=WhatSchema(value="building proximity analysis to open drainage channels", provided_by_user=True),
        where=WhereSchema(value="Pune", provided_by_user=True),
        when=WhenSchema(value="Latest available", provided_by_user=False),
        target=TargetSchema(values=["open drainage channels", "buildings"], provided_by_user=True),
        measurement=MeasurementSchema(value="buildings within 200 metres of open drainage channels", provided_by_user=True),
        output_format=OutputFormatSchema(values=["interactive map", "GeoJSON"], provided_by_user=True)
    )

    plan = planner.generate_plan(understanding)

    assert plan.is_valid is True
    assert plan.plan_id.startswith("plan_")
    assert plan.where == "Pune"
    assert "open drainage channels" in plan.target
    assert "buildings" in plan.target

    # Validate Five Plans structure
    assert plan.five_plans is not None
    assert len(plan.five_plans.data_retrieval_plan) > 0
    assert len(plan.five_plans.visual_detection_plan) > 0
    assert len(plan.five_plans.spatial_analysis_plan) > 0
    assert plan.five_plans.validation_plan.crs_validation == "EPSG:4326"
    assert "GeoJSON" in plan.five_plans.output_and_visualization_plan.export_formats

    # Validate Data Retrieval Plan: Boundaries and Vector GIS Data required; Radar/Elevation unnecessary
    retrieval_cats = [step.category for step in plan.data_retrieval]
    assert "Boundaries / AOI" in retrieval_cats
    assert "Vector GIS Data" in retrieval_cats

    # Check requirement levels
    bound_step = next(s for s in plan.data_retrieval if s.category == "Boundaries / AOI")
    assert bound_step.requirement_level == "required"

    # Validate Visual Detection Plan: Grounding DINO / SAM 2 selected
    visual_models = [step.model for step in plan.visual_search]
    assert any(m in ["grounding_dino", "sam_2", "grounding_dino_geo", "segment_anything_geo"] for m in visual_models)

    # Validate Spatial Analysis Plan: distance_buffer_filter with threshold 200m & GeoPandas/Shapely
    spatial_ops = [step.operation for step in plan.spatial_analysis]
    assert "distance_buffer_filter" in spatial_ops

    spatial_step = next(s for s in plan.spatial_analysis if s.operation == "distance_buffer_filter")
    assert spatial_step.parameters.get("threshold_meters") == 200
    assert "GeoPandas" in spatial_step.tools_used or "Shapely" in spatial_step.tools_used

    # Validate Selected Models and Tools Metadata
    assert "vision_models" in plan.selected_models_and_tools
    assert "gis_tools" in plan.selected_models_and_tools


# -----------------------------------------------------------------------------
# 2. Image Search Query
# -----------------------------------------------------------------------------
def test_image_search_query_plan(planner):
    """
    Query: 'Search for Sentinel-2 satellite imagery of Mumbai from January 2024 with cloud cover < 10%'
    Must specify RemoteCLIP model for satellite image search & pyproj/GeoPandas.
    """
    understanding = QueryUnderstanding(
        what=WhatSchema(value="satellite imagery search", provided_by_user=True),
        where=WhereSchema(value="Mumbai", provided_by_user=True),
        when=WhenSchema(value="January 2024", provided_by_user=True),
        target=TargetSchema(values=["Sentinel-2 satellite imagery"], provided_by_user=True),
        measurement=MeasurementSchema(value="cloud cover < 10%", provided_by_user=True),
        output_format=OutputFormatSchema(values=["image_metadata", "GeoTIFF"], provided_by_user=True)
    )

    plan = planner.generate_plan(understanding)

    assert plan.is_valid is True
    assert plan.where == "Mumbai"
    assert plan.when == "January 2024"

    # Data retrieval must contain Optical Imagery
    optical_step = next(s for s in plan.data_retrieval if s.category == "Optical Imagery")
    assert optical_step.requirement_level == "required"
    assert optical_step.registered_source_api == "STAC_EarthSearch_Sentinel2"

    # Visual detection must select RemoteCLIP for satellite image search
    visual_models = [s.model for s in plan.visual_search]
    assert "remote_clip" in visual_models

    remote_clip_step = next(s for s in plan.visual_search if s.model == "remote_clip")
    assert remote_clip_step.task == "vision_language_retrieval"

    # Tools should include pyproj or GeoPandas
    tools_used = [t for s in plan.spatial_analysis for t in s.tools_used]
    assert "pyproj" in tools_used or "GeoPandas" in tools_used


# -----------------------------------------------------------------------------
# 3. Image Segmentation Query
# -----------------------------------------------------------------------------
def test_image_segmentation_query_plan(planner):
    """
    Query: 'Segment urban green spaces in Delhi using high-res satellite imagery'
    Must select SegFormer model for semantic land cover segmentation.
    """
    understanding = QueryUnderstanding(
        what=WhatSchema(value="urban green space segmentation", provided_by_user=True),
        where=WhereSchema(value="Delhi", provided_by_user=True),
        when=WhenSchema(value="Latest available", provided_by_user=False),
        target=TargetSchema(values=["urban green spaces"], provided_by_user=True),
        measurement=MeasurementSchema(value="segmentation of green spaces", provided_by_user=True),
        output_format=OutputFormatSchema(values=["GeoJSON", "interactive map"], provided_by_user=True)
    )

    plan = planner.generate_plan(understanding)

    assert plan.is_valid is True
    assert plan.where == "Delhi"

    # Visual detection must select SegFormer or SAM 2 for segmentation
    visual_models = [s.model for s in plan.visual_search]
    assert "segformer" in visual_models or "sam_2" in visual_models

    seg_step = next(s for s in plan.visual_search if s.model in ["segformer", "sam_2"])
    assert seg_step.task in ["semantic_segmentation", "instance_segmentation"]

    # Spatial analysis operation
    spatial_ops = [s.operation for s in plan.spatial_analysis]
    assert "raster_to_vector" in spatial_ops or "distance_buffer_filter" in spatial_ops


# -----------------------------------------------------------------------------
# 4. Two-Date Change Detection Query
# -----------------------------------------------------------------------------
def test_two_date_change_detection_query_plan(planner):
    """
    Query: 'Detect urban expansion and building changes in Bangalore between 2020 and 2024'
    Must select ChangeFormer model for bi-temporal change detection.
    """
    understanding = QueryUnderstanding(
        what=WhatSchema(value="urban expansion and building change detection", provided_by_user=True),
        where=WhereSchema(value="Bangalore", provided_by_user=True),
        when=WhenSchema(value="2020 to 2024", provided_by_user=True),
        target=TargetSchema(values=["buildings", "urban expansion"], provided_by_user=True),
        measurement=MeasurementSchema(value="bi-temporal change between 2020 and 2024", provided_by_user=True),
        output_format=OutputFormatSchema(values=["change map", "GeoJSON", "summary statistics"], provided_by_user=True)
    )

    plan = planner.generate_plan(understanding)

    assert plan.is_valid is True
    assert plan.where == "Bangalore"
    assert plan.when == "2020 to 2024"

    # Visual detection must select ChangeFormer for bi-temporal change
    visual_models = [s.model for s in plan.visual_search]
    assert "changeformer" in visual_models

    change_step = next(s for s in plan.visual_search if s.model == "changeformer")
    assert change_step.task == "bi_temporal_change_detection"

    # Spatial analysis operation
    spatial_ops = [s.operation for s in plan.spatial_analysis]
    assert "change_detection_comparison" in spatial_ops or "distance_buffer_filter" in spatial_ops


# -----------------------------------------------------------------------------
# 5. Missing Data and Unsupported Operations
# -----------------------------------------------------------------------------
def test_missing_data_unsupported_query_plan(planner):
    """
    Query: 'Retrieve underwater sonar bathymetry data at 1cm resolution in Chennai'
    Must flag missing data in missing_data_flags.
    """
    understanding = QueryUnderstanding(
        what=WhatSchema(value="underwater bathymetry analysis", provided_by_user=True),
        where=WhereSchema(value="Chennai", provided_by_user=True),
        when=WhenSchema(value="Latest available", provided_by_user=False),
        target=TargetSchema(values=["underwater bathymetry sonar"], provided_by_user=True),
        measurement=MeasurementSchema(value="1cm resolution sonar mapping", provided_by_user=True),
        output_format=OutputFormatSchema(values=["bathymetric map"], provided_by_user=True)
    )

    plan = planner.generate_plan(understanding)

    assert plan.is_valid is True
    assert len(plan.missing_data_flags) > 0
    assert any("no registered source" in flag.lower() or "missing" in flag.lower() for flag in plan.missing_data_flags)


# -----------------------------------------------------------------------------
# 6. Multi-Turn Context and Missing OUTPUT Format
# -----------------------------------------------------------------------------
def test_multi_turn_missing_output_gating(checker, merger, planner):
    """
    Turn 1: 'Analyze solar potential in Jaipur' (Missing OUTPUT format) -> NEEDS_INFORMATION
    Turn 2: 'Show me an interactive map and GeoJSON' -> Merged state becomes READY -> Plan generated.
    """
    # Turn 1
    turn1_understanding = QueryUnderstanding(
        what=WhatSchema(value="solar potential analysis", confidence=1.0, provided_by_user=True),
        where=WhereSchema(value="Jaipur", confidence=1.0, provided_by_user=True),
        target=TargetSchema(values=["solar panels"], confidence=1.0, provided_by_user=True),
        measurement=MeasurementSchema(value="roof area and solar irradiance", confidence=1.0, provided_by_user=True),
        output_format=OutputFormatSchema(values=[], confidence=0.0, provided_by_user=False)
    )

    res1 = checker.check(turn1_understanding)
    assert res1.is_sufficient is False
    assert res1.status == "NEEDS_INFORMATION"
    assert "output_format" in res1.missing_information


    # Turn 2
    turn2_extraction = QueryUnderstanding(
        output_format=OutputFormatSchema(values=["interactive map", "GeoJSON"], provided_by_user=True)
    )

    merged = merger.merge(previous=turn1_understanding, current=turn2_extraction, user_message="Show me an interactive map and GeoJSON")

    res2 = checker.check(merged)
    assert res2.is_sufficient is True
    assert res2.status == "READY"

    # Generate Plan
    plan = planner.generate_plan(merged)
    assert plan.is_valid is True
    assert plan.where == "Jaipur"
    assert "interactive map" in plan.output_format
    assert "GeoJSON" in plan.output_format


# -----------------------------------------------------------------------------
# 7. Model and Tool Registry Tests
# -----------------------------------------------------------------------------
def test_model_and_tool_registry_lookups():
    models = list_registered_models()
    assert len(models) >= 7

    model_ids = [m.id for m in models]
    assert "grounding_dino" in model_ids
    assert "yolo_world" in model_ids
    assert "sam_2" in model_ids
    assert "segformer" in model_ids
    assert "prithvi" in model_ids
    assert "changeformer" in model_ids
    assert "remote_clip" in model_ids

    tools = list_registered_tools()
    assert len(tools) >= 4

    tool_ids = [t.id for t in tools]
    assert "geopandas" in tool_ids
    assert "shapely" in tool_ids
    assert "pyproj" in tool_ids
    assert "postgis" in tool_ids

    # Specific entry checks
    dino = get_registered_model("grounding_dino")
    assert dino is not None
    assert dino.name == "Grounding DINO"

    geopandas = get_registered_tool("geopandas")
    assert geopandas is not None
    assert geopandas.name == "GeoPandas"
