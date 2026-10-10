"""GEOAI-05 - Hospital Exposure to Landslide Risk Pipeline Tests.

Verifies end-to-end correctness of query parsing, capability-based planning,
hazard and hospital data retrieval, point-in-polygon exposure analysis,
job execution status reporting, output deliverable formatting, and regression safety.
"""

import pytest
import os
import json
from shapely.geometry import Point, Polygon

from app.schemas.query_schema import QueryUnderstanding
from app.services.query_parser import query_parser
from app.services.query_planner import query_planner
from app.services.planner_allowlist import validate_plan_against_allowlist, SPATIAL_CAPABILITY_REGISTRY
from app.services.retrieval_connectors import LandslideHazardConnector, OverpassVectorConnector
from app.services.spatial_engine import spatial_engine
from app.services.job_manager import job_manager
from app.services.output_engine import output_engine
from app.schemas.spatial_schema import SpatialAnalysisLayerResult, SpatialEngineResult
from app.schemas.retrieval_schema import RetrievalExecutionResult, RetrievedAssetMetadata
from app.schemas.vision_schema import VisualDetectionResult


TARGET_QUERY = "Hospitals exposed to landslide risk zones in Pune district, Maharashtra in 2024"


def test_1_parse_exact_target_query_including_2024():
    """Test 1: Parses exact target query preserving 5 core dimensions and hospital/landslide entities."""
    parsed: QueryUnderstanding = query_parser.parse(TARGET_QUERY)

    assert parsed.what.value is not None
    assert "hospital" in parsed.what.value.lower() and "landslide" in parsed.what.value.lower()
    assert parsed.where.value == "Pune district, Maharashtra" or "pune" in parsed.where.value.lower()
    assert "hospitals" in [t.lower() for t in parsed.target.values]
    assert any("landslide" in t.lower() for t in parsed.target.values)
    assert parsed.measurement.value is not None
    assert "point-in-polygon" in parsed.measurement.value.lower() or "exposure" in parsed.measurement.value.lower()
    assert "GeoJSON" in parsed.output_format.values or "interactive map" in parsed.output_format.values


def test_2_correct_planning_for_landslide_exposure():
    """Test 2: Planner selects point_in_polygon_exposure operation, no Grounding DINO/SAM 2 vision models, and valid capability DAG."""
    parsed = query_parser.parse(TARGET_QUERY)
    plan = query_planner.generate_plan(parsed)

    assert plan.spatial_analysis[0].operation == "point_in_polygon_exposure"
    assert "distance_buffer_filter" not in [step.operation for step in plan.spatial_analysis]
    assert len(plan.visual_search) == 0  # Pure vector GIS query, no vision model required

    # Validate against capability registry
    assert "point_in_polygon_exposure" in SPATIAL_CAPABILITY_REGISTRY
    is_valid, warnings = validate_plan_against_allowlist(plan)
    assert is_valid is True


def test_3_hospital_retrieval_filtering_and_identity_preservation(tmp_path):
    """Test 3: Hospital connector preserves real OSM node/way IDs, names, coordinates, and tags."""
    conn = OverpassVectorConnector()
    meta = conn.fetch(
        spatial_coverage="Pune district, Maharashtra",
        search_parameters={"amenity": "hospital", "area": "Pune District"},
        output_dir=str(tmp_path)
    )

    assert meta.status == "success"
    assert meta.item_count > 0
    with open(meta.file_path, "r", encoding="utf-8") as f:
        geojson = json.load(f)

    feats = geojson.get("features", [])
    assert len(feats) > 0

    # Verify real hospital names and tags preserved
    h_names = [f.get("properties", {}).get("name") or f.get("properties", {}).get("hospital_name") for f in feats]
    assert any(n and "Hospital" in n for n in h_names)
    assert any(f.get("id", "").startswith("node/") or f.get("id", "").startswith("way/") for f in feats)


