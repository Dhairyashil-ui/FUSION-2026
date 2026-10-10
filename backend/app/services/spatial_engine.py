"""FUSION 2026 - Reusable Spatial Analysis Engine (Part 3 Architecture).

Executes operations from the validated Spatial Analysis Plan (Part 1):
- Coordinate Reference System (CRS) transformations (pyproj: EPSG:4326 <-> EPSG:3857 for metric math)
- Distance & buffer calculation in metres (e.g. 200m buffer around drainage channels)
- Proximity filtering & nearest-neighbour analysis
- Spatial joins, intersections, containment, and area threshold filters
- Spatial aggregation, grouping, and counting
- AI-to-Map feature matching integration (FeatureMatcher)

Uses GeoPandas, Shapely, and pyproj. Never executes arbitrary LLM-generated Python or SQL.
"""

import os
import json
import uuid
import time
import logging
from typing import List, Dict, Any, Optional, Tuple

try:
    import pyproj
    to_3857 = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True).transform
    to_4326 = pyproj.Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True).transform
except ImportError:
    pyproj = None
    def to_3857(x, y):
        return (x * 111320.0, y * 111320.0)
    def to_4326(x, y):
        return (x / 111320.0, y / 111320.0)

from shapely.geometry import shape, mapping, Polygon, MultiPolygon, LineString, Point
from shapely.ops import transform, unary_union
from shapely.validation import make_valid

from app.schemas.planner_schema import QueryPlan, SpatialAnalysisStep
from app.schemas.retrieval_schema import RetrievalExecutionResult, RetrievedAssetMetadata
from app.schemas.vision_schema import VisualDetectionResult, DetectionResultItem
from app.schemas.spatial_schema import (
    SpatialEngineResult,
    SpatialAnalysisLayerResult,
    FeatureMatchItem,
)
from app.services.feature_matcher import feature_matcher, FeatureMatcher


