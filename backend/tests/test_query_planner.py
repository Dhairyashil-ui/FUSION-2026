import sys
import os
import json
import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import Base
import app.models
from app.models.project import Project
from app.schemas.query_schema import QueryUnderstanding
from app.schemas.planner_schema import QueryPlan
from app.services.query_planner import query_planner
from app.services.planner_allowlist import validate_plan_against_allowlist
from app.services.conversation_manager import conversation_manager

TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
Base.metadata.create_all(bind=test_engine)


def test_generic_query_plans_generation():
    """Validates that QueryPlanner generates structured 5-section plans for multiple distinct queries."""
    queries = [
        {
            "what": "infrastructure discovery",
            "where": "Pune",
            "target": ["commercial buildings", "solar panels", "open drainage"],
            "measurement": "filter by distance to drainage using a 200 m threshold",
            "output_format": ["interactive map", "GeoJSON"]
        },
        {
            "what": "wildfire damage assessment",
            "where": "Maui, Hawaii",
            "target": ["structures", "vegetation"],
            "measurement": "delta NBR burn severity index threshold > 0.4",
            "output_format": ["burn severity map", "report"]
        },
        {
            "what": "vehicle anomaly detection",
            "where": "Strait of Malacca",
            "target": ["vessels", "restricted corridors"],
            "measurement": "proximity distance < 100m from checkpoint",
            "output_format": ["alerts", "GeoJSON"]
        }
    ]

    for q in queries:
        understanding = QueryUnderstanding(
            what={"value": q["what"], "confidence": 0.95, "provided_by_user": True},
            where={"value": q["where"], "type": "city_or_named_area", "confidence": 0.99, "provided_by_user": True},
            target={"values": q["target"], "confidence": 0.98, "provided_by_user": True},
            measurement={"value": q["measurement"], "confidence": 0.95, "provided_by_user": True},
            output_format={"values": q["output_format"], "confidence": 0.95, "provided_by_user": True}
        )

        plan = query_planner.generate_plan(understanding)

        assert isinstance(plan, QueryPlan)
        assert plan.what == q["what"]
        assert plan.where == q["where"]
        assert plan.target == q["target"]
        assert len(plan.data_retrieval) >= 2
        assert len(plan.visual_search) >= 1
        assert len(plan.spatial_analysis) >= 1
        assert len(plan.execution_graph) >= 3
        assert len(plan.output_specification.export_formats) >= 1
        assert plan.is_valid is True
        print(f"PASS Plan '{plan.plan_id}' generated for '{q['what']}' in '{q['where']}' ({len(plan.execution_graph)} graph steps)")


def test_allowlist_validation_and_fallback():
    """Validates that unauthorized datasets/models trigger safe fallbacks or validation flags."""
    raw_plan_dict = {
        "plan_id": "plan_test_allowlist",
        "what": "crop analysis",
        "where": "California",
        "target": ["citrus trees"],
        "measurement": "area threshold > 1 ha",
        "output_format": ["map"],
        "data_retrieval": [
            {
                "dataset_id": "custom_drone_imagery",  # Not directly in allowlist -> fallback to planet_scope
                "purpose": "High resolution drone scan",
                "spatial_coverage": "California",
                "resolution_requirements": "0.1m",
                "dependencies": []
            }
        ],
        "visual_search": [
            {
                "target_entity": "citrus trees",
                "model": "custom_cnn",  # Not directly in allowlist -> fallback to yolov8_geo
                "text_prompt": "detect citrus trees",
                "detection_type": "instance_segmentation",
                "confidence_threshold": 0.8,
                "output_format": "georeferenced_vector"
            }
        ],
        "spatial_analysis": [
            {
                "operation": "area_threshold_filter",
                "input_layers": ["custom_drone_imagery"],
                "parameters": {"min_hectares": 1},
                "output_layer": "filtered_crops"
            }
        ],
        "output_specification": {
            "result_fields": ["id", "geometry"],
            "geometry_types": ["Polygon"],
            "export_formats": ["map"],
            "visualization_style": "default"
        },
        "validation_and_fallback": {
            "data_checks": ["geometry_valid"],
            "crs_validation": "EPSG:4326",
            "confidence_checks": [],
            "fallback_strategy": None
        },
        "execution_graph": [
            {
                "step_id": "step_1",
                "step_name": "Area Filter",
                "step_type": "spatial_analysis",
                "operation": "area_threshold_filter",
                "inputs": [],
                "parameters": {},
                "expected_outputs": ["filtered_crops"],
                "failure_conditions": []
            }
        ]
    }

    plan = QueryPlan.model_validate(raw_plan_dict)
    is_valid, warnings = validate_plan_against_allowlist(plan)

    assert plan.data_retrieval[0].dataset_id == "planet_scope"
    assert plan.visual_search[0].model == "yolov8_geo"
    assert len(warnings) >= 2
    print(f"PASS Allowlist fallback verified: {warnings}")