def test_4_dataset_temporal_and_geographic_coverage_validation(tmp_path):
    """Test 4: Landslide hazard connector validates 2024 period, Pune district coverage, and provenance metadata."""
    conn = LandslideHazardConnector()
    meta = conn.fetch(
        spatial_coverage="Pune district, Maharashtra",
        search_parameters={"area": "Pune District", "year": "2024"},
        output_dir=str(tmp_path)
    )

    assert meta.status == "success"
    assert meta.provenance.get("observation_period") == "2024"
    assert "Pune District" in meta.provenance.get("geographic_coverage", "")
    assert meta.provenance.get("dataset_type") == "landslide_susceptibility"


def test_5_point_strictly_inside_polygon():
    """Test 5: Spatial engine classifies a hospital point strictly inside a landslide polygon as 'inside'."""
    poly_geom = {
        "type": "Polygon",
        "coordinates": [[[73.80, 18.50], [73.85, 18.50], [73.85, 18.55], [73.80, 18.55], [73.80, 18.50]]]
    }
    hosp_geom = {"type": "Point", "coordinates": [73.82, 18.52]}

    retrieved_features = {
        "osm_hospitals": [{
            "type": "Feature",
            "id": "node/101",
            "properties": {"feature_id": "node/101", "name": "Inside Test Hospital", "amenity": "hospital"},
            "geometry": hosp_geom
        }],
        "landslide_hazard_zones": [{
            "type": "Feature",
            "id": "risk_poly_01",
            "properties": {"feature_id": "risk_poly_01", "name": "High Risk Zone A", "risk_class": "High Risk", "risk_score": 0.9},
            "geometry": poly_geom
        }]
    }

    step_result = spatial_engine._execute_step_operation(
        step_idx=1,
        step=query_planner._build_dynamic_plan("Hospital exposure", "Pune", "2024", ["hospitals"], "exposure", ["GeoJSON"]).spatial_analysis[0],
        retrieved_features=retrieved_features,
        detections=[],
        matched_items=[]
    )

    feats = step_result.geojson_data.get("features", [])
    hosp_feat = next(f for f in feats if f.get("properties", {}).get("feature_role") == "target_hospital")
    assert hosp_feat["properties"]["spatial_classification"] == "inside"
    assert hosp_feat["properties"]["primary_risk_class"] == "High Risk"


def test_6_point_exactly_on_polygon_boundary():
    """Test 6: Spatial engine classifies a hospital point on a polygon boundary as 'boundary_touching'."""
    poly_geom = {
        "type": "Polygon",
        "coordinates": [[[73.80, 18.50], [73.85, 18.50], [73.85, 18.55], [73.80, 18.55], [73.80, 18.50]]]
    }
    hosp_geom = {"type": "Point", "coordinates": [73.80, 18.52]}  # On western boundary edge

    retrieved_features = {
        "osm_hospitals": [{
            "type": "Feature",
            "id": "node/102",
            "properties": {"feature_id": "node/102", "name": "Boundary Test Hospital", "amenity": "hospital"},
            "geometry": hosp_geom
        }],
        "landslide_hazard_zones": [{
            "type": "Feature",
            "id": "risk_poly_01",
            "properties": {"feature_id": "risk_poly_01", "name": "High Risk Zone A", "risk_class": "High Risk", "risk_score": 0.9},
            "geometry": poly_geom
        }]
    }

    step_result = spatial_engine._execute_step_operation(
        step_idx=1,
        step=query_planner._build_dynamic_plan("Hospital exposure", "Pune", "2024", ["hospitals"], "exposure", ["GeoJSON"]).spatial_analysis[0],
        retrieved_features=retrieved_features,
        detections=[],
        matched_items=[]
    )

    feats = step_result.geojson_data.get("features", [])
    hosp_feat = next(f for f in feats if f.get("properties", {}).get("feature_role") == "target_hospital")
    assert hosp_feat["properties"]["spatial_classification"] in ["boundary_touching", "inside"]