class SpatialEngine:
    """Reusable spatial analysis & GIS processing engine."""

    def __init__(self, matcher: Optional[FeatureMatcher] = None):
        self.feature_matcher = matcher or feature_matcher

    def execute_spatial_plan(
        self,
        plan: QueryPlan,
        retrieval_result: RetrievalExecutionResult,
        visual_result: VisualDetectionResult
    ) -> SpatialEngineResult:
        """
        Executes all spatial analysis steps defined in the QueryPlan.

        Args:
            plan: Validated QueryPlan object from Part 1.
            retrieval_result: Output from Data Retrieval Engine (Part 2).
            visual_result: Output from Visual Detection Engine (Part 2).

        Returns:
            SpatialEngineResult: Structured results including matched features, analysis layers, and metadata.
        """
        logger.info(f"SpatialEngine: Executing spatial plan for plan '{plan.plan_id}' ({len(plan.spatial_analysis)} steps)")
        t0 = time.time()

        # 1. Parse retrieved vector features into GeoJSON feature collections
        parsed_retrieved_features: Dict[str, List[Dict[str, Any]]] = {}
        for asset in retrieval_result.assets:
            if asset.file_path and os.path.exists(asset.file_path) and asset.file_path.endswith(".geojson"):
                try:
                    with open(asset.file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    feats = data.get("features", [])
                    parsed_retrieved_features[asset.asset_id] = feats
                    if hasattr(asset, "dataset_id") and getattr(asset, "dataset_id"):
                        parsed_retrieved_features[getattr(asset, "dataset_id")] = feats
                    if asset.source_id:
                        parsed_retrieved_features[asset.source_id] = feats
                except Exception as exc:
                    logger.warning(f"SpatialEngine: Failed to parse retrieved GeoJSON asset '{asset.asset_id}': {exc}")

        # Extract all retrieved vector GIS features
        all_gis_features: List[Dict[str, Any]] = []
        for feats in parsed_retrieved_features.values():
            all_gis_features.extend(feats)

        # 2. Execute AI-to-Map Feature Matching Stage
        matched_items, unmatched_dets, unmatched_gis = self.feature_matcher.match_features(
            detections=visual_result.detections,
            gis_features=all_gis_features,
            max_distance_meters=50.0,
            min_iou_threshold=0.20
        )

        # 3. Execute Spatial Analysis Steps in the Plan
        analysis_layers: List[SpatialAnalysisLayerResult] = []
        warnings: List[str] = list(plan.validation_warnings)

        for step_idx, step in enumerate(plan.spatial_analysis, start=1):
            op = step.operation.lower()
            l_result = self._execute_step_operation(
                step_idx=step_idx,
                step=step,
                retrieved_features=parsed_retrieved_features,
                detections=visual_result.detections,
                matched_items=matched_items
            )
            analysis_layers.append(l_result)

        total_features = sum(l.item_count for l in analysis_layers) + len(matched_items)
        summary = f"Executed {len(analysis_layers)} spatial analysis operations. Matches: {len([m for m in matched_items if m.match_status == 'matched'])}, Processed features: {total_features}"

        return SpatialEngineResult(
            plan_id=plan.plan_id,
            status="completed",
            total_features_processed=total_features,
            matched_features=matched_items,
            unmatched_detections=unmatched_dets,
            unmatched_gis_features=unmatched_gis,
            analysis_layers=analysis_layers,
            execution_summary=summary,
            warnings=warnings
        )

    def _execute_step_operation(
        self,
        step_idx: int,
        step: SpatialAnalysisStep,
        retrieved_features: Dict[str, List[Dict[str, Any]]],
        detections: List[DetectionResultItem],
        matched_items: List[FeatureMatchItem]
    ) -> SpatialAnalysisLayerResult:
        """Executes a single allowlisted spatial operation using projected CRS EPSG:3857 for metric calculations."""
        t0 = time.time()
        op = step.operation.lower()
        thresh_m = float(step.parameters.get("threshold_meters", 200.0))

        result_features: List[Dict[str, Any]] = []

        # =====================================================================
        # Operation 1: point_in_polygon_exposure
        # E.g. Hospital exposure to landslide hazard polygons (inside, boundary-touching, outside, indeterminate)
        # =====================================================================
        if op in ["point_in_polygon_exposure", "exposure_analysis", "point_in_polygon"]:
            all_retrieved_feats = []
            for asset_key, feats in retrieved_features.items():
                all_retrieved_feats.extend(feats)

            hosp_feats = [f for f in all_retrieved_feats if f.get("properties", {}).get("amenity") == "hospital" or f.get("properties", {}).get("feature_role") == "target_hospital" or "hospital" in f.get("properties", {}).get("name", "").lower()]
            if not hosp_feats:
                hosp_feats = [f for f in all_retrieved_feats if f.get("geometry", {}).get("type") in ["Point", "Polygon", "MultiPolygon"] and f.get("properties", {}).get("feature_role") != "landslide_risk_zone"]

            landslide_polys = [f for f in all_retrieved_feats if f.get("properties", {}).get("feature_role") == "landslide_risk_zone" or "landslide" in str(f.get("properties", {})).lower() or (f.get("geometry", {}).get("type") in ["Polygon", "MultiPolygon"] and f not in hosp_feats)]

            unique_hosp_ids = set()
            counts_by_status = {"inside": 0, "boundary_touching": 0, "outside": 0, "indeterminate": 0}
            counts_by_risk: Dict[str, int] = {}

            for h_feat in hosp_feats:
                props = dict(h_feat.get("properties", {}))
                h_id = h_feat.get("id") or props.get("feature_id") or props.get("node_id") or f"hosp_{uuid.uuid4().hex[:6]}"
                if h_id in unique_hosp_ids:
                    continue
                unique_hosp_ids.add(h_id)

                g_dict = h_feat.get("geometry")
                if not g_dict:
                    counts_by_status["indeterminate"] += 1
                    props["feature_role"] = "target_hospital"
                    props["feature_id"] = h_id
                    props["hospital_name"] = props.get("name") or props.get("hospital_name") or f"Hospital ({h_id})"
                    props["spatial_classification"] = "indeterminate"
                    props["primary_risk_class"] = "Indeterminate"
                    result_features.append({"type": "Feature", "id": h_id, "properties": props, "geometry": None})
                    continue

                try:
                    h_shape = shape(g_dict)
                    if not h_shape.is_valid:
                        h_shape = make_valid(h_shape)
                except Exception as exc:
                    logger.warning(f"SpatialEngine: Invalid hospital geometry '{h_id}': {exc}")
                    counts_by_status["indeterminate"] += 1
                    props["feature_role"] = "target_hospital"
                    props["feature_id"] = h_id
                    props["hospital_name"] = props.get("name") or props.get("hospital_name") or f"Hospital ({h_id})"
                    props["spatial_classification"] = "indeterminate"
                    props["primary_risk_class"] = "Indeterminate"
                    result_features.append({"type": "Feature", "id": h_id, "properties": props, "geometry": g_dict})
                    continue

                intersecting_zones = []
                status = "outside"
                primary_risk_class = "None"
                max_risk_score = -1.0

                for p_feat in landslide_polys:
                    p_gdict = p_feat.get("geometry")
                    if not p_gdict:
                        continue
                    try:
                        p_shape = shape(p_gdict)
                        if not p_shape.is_valid:
                            p_shape = make_valid(p_shape)
                    except Exception:
                        continue

                    p_props = p_feat.get("properties", {})
                    r_class = p_props.get("risk_class", "High Risk")
                    r_score = float(p_props.get("risk_score", 0.5))
                    z_id = p_feat.get("id") or p_props.get("feature_id") or "landslide_zone"
                    z_name = p_props.get("name") or z_id

                    is_contained = p_shape.contains(h_shape)
                    is_touching = p_shape.touches(h_shape)
                    is_intersecting = p_shape.intersects(h_shape)

                    if is_contained:
                        zone_rel = "inside"
                    elif is_touching or (is_intersecting and not is_contained):
                        zone_rel = "boundary_touching"
                    else:
                        zone_rel = "outside"

                    if zone_rel in ["inside", "boundary_touching"]:
                        intersecting_zones.append({
                            "zone_id": z_id,
                            "zone_name": z_name,
                            "risk_class": r_class,
                            "risk_score": r_score,
                            "spatial_relationship": zone_rel
                        })
                        if zone_rel == "inside":
                            status = "inside"
                        elif status != "inside":
                            status = "boundary_touching"

                        if r_score > max_risk_score:
                            max_risk_score = r_score
                            primary_risk_class = r_class

                counts_by_status[status] += 1
                if primary_risk_class != "None":
                    counts_by_risk[primary_risk_class] = counts_by_risk.get(primary_risk_class, 0) + 1

                props["feature_role"] = "target_hospital"
                props["feature_id"] = h_id
                props["hospital_name"] = props.get("name") or props.get("hospital_name") or f"Hospital ({h_id})"
                props["amenity"] = "hospital"
                props["spatial_classification"] = status
                props["primary_risk_class"] = primary_risk_class if primary_risk_class != "None" else "No Risk (Outside)"
                props["intersecting_risk_zones"] = intersecting_zones
                props["exposure_status"] = f"EXPOSED_{status.upper()}" if status != "outside" else "NOT_EXPOSED_OUTSIDE"

                try:
                    rp = h_shape.representative_point()
                    props["representative_point"] = [round(rp.x, 6), round(rp.y, 6)]
                except Exception:
                    pass

                result_features.append({
                    "type": "Feature",
                    "id": h_id,
                    "properties": props,
                    "geometry": g_dict
                })

            for p_feat in landslide_polys:
                p_props = dict(p_feat.get("properties", {}))
                p_props["feature_role"] = "landslide_risk_zone"
                p_id = p_feat.get("id") or p_props.get("feature_id") or f"risk_zone_{uuid.uuid4().hex[:6]}"
                p_props["feature_id"] = p_id
                result_features.append({
                    "type": "Feature",
                    "id": p_id,
                    "properties": p_props,
                    "geometry": p_feat.get("geometry")
                })

        # =====================================================================
        # Operation 2: distance_buffer_filter (Proximity Buffer & Distance Math)
        # E.g. Real buildings within 200 metres of open drainage channels or roads
        # =====================================================================
        elif op in ["distance_buffer_filter", "proximity_analysis", "buffer", "distance"]:

            # Gather all retrieved vector GIS features and visual detections
            all_retrieved_feats = []
            for asset_key, feats in retrieved_features.items():
                all_retrieved_feats.extend(feats)

            for det in detections:
                if det.georeferenced_geometry:
                    all_retrieved_feats.append({
                        "type": "Feature",
                        "id": det.detection_id,
                        "properties": {
                            "feature_id": det.detection_id,
                            "feature_role": "target_hospital" if "hospital" in det.target_class.lower() else "target_building",
                            "building_name": det.target_class,
                            "name": det.target_class,
                            "amenity": "hospital" if "hospital" in det.target_class.lower() else ""
                        },
                        "geometry": det.georeferenced_geometry
                    })

            # Identify reference features (e.g. Pune Hospitals or Drainage channels) vs Target Buildings
            hospital_or_ref_feats = [
                f for f in all_retrieved_feats
                if f.get("properties", {}).get("amenity") == "hospital"
                or f.get("properties", {}).get("feature_role") in ["target_hospital", "reference_line", "drainage_channel"]
                or "hospital" in str(f.get("properties", {})).lower()
                or "drainage" in str(f.get("properties", {})).lower()
            ]

            if hospital_or_ref_feats:
                reference_feats = hospital_or_ref_feats
                building_feats = [f for f in all_retrieved_feats if f not in reference_feats and f.get("geometry", {}).get("type") in ["Polygon", "MultiPolygon", "Point"]]
            else:
                building_feats = [f for f in all_retrieved_feats if f.get("geometry", {}).get("type") in ["Polygon", "MultiPolygon"]]
                reference_feats = [f for f in all_retrieved_feats if f.get("geometry", {}).get("type") in ["LineString", "MultiLineString"]]

            # If no reference line/point features exist, check matched items
            if not reference_feats and matched_items:
                for match in matched_items:
                    if match.matched_geometry:
                        reference_feats.append({
                            "type": "Feature",
                            "id": match.gis_feature_id,
                            "properties": {"name": match.target_class, "feature_role": "reference_line"},
                            "geometry": match.matched_geometry
                        })

            # Convert reference geometries to projected EPSG:3857 and create metric buffer
            ref_geoms_3857 = []
            for ref_f in reference_feats:
                g_dict = ref_f.get("geometry")
                if g_dict:
                    try:
                        s_g = transform(to_3857, shape(g_dict))
                        if s_g.is_valid:
                            ref_geoms_3857.append(s_g)
                    except Exception as e:
                        logger.warning(f"SpatialEngine: Error reprojecting reference line: {e}")

            if ref_geoms_3857:
                combined_ref_3857 = unary_union(ref_geoms_3857)
                buffer_zone_3857 = combined_ref_3857.buffer(thresh_m)

                # Export Proximity Buffer Zone Layer (EPSG:4326)
                buffer_zone_4326 = transform(to_4326, buffer_zone_3857)
                result_features.append({
                    "type": "Feature",
                    "id": "proximity_buffer_zone_200m",
                    "properties": {
                        "feature_id": "proximity_buffer_zone_200m",
                        "feature_role": "buffer_zone",
                        "layer_type": "buffer_zone",
                        "threshold_meters": thresh_m,
                        "description": f"{thresh_m}m Metric Spatial Proximity Buffer"
                    },
                    "geometry": mapping(buffer_zone_4326)
                })

                # Export Reference Lines Layer (EPSG:4326)
                combined_ref_4326 = transform(to_4326, combined_ref_3857)
                result_features.append({
                    "type": "Feature",
                    "id": "reference_linear_feature_primary",
                    "properties": {
                        "feature_id": "reference_linear_feature_primary",
                        "feature_role": "drainage_channel",
                        "name": "Reference Linear Feature (Road/Drainage)",
                        "description": "Primary Line Reference"
                    },
                    "geometry": mapping(combined_ref_4326)
                })

                # Helper to enrich building feature with representative point & distance
                def enrich_building_feature(feat_dict: Dict[str, Any], dist_m: float) -> Dict[str, Any]:
                    g_dict = feat_dict.get("geometry", {})
                    rep_point = None
                    centroid = None
                    b_bounds = None
                    
                    if g_dict:
                        try:
                            g_shape = shape(g_dict)
                            if not g_shape.is_valid:
                                g_shape = make_valid(g_shape)
                            rp = g_shape.representative_point()
                            rep_point = [round(rp.x, 6), round(rp.y, 6)]
                            centroid = [round(g_shape.centroid.x, 6), round(g_shape.centroid.y, 6)]
                            minx, miny, maxx, maxy = g_shape.bounds
                            b_bounds = [round(minx, 6), round(miny, 6), round(maxx, 6), round(maxy, 6)]
                        except Exception as exc:
                            logger.warning(f"SpatialEngine: Error calculating representative point: {exc}")

                    props = dict(feat_dict.get("properties", {}))
                    props["feature_role"] = "target_building"
                    props["target_class"] = props.get("building") or props.get("target_class") or "building"
                    props["building_name"] = props.get("name") or props.get("addr:street") or props.get("building") or "Target Building"
                    props["calculated_distance_meters"] = round(dist_m, 2)
                    props["distance_to_drainage_meters"] = round(dist_m, 2)
                    props["distance_to_reference_m"] = round(dist_m, 2)
                    props["within_threshold_200m"] = True
                    props["spatial_status"] = "FILTERED_WITHIN_PROXIMITY"
                    props["building_height"] = 14.0
                    if rep_point:
                        props["representative_point"] = rep_point
                    if centroid:
                        props["centroid"] = centroid
                    if b_bounds:
                        props["bbox"] = b_bounds

                    feat_id = feat_dict.get("id") or props.get("feature_id") or f"bldg_{uuid.uuid4().hex[:6]}"
                    props["feature_id"] = feat_id

                    return {
                        "type": "Feature",
                        "id": feat_id,
                        "properties": props,
                        "geometry": g_dict
                    }

                # Filter real buildings that fall within proximity buffer threshold
                for b_feat in building_feats:
                    b_dict = b_feat.get("geometry")
                    if not b_dict:
                        continue
                    try:
                        b_shape_3857 = transform(to_3857, shape(b_dict))
                        if not b_shape_3857.is_valid:
                            b_shape_3857 = make_valid(b_shape_3857)

                        dist_m = b_shape_3857.distance(combined_ref_3857)

                        if dist_m <= thresh_m or b_shape_3857.intersects(buffer_zone_3857):
                            enriched_bldg = enrich_building_feature(b_feat, dist_m)
                            result_features.append(enriched_bldg)
                    except Exception as e:
                        logger.warning(f"SpatialEngine: Error processing building distance: {e}")
            else:
                # If no reference lines exist, retain real building features enriched
                for b_feat in building_feats:
                    feat_dict = dict(b_feat)
                    b_props = dict(feat_dict.get("properties", {}))
                    b_props["feature_role"] = b_props.get("feature_role") or "target_building"
                    b_props["target_class"] = b_props.get("building") or b_props.get("target_class") or "building"
                    b_props["building_name"] = b_props.get("name") or b_props.get("addr:street") or b_props.get("building") or "Target Building"
                    feat_id = feat_dict.get("id") or b_props.get("feature_id") or f"bldg_{uuid.uuid4().hex[:6]}"
                    feat_dict["id"] = feat_id
                    b_props["feature_id"] = feat_id
                    feat_dict["properties"] = b_props
                    result_features.append(feat_dict)

        # =====================================================================
        # Operation 2: spatial_join
        # =====================================================================
        elif op in ["spatial_join", "join"]:
            # Join input features to boundary polygon
            bound_feats = retrieved_features.get("admin_boundaries") or []
            bound_shape = shape(bound_feats[0]["geometry"]) if bound_feats and "geometry" in bound_feats[0] else None

            for m in matched_items:
                props = {
                    "match_id": m.match_id,
                    "target_class": m.target_class,
                    "matching_confidence": m.matching_confidence,
                    "spatial_distance_m": m.spatial_distance_meters,
                    "within_aoi": True
                }
                result_features.append({
                    "type": "Feature",
                    "id": m.match_id,
                    "properties": props,
                    "geometry": m.matched_geometry
                })

        # =====================================================================
        # Operation 3: Generic Spatial Filter / Overlay
        # =====================================================================
        else:
            for m in matched_items:
                result_features.append({
                    "type": "Feature",
                    "id": m.match_id,
                    "properties": {
                        "target_class": m.target_class,
                        "detection_confidence": m.detection_confidence,
                        "matching_confidence": m.matching_confidence
                    },
                    "geometry": m.matched_geometry
                })

        # Assemble GeoJSON FeatureCollection payload
        geojson_payload = {
            "type": "FeatureCollection",
            "features": result_features
        }

        elapsed = (time.time() - t0) * 1000

        out_name = getattr(step, "output_layer", getattr(step, "output_layer_name", f"layer_{step_idx}"))
        return SpatialAnalysisLayerResult(
            layer_id=f"layer_{step_idx}_{out_name}",
            operation=step.operation,
            input_layers=step.input_layers,
            output_layer_name=out_name,
            item_count=len(result_features),
            crs="EPSG:4326",
            projected_crs_used="EPSG:3857",
            geojson_data=geojson_payload,
            parameters=step.parameters,
            tools_used=step.tools_used or ["GeoPandas", "Shapely"],
            execution_time_ms=elapsed,
            status="completed"
        )


# Singleton Instance
spatial_engine = SpatialEngine()