def test_multi_turn_gating_no_plan_until_ready():
    """Validates that NO plan is returned while query is incomplete, and plan is generated when READY."""
    db = TestingSessionLocal()
    project = Project(name="Planner Gating Test")
    db.add(project)
    db.commit()
    db.refresh(project)

    # Turn 1: Incomplete (missing measurement and output_format)
    t1_llm = {
        "what": {"value": "infrastructure discovery", "confidence": 0.95, "provided_by_user": True},
        "where": {"value": "Pune", "type": "city_or_named_area", "confidence": 0.99, "provided_by_user": True},
        "target": {"values": ["commercial buildings", "solar panels"], "confidence": 0.98, "provided_by_user": True},
        "measurement": {"value": None, "confidence": 0.0, "provided_by_user": False},
        "output_format": {"values": [], "confidence": 0.0, "provided_by_user": False}
    }
    with patch("app.services.query_parser.query_parser.service.generate", return_value=json.dumps(t1_llm)):
        res1 = conversation_manager.process_query(project_id=project.id, user_query="Find solar panel buildings in Pune.", db=db)
        assert res1.sufficiency.status == "NEEDS_INFORMATION"
        assert res1.plan is None
        assert "What spatial relationships" in res1.assistant_response
        print("PASS Turn 1: Needs information, NO execution plan generated.")

    # Turn 2: Provide measurement, still missing output_format
    t2_llm = {
        "what": {"value": None, "confidence": 0.0, "provided_by_user": False},
        "where": {"value": None, "type": None, "confidence": 0.0, "provided_by_user": False},
        "target": {"values": ["open drainage"], "confidence": 0.95, "provided_by_user": True},
        "measurement": {"value": "within 200m of open drainage", "confidence": 0.95, "provided_by_user": True},
        "output_format": {"values": [], "confidence": 0.0, "provided_by_user": False}
    }
    with patch("app.services.query_parser.query_parser.service.generate", return_value=json.dumps(t2_llm)):
        res2 = conversation_manager.process_query(project_id=project.id, user_query="Within 200m of open drainage.", db=db)
        assert res2.sufficiency.status == "NEEDS_INFORMATION"
        assert res2.plan is None
        assert "What output format" in res2.assistant_response
        print("PASS Turn 2: Still missing output format, NO execution plan generated.")

    # Turn 3: Complete query (Provide output_format) -> READY -> Plan generated!
    t3_llm = {
        "what": {"value": None, "confidence": 0.0, "provided_by_user": False},
        "where": {"value": None, "type": None, "confidence": 0.0, "provided_by_user": False},
        "target": {"values": [], "confidence": 0.0, "provided_by_user": False},
        "measurement": {"value": None, "confidence": 0.0, "provided_by_user": False},
        "output_format": {"values": ["map", "GeoJSON"], "confidence": 0.95, "provided_by_user": True}
    }
    with patch("app.services.query_parser.query_parser.service.generate", return_value=json.dumps(t3_llm)):
        res3 = conversation_manager.process_query(project_id=project.id, user_query="Give me a map and GeoJSON.", db=db)
        assert res3.sufficiency.status == "READY"
        assert res3.plan is not None
        assert isinstance(res3.plan, QueryPlan)
        assert len(res3.plan.execution_graph) >= 3
        print(f"PASS Turn 3: READY! Plan '{res3.plan.plan_id}' generated successfully with {len(res3.plan.execution_graph)} execution steps!")

    db.close()


def test_pune_drainage_and_building_proximity_retrieval_plan():
    """
    Validates dynamic category evaluation for Pune drainage & building proximity query:
    - Requests Boundaries / AOI and Vector GIS Data (drainage & buildings).
    - Excludes Radar / SAR, Elevation / 3D, and Thematic Data.
    """
    understanding = QueryUnderstanding(
        what={"value": "open drainage channels and building proximity discovery", "confidence": 0.95, "provided_by_user": True},
        where={"value": "Pune", "type": "city_or_named_area", "confidence": 0.99, "provided_by_user": True},
        target={"values": ["open drainage channels", "buildings"], "confidence": 0.98, "provided_by_user": True},
        measurement={"value": "buildings within 200 metres of open drainage channels", "confidence": 0.95, "provided_by_user": True},
        output_format={"values": ["interactive map", "GeoJSON"], "confidence": 0.95, "provided_by_user": True}
    )

    plan = query_planner.generate_plan(understanding)

    assert isinstance(plan, QueryPlan)
    categories = [step.category for step in plan.data_retrieval if step.requirement_level == "required"]
    assert "Boundaries / AOI" in categories
    assert "Vector GIS Data" in categories

    # Radar/SAR, Elevation/3D, and Thematic should NOT be required
    unneeded_categories = [step.category for step in plan.data_retrieval if step.requirement_level == "required" and step.category in ["Radar / SAR", "Elevation / 3D", "Thematic / Temporal Data"]]
    assert len(unneeded_categories) == 0

    print(f"PASS Pune drainage & building proximity plan validated: Required categories = {set(categories)}")