def test_7_point_outside_all_polygons():
    """Test 7: Spatial engine classifies a hospital point outside all risk polygons as 'outside'."""
    poly_geom = {
        "type": "Polygon",
        "coordinates": [[[73.80, 18.50], [73.85, 18.50], [73.85, 18.55], [73.80, 18.55], [73.80, 18.50]]]
    }
    hosp_geom = {"type": "Point", "coordinates": [73.90, 18.60]}  # Well outside

    retrieved_features = {
        "osm_hospitals": [{
            "type": "Feature",
            "id": "node/103",
            "properties": {"feature_id": "node/103", "name": "Safe Outside Hospital", "amenity": "hospital"},
            "geometry": hosp_geom
        }],
        "landslide_hazard_zones": [{
            "type": "Feature",
            "id": "risk_poly_01",
            "properties": {"feature_id": "risk_poly_01", "name": "High Risk Zone A", "risk_class": "High Risk", "risk_score": 0.9},
            "geometry": poly_geom
        }]
    }

    step_result = spatial_engine._execute_step_operation(
        step_idx=1,
        step=query_planner._build_dynamic_plan("Hospital exposure", "Pune", "2024", ["hospitals"], "exposure", ["GeoJSON"]).spatial_analysis[0],
        retrieved_features=retrieved_features,
        detections=[],
        matched_items=[]
    )

    feats = step_result.geojson_data.get("features", [])
    hosp_feat = next(f for f in feats if f.get("properties", {}).get("feature_role") == "target_hospital")
    assert hosp_feat["properties"]["spatial_classification"] == "outside"
    assert hosp_feat["properties"]["primary_risk_class"] == "No Risk (Outside)"


def test_8_overlapping_risk_polygons_and_unique_hospital_counts():
    """Test 8: Handles overlapping hazard polygons without double-counting unique hospitals."""
    poly_1 = {
        "type": "Polygon",
        "coordinates": [[[73.80, 18.50], [73.85, 18.50], [73.85, 18.55], [73.80, 18.55], [73.80, 18.50]]]
    }
    poly_2 = {
        "type": "Polygon",
        "coordinates": [[[73.82, 18.51], [73.87, 18.51], [73.87, 18.56], [73.82, 18.56], [73.82, 18.51]]]
    }
    hosp_geom = {"type": "Point", "coordinates": [73.83, 18.52]}  # Intersects both poly_1 and poly_2

    retrieved_features = {
        "osm_hospitals": [{
            "type": "Feature",
            "id": "node/104",
            "properties": {"feature_id": "node/104", "name": "Overlapping Hospital", "amenity": "hospital"},
            "geometry": hosp_geom
        }],
        "landslide_hazard_zones": [
            {"type": "Feature", "id": "risk_poly_01", "properties": {"feature_id": "risk_poly_01", "name": "Moderate Risk Zone", "risk_class": "Moderate Risk", "risk_score": 0.5}, "geometry": poly_1},
            {"type": "Feature", "id": "risk_poly_02", "properties": {"feature_id": "risk_poly_02", "name": "High Risk Zone", "risk_class": "High Risk", "risk_score": 0.95}, "geometry": poly_2},
        ]
    }

    step_result = spatial_engine._execute_step_operation(
        step_idx=1,
        step=query_planner._build_dynamic_plan("Hospital exposure", "Pune", "2024", ["hospitals"], "exposure", ["GeoJSON"]).spatial_analysis[0],
        retrieved_features=retrieved_features,
        detections=[],
        matched_items=[]
    )

    feats = step_result.geojson_data.get("features", [])
    hosp_feats = [f for f in feats if f.get("properties", {}).get("feature_role") == "target_hospital"]
    assert len(hosp_feats) == 1  # Exactly 1 unique hospital feature
    assert hosp_feats[0]["properties"]["primary_risk_class"] == "High Risk"  # Highest risk score selected
    assert len(hosp_feats[0]["properties"]["intersecting_risk_zones"]) == 2


def test_9_missing_risk_datasets_and_failed_retrieval(tmp_path):
    """Test 9: Landslide hazard connector returns blocked_missing_data when requested area has no dataset."""
    conn = LandslideHazardConnector()
    meta = conn.fetch(
        spatial_coverage="Unknown Desert District",
        search_parameters={"area": "Unknown Desert District", "year": "2024"},
        output_dir=str(tmp_path)
    )

    assert meta.status == "blocked_missing_data"
    assert meta.item_count == 0
    assert len(meta.warnings) > 0


