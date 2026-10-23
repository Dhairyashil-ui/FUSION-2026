"""FUSION 2026 - Final Output and Visualization Engine (Part 3 Architecture).

Consumes the Output and Visualization Plan from Part 1 and spatial analysis results.
Generates user-requested deliverables:
- Validated GeoJSON FeatureCollection for vector GIS results
- Formatted CSV tabular export for summary attributes and metrics
- Interactive map layer specifications with styles, legends, and popups
- Summary statistics and result tables
"""

import json
import csv
import io
import logging
from typing import Dict, Any, List, Optional

from app.schemas.planner_schema import QueryPlan
from app.schemas.spatial_schema import (
    SpatialEngineResult,
    FinalValidationReport,
    FinalOutputDeliverable,
)

logger = logging.getLogger(__name__)


class OutputEngine:
    """Generates final GeoJSON, CSV, and interactive map layer deliverables."""

    def generate_output(
        self,
        plan: QueryPlan,
        spatial_result: SpatialEngineResult,
        validation_report: FinalValidationReport
    ) -> FinalOutputDeliverable:
        """
        Generates deliverables matching the user's requested output formats.

        Args:
            plan: QueryPlan Pydantic model.
            spatial_result: SpatialEngineResult output.
            validation_report: FinalValidationReport.

        Returns:
            FinalOutputDeliverable: Complete deliverable payload.
        """
        logger.info(f"OutputEngine: Generating deliverables for plan '{plan.plan_id}'")

        if validation_report is None:
            validation_report = FinalValidationReport()

        # 1. Assemble Unified GeoJSON FeatureCollection
        all_features: List[Dict[str, Any]] = []

        # Add matched features to GeoJSON export
        for m in spatial_result.matched_features:
            if m.matched_geometry:
                rep_pt = None
                try:
                    s_g = shape(m.matched_geometry)
                    if not s_g.is_valid:
                        s_g = make_valid(s_g)
                    rp = s_g.representative_point()
                    rep_pt = [round(rp.x, 6), round(rp.y, 6)]
                except Exception:
                    pass

                all_features.append({
                    "type": "Feature",
                    "id": m.match_id,
                    "properties": {
                        "feature_id": m.match_id,
                        "feature_role": "target_building",
                        "building_name": m.original_name if m.original_name else f"Matched {m.target_class.title()} ({m.gis_feature_id})",
                        "detection_id": m.detection_id,
                        "gis_feature_id": m.gis_feature_id,
                        "target_class": m.target_class,
                        "matching_method": m.matching_method,
                        "spatial_distance_meters": m.spatial_distance_meters,
                        "detection_confidence": m.detection_confidence,
                        "matching_confidence": m.matching_confidence,
                        "match_status": m.match_status,
                        "provenance": m.provenance,
                        "representative_point": rep_pt
                    },
                    "geometry": m.matched_geometry
                })

        # Add spatial analysis layer features to GeoJSON export
        for layer in spatial_result.analysis_layers:
            layer_feats = layer.geojson_data.get("features", [])
            for feat in layer_feats:
                feat_copy = dict(feat)
                props_copy = dict(feat_copy.get("properties", {}))
                feat_id = feat_copy.get("id") or props_copy.get("feature_id") or props_copy.get("gis_feature_id")
                if feat_id:
                    feat_copy["id"] = feat_id
                    props_copy["feature_id"] = feat_id
                feat_copy["properties"] = props_copy
                all_features.append(feat_copy)

        geojson_export = {
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
            "features": all_features
        }

        # Check if deliverable contains hospital exposure analysis features
        hospital_features = [f for f in all_features if f.get("properties", {}).get("feature_role") == "target_hospital"]
        is_hospital_exposure = len(hospital_features) > 0 or "hospital" in plan.what.lower()

        # 2. Assemble CSV Tabular Export
        csv_buffer = io.StringIO()
        csv_writer = csv.writer(csv_buffer)

        if is_hospital_exposure and hospital_features:
            csv_writer.writerow([
                "hospital_id", "hospital_name", "spatial_classification",
                "primary_risk_class", "intersecting_zones_count", "latitude", "longitude", "provenance_source"
            ])
            for h in hospital_features:
                props = h.get("properties", {})
                rp = props.get("representative_point") or [None, None]
                csv_writer.writerow([
                    props.get("feature_id") or h.get("id"),
                    props.get("hospital_name") or props.get("name"),
                    props.get("spatial_classification", "unknown"),
                    props.get("primary_risk_class", "None"),
                    len(props.get("intersecting_risk_zones", [])),
                    rp[1] if rp and len(rp) == 2 else "N/A",
                    rp[0] if rp and len(rp) == 2 else "N/A",
                    props.get("amenity") or "OpenStreetMap"
                ])
        else:
            target_buildings = [
                f for f in all_features
                if f.get("properties", {}).get("feature_role") in ["target_building", "target_hospital"]
                or f.get("properties", {}).get("building_name")
            ]
            if target_buildings:
                csv_writer.writerow([
                    "feature_id", "building_name", "target_class", "calculated_distance_meters",
                    "nearest_neighbor", "detection_confidence", "latitude", "longitude"
                ])
                for b in target_buildings:
                    props = b.get("properties", {})
                    rp = props.get("representative_point") or [None, None]
                    if (not rp or rp[0] is None) and b.get("geometry", {}).get("type") == "Point":
                        coords = b.get("geometry", {}).get("coordinates", [])
                        if len(coords) >= 2:
                            rp = [coords[0], coords[1]]
                    csv_writer.writerow([
                        props.get("feature_id") or b.get("id"),
                        props.get("building_name") or props.get("name"),
                        props.get("target_class") or "building",
                        props.get("calculated_distance_meters", "N/A"),
                        props.get("nearest_building_name", "N/A"),
                        props.get("detection_confidence", 1.0),
                        rp[1] if rp and len(rp) == 2 else "N/A",
                        rp[0] if rp and len(rp) == 2 else "N/A",
                    ])
            else:
                csv_writer.writerow([
                    "feature_id", "target_class", "matching_method",
                    "distance_meters", "detection_confidence", "matching_confidence", "match_status"
                ])
                for m in spatial_result.matched_features:
                    csv_writer.writerow([
                        m.match_id,
                        m.target_class,
                        m.matching_method,
                        m.spatial_distance_meters if m.spatial_distance_meters is not None else "N/A",
                        m.detection_confidence,
                        m.matching_confidence,
                        m.match_status
                    ])
        csv_text = csv_buffer.getvalue()

        # 3. Assemble Interactive Map Layers Configuration for UI
        if is_hospital_exposure:
            map_layers: List[Dict[str, Any]] = [
                {
                    "layer_id": "aoi_boundary_layer",
                    "title": f"Pune District AOI Boundary ({plan.where})",
                    "type": "geojson",
                    "style": {"color": "#2563eb", "weight": 2, "dashArray": "5,5", "fillColor": "#3b82f6", "fillOpacity": 0.08},
                    "visible": True
                },
                {
                    "layer_id": "landslide_risk_zones_layer",
                    "title": "Landslide Risk Hazard Polygons (2024)",
                    "type": "geojson",
                    "style": {"color": "#ef4444", "weight": 2, "fillColor": "#dc2626", "fillOpacity": 0.3},
                    "visible": True
                },
                {
                    "layer_id": "hospital_locations_layer",
                    "title": "Verified Hospitals & Exposure Status",
                    "type": "geojson",
                    "style": {"color": "#ffffff", "weight": 2.5, "radius": 8},
                    "visible": True
                }
            ]
        else:
            map_layers: List[Dict[str, Any]] = [
                {
                    "layer_id": "aoi_boundary_layer",
                    "title": f"AOI Boundary ({plan.where})",
                    "type": "geojson",
                    "style": {"color": "#3b82f6", "weight": 2, "fillOpacity": 0.1},
                    "visible": True
                },
                {
                    "layer_id": "proximity_buffer_200m",
                    "title": "200m Proximity Buffer Zone",
                    "type": "geojson",
                    "style": {"color": "#ef4444", "weight": 1.5, "dashArray": "4,4", "fillColor": "#fee2e2", "fillOpacity": 0.25},
                    "visible": True
                },
                {
                    "layer_id": "matched_features_layer",
                    "title": "Detected & Matched Spatial Features",
                    "type": "geojson",
                    "style": {"color": "#10b981", "weight": 3, "fillOpacity": 0.5},
                    "visible": True
                }
            ]

        # 4. Summary Statistics
        if is_hospital_exposure and hospital_features:
            inside_cnt = sum(1 for h in hospital_features if h.get("properties", {}).get("spatial_classification") == "inside")
            touch_cnt = sum(1 for h in hospital_features if h.get("properties", {}).get("spatial_classification") == "boundary_touching")
            outside_cnt = sum(1 for h in hospital_features if h.get("properties", {}).get("spatial_classification") == "outside")
            indet_cnt = sum(1 for h in hospital_features if h.get("properties", {}).get("spatial_classification") == "indeterminate")

            risk_class_counts: Dict[str, int] = {}
            for h in hospital_features:
                rc = h.get("properties", {}).get("primary_risk_class", "None")
                if rc != "None" and rc != "No Risk (Outside)":
                    risk_class_counts[rc] = risk_class_counts.get(rc, 0) + 1

            stats = {
                "aoi": plan.where,
                "analytical_task": plan.what,
                "observation_year": plan.when or "2024",
                "total_hospitals_evaluated": len(hospital_features),
                "hospitals_inside_risk_zones": inside_cnt,
                "hospitals_touching_boundaries": touch_cnt,
                "hospitals_outside_risk_zones": outside_cnt,
                "hospitals_indeterminate": indet_cnt,
                "counts_by_risk_class": risk_class_counts,
                "total_spatial_features": len(all_features),
                "crs": "EPSG:4326"
            }
        else:
            target_buildings = [
                f for f in all_features
                if f.get("properties", {}).get("feature_role") in ["target_building", "target_hospital"]
                or f.get("properties", {}).get("building_name")
            ]
            stats = {
                "aoi": plan.where,
                "analytical_task": plan.what,
                "total_spatial_features": len(all_features),
                "total_targets_evaluated": len(target_buildings) if target_buildings else len(all_features),
                "matched_features_count": len(target_buildings) if target_buildings else len([m for m in spatial_result.matched_features if m.match_status == "matched"]),
                "unmatched_detections_count": len(spatial_result.unmatched_detections),
                "unmatched_gis_features_count": len(spatial_result.unmatched_gis_features),
                "crs": "EPSG:4326",
                "projected_metric_crs": "EPSG:3857"
            }

        return FinalOutputDeliverable(
            plan_id=plan.plan_id,
            title=f"GEOAI-05 Final Analysis Deliverable: {plan.what.title()}",
            query_summary=plan.query_summary.model_dump(),
            geojson_export=geojson_export,
            csv_export=csv_text,
            map_layers=map_layers,
            summary_statistics=stats,
            validation_report=validation_report,
            status="completed"
        )



# Singleton Instance
output_engine = OutputEngine()