def test_flood_mapping_retrieval_plan():
    """
    Validates dynamic category evaluation for Flood Inundation mapping:
    - Requires Radar / SAR (Sentinel-1) and Elevation / 3D (Copernicus DEM).
    """
    understanding = QueryUnderstanding(
        what={"value": "flood inundation mapping and water level monitoring", "confidence": 0.95, "provided_by_user": True},
        where={"value": "Indus River Basin", "type": "named_region", "confidence": 0.99, "provided_by_user": True},
        target={"values": ["flood extent", "submerged structures"], "confidence": 0.98, "provided_by_user": True},
        measurement={"value": "identify flooded regions and DEM slope inundation depth", "confidence": 0.95, "provided_by_user": True},
        output_format={"values": ["flood hazard map", "GeoJSON"], "confidence": 0.95, "provided_by_user": True}
    )

    plan = query_planner.generate_plan(understanding)

    req_categories = [step.category for step in plan.data_retrieval if step.requirement_level == "required"]
    req_apis = [step.registered_source_api for step in plan.data_retrieval if step.requirement_level == "required"]

    assert "Radar / SAR" in req_categories
    assert "Elevation / 3D" in req_categories
    assert "STAC_Sentinel1_SAR" in req_apis
    assert "Copernicus_DEM_API" in req_apis or "SRTM_DEM_30m" in req_apis

    print(f"PASS Flood mapping plan validated: Required APIs = {set(req_apis)}")


def test_building_height_3d_analysis_retrieval_plan():
    """
    Validates dynamic category evaluation for 3D Building Height analysis:
    - Requires Elevation / 3D (USGS 3DEP LiDAR / DEM) and Vector GIS Data (building footprints).
    """
    understanding = QueryUnderstanding(
        what={"value": "3D building height analysis and urban density", "confidence": 0.95, "provided_by_user": True},
        where={"value": "Downtown Manhattan", "type": "city_district", "confidence": 0.99, "provided_by_user": True},
        target={"values": ["building footprints", "height profile"], "confidence": 0.98, "provided_by_user": True},
        measurement={"value": "calculate 3D building height from point cloud LiDAR", "confidence": 0.95, "provided_by_user": True},
        output_format={"values": ["3D GeoJSON", "interactive 3D map"], "confidence": 0.95, "provided_by_user": True}
    )

    plan = query_planner.generate_plan(understanding)

    req_categories = [step.category for step in plan.data_retrieval if step.requirement_level == "required"]
    assert "Elevation / 3D" in req_categories
    assert "Vector GIS Data" in req_categories

    print(f"PASS 3D Building height plan validated: Required categories = {set(req_categories)}")


def test_missing_data_scenario_retrieval_plan():
    """
    Validates missing data reporting when unsupported datasets/APIs are requested:
    - Flags missing data in missing_data_flags without inventing fake APIs.
    """
    understanding = QueryUnderstanding(
        what={"value": "deep underwater sonar bathymetry map at 1cm resolution", "confidence": 0.95, "provided_by_user": True},
        where={"value": "Lake Tahoe", "type": "lake", "confidence": 0.99, "provided_by_user": True},
        target={"values": ["bathymetry sonar contours"], "confidence": 0.98, "provided_by_user": True},
        measurement={"value": "sonar depth soundings < 1cm resolution", "confidence": 0.95, "provided_by_user": True},
        output_format={"values": ["bathymetric map"], "confidence": 0.95, "provided_by_user": True}
    )

    plan = query_planner.generate_plan(understanding)

    assert len(plan.missing_data_flags) > 0
    assert any("Data Source Registry" in flag or "no registered source" in flag for flag in plan.missing_data_flags)

    print(f"PASS Missing data scenario validated: Flagged = {plan.missing_data_flags}")


if __name__ == "__main__":
    test_generic_query_plans_generation()
    test_allowlist_validation_and_fallback()
    test_multi_turn_gating_no_plan_until_ready()
    test_pune_drainage_and_building_proximity_retrieval_plan()
    test_flood_mapping_retrieval_plan()
    test_building_height_3d_analysis_retrieval_plan()
    test_missing_data_scenario_retrieval_plan()