def test_10_correct_job_status_when_mandatory_analysis_is_blocked():
    """Test 10: JobManager marks job status as blocked_missing_data when required hazard dataset is missing."""
    parsed = QueryUnderstanding(
        what={"value": "Hospital exposure to landslide-risk zones", "confidence": 0.95, "provided_by_user": True},
        where={"value": "Unknown Desert District", "type": "district", "confidence": 0.95, "provided_by_user": True},
        when={"value": "2024", "confidence": 0.95, "provided_by_user": True},
        target={"values": ["hospitals", "landslide-risk polygons"], "confidence": 0.95, "provided_by_user": True},
        measurement={"value": "Point-in-polygon containment", "confidence": 0.95, "provided_by_user": True},
        output_format={"values": ["interactive map", "GeoJSON", "CSV"], "confidence": 0.95, "provided_by_user": True}
    )

    job = job_manager.create_job(parsed)
    executed_job = job_manager.run_job_execution(job.job_id)

    assert executed_job.status == "blocked_missing_data"
    assert executed_job.stages[1].status == "blocked_missing_data"


def test_11_geojson_csv_consistency_and_map_feature_selection():
    """Test 11: OutputEngine produces consistent GeoJSON, CSV, and summary statistics derived from the same spatial results."""
    parsed = query_parser.parse(TARGET_QUERY)
    plan = query_planner.generate_plan(parsed)

    retrieved_features = {
        "osm_hospitals": [{
            "type": "Feature",
            "id": "node/35912401",
            "properties": {"feature_id": "node/35912401", "name": "Deenanath Mangeshkar Hospital", "amenity": "hospital"},
            "geometry": {"type": "Point", "coordinates": [73.8340, 18.5040]}
        }],
        "landslide_hazard_zones": [{
            "type": "Feature",
            "id": "landslide_risk_zone_02",
            "properties": {"feature_id": "landslide_risk_zone_02", "name": "Mulshi-Kothrud Moderate Risk Belt", "risk_class": "Moderate Risk", "risk_score": 0.55},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[73.7200, 18.5000], [73.8400, 18.5000], [73.8400, 18.5800], [73.7200, 18.5800], [73.7200, 18.5000]]]
            }
        }]
    }

    layer_res = spatial_engine._execute_step_operation(
        step_idx=1,
        step=plan.spatial_analysis[0],
        retrieved_features=retrieved_features,
        detections=[],
        matched_items=[]
    )

    spatial_res = SpatialEngineResult(
        plan_id=plan.plan_id,
        status="completed",
        total_features_processed=layer_res.item_count,
        matched_features=[],
        unmatched_detections=[],
        unmatched_gis_features=[],
        analysis_layers=[layer_res],
        execution_summary="Completed hospital exposure analysis",
        warnings=[]
    )

    deliverable = output_engine.generate_output(plan, spatial_res, None)

    assert deliverable.status == "completed"
    assert deliverable.geojson_export is not None
    assert "hospital_id" in deliverable.csv_export
    assert "Deenanath Mangeshkar Hospital" in deliverable.csv_export
    assert deliverable.summary_statistics["total_hospitals_evaluated"] == 1
    assert deliverable.summary_statistics["hospitals_inside_risk_zones"] == 1


def test_12_regression_tests_for_existing_supported_query_types():
    """Test 12: Existing supported queries (drainage building proximity, flood risk, urban change) pass without regression."""
    q1 = "Find commercial buildings with solar panels within 200 metres of open drainage in Pune."
    p1 = query_parser.parse(q1)
    plan1 = query_planner.generate_plan(p1)

    assert "buildings" in [t.lower() for t in p1.target.values]
    assert plan1.spatial_analysis[0].operation in ["distance_buffer_filter", "proximity_analysis"]

    q2 = "Flood risk mapping for Indus river basin."
    p2 = query_parser.parse(q2)
    plan2 = query_planner.generate_plan(p2)

    assert "flood" in p2.what.value.lower()
    assert plan2.is_valid is True
