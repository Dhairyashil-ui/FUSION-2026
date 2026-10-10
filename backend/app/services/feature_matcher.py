"""FUSION 2026 - AI-to-Map Feature Matching Stage (Part 3).

Connects AI visual detections (SAM 2, Grounding DINO, SegFormer, ChangeFormer) to mapped
geographic vector GIS features (OSM building footprints, drainage lines, infrastructure).

Calculates spatial distance in metres (using projected EPSG:3857 CRS) and geometry IoU overlap.
Preserves separate detection_confidence and matching_confidence.
Explicitly flags unmatched detections and unmatched GIS features instead of silently discarding them.
"""

import math
import uuid
import logging
from typing import List, Dict, Any, Tuple, Optional

from shapely.geometry import shape, mapping, Polygon, MultiPolygon, LineString, Point
from shapely.ops import transform
import pyproj

from app.schemas.vision_schema import DetectionResultItem
from app.schemas.retrieval_schema import RetrievedAssetMetadata
from app.schemas.spatial_schema import FeatureMatchItem

logger = logging.getLogger(__name__)

# Coordinate transformer: WGS84 EPSG:4326 -> Projected EPSG:3857 (Metres)
to_3857 = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True).transform
to_4326 = pyproj.Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True).transform


class FeatureMatcher:
    """Matches AI vision detections with mapped vector GIS features."""

    def match_features(
        self,
        detections: List[DetectionResultItem],
        gis_features: List[Dict[str, Any]],
        max_distance_meters: float = 50.0,
        min_iou_threshold: float = 0.20
    ) -> Tuple[List[FeatureMatchItem], List[str], List[str]]:
        """
        Matches vision detections to vector GIS features.

        Args:
            detections: List of DetectionResultItem objects from Visual Detection Engine.
            gis_features: List of GeoJSON feature dicts from Data Retrieval Engine.
            max_distance_meters: Maximum spatial distance in metres to consider a match.
            min_iou_threshold: Minimum geometry overlap (IoU) to consider a polygon match.

        Returns:
            Tuple containing:
            - matched_items: List of FeatureMatchItem objects.
            - unmatched_detections: List of unmatched detection IDs.
            - unmatched_gis_features: List of unmatched GIS feature IDs.
        """
        logger.info(f"FeatureMatcher: Matching {len(detections)} AI detections against {len(gis_features)} vector GIS features")

        matched_items: List[FeatureMatchItem] = []
        matched_det_ids = set()
        matched_gis_ids = set()

        # Parse GIS features into Shapely geometries (EPSG:3857)
        parsed_gis: List[Tuple[str, Any, Dict[str, Any]]] = []
        for idx, feat in enumerate(gis_features):
            gis_id = str(feat.get("id") or feat.get("properties", {}).get("name") or f"osm_feat_{idx+1}")
            geom_dict = feat.get("geometry")
            if not geom_dict:
                continue
            try:
                s_geom = shape(geom_dict)
                s_geom_3857 = transform(to_3857, s_geom)
                parsed_gis.append((gis_id, s_geom_3857, feat.get("properties", {})))
            except Exception as e:
                logger.warning(f"FeatureMatcher: Could not parse GIS geometry {gis_id}: {e}")

        # Iterate through detections and find best spatial match
        for det in detections:
            det_geom_dict = det.georeferenced_geometry
            if not det_geom_dict:
                continue

            try:
                det_shape = shape(det_geom_dict)
                det_shape_3857 = transform(to_3857, det_shape)
            except Exception as e:
                logger.warning(f"FeatureMatcher: Could not parse detection geometry {det.detection_id}: {e}")
                continue

            best_match_id = None
            best_dist = float("inf")
            best_iou = 0.0
            best_gis_props = {}
            best_gis_geom_3857 = None

            for gis_id, gis_geom_3857, props in parsed_gis:
                # Compute distance in metres
                dist = det_shape_3857.distance(gis_geom_3857)

                # Compute IoU if both are polygons
                iou = 0.0
                if det_shape_3857.geom_type in ["Polygon", "MultiPolygon"] and gis_geom_3857.geom_type in ["Polygon", "MultiPolygon"]:
                    try:
                        inter_area = det_shape_3857.intersection(gis_geom_3857).area
                        union_area = det_shape_3857.union(gis_geom_3857).area
                        if union_area > 0:
                            iou = inter_area / union_area
                    except Exception:
                        iou = 0.0

                if dist < best_dist:
                    best_dist = dist
                    best_iou = iou
                    best_match_id = gis_id
                    best_gis_props = props
                    best_gis_geom_3857 = gis_geom_3857

            # Evaluate matching evidence threshold
            is_match = False
            match_method = "spatial_distance"

            if best_iou >= min_iou_threshold:
                is_match = True
                match_method = "geometry_iou"
            elif best_dist <= max_distance_meters:
                is_match = True
                match_method = "spatial_distance"

            if is_match and best_match_id:
                matched_det_ids.add(det.detection_id)
                matched_gis_ids.add(best_match_id)

                # Matching confidence score based on spatial evidence
                dist_conf = max(0.0, 1.0 - (best_dist / max_distance_meters)) if max_distance_meters > 0 else 1.0
                match_conf = round(min(1.0, max(0.5, (0.6 * dist_conf) + (0.4 * best_iou))), 2)

                # Convert matched geometry back to EPSG:4326 for GeoJSON output
                matched_geom_4326 = mapping(transform(to_4326, best_gis_geom_3857)) if best_gis_geom_3857 else det_geom_dict

                matched_items.append(
                    FeatureMatchItem(
                        match_id=f"match_{uuid.uuid4().hex[:6]}",
                        detection_id=det.detection_id,
                        gis_feature_id=best_match_id,
                        target_class=det.target_class,
                        matching_method=match_method,
                        spatial_distance_meters=round(best_dist, 2),
                        geometry_iou=round(best_iou, 4),
                        detection_confidence=det.confidence,
                        matching_confidence=match_conf,
                        match_status="matched",
                        matched_geometry=matched_geom_4326,
                        original_name=best_gis_props.get("name") or best_gis_props.get("building") or best_gis_props.get("addr:street"),
                        provenance=f"Matched AI detection '{det.detection_id}' ({det.model_id}) with GIS feature '{best_match_id}' via {match_method} (dist: {round(best_dist, 1)}m, IoU: {round(best_iou, 2)})"
                    )
                )
            else:
                # Mark as unmatched detection (preserve spatial entity)
                matched_items.append(
                    FeatureMatchItem(
                        match_id=f"unmatched_det_{uuid.uuid4().hex[:6]}",
                        detection_id=det.detection_id,
                        gis_feature_id="unmatched",
                        target_class=det.target_class,
                        matching_method="none",
                        spatial_distance_meters=round(best_dist, 2) if best_dist < 10000 else None,
                        geometry_iou=round(best_iou, 4),
                        detection_confidence=det.confidence,
                        matching_confidence=0.0,
                        match_status="unmatched_detection",
                        matched_geometry=det_geom_dict,
                        provenance=f"AI detection '{det.detection_id}' ({det.model_id}) has no matching vector feature within {max_distance_meters}m"
                    )
                )

        unmatched_det_list = [d.detection_id for d in detections if d.detection_id not in matched_det_ids]
        unmatched_gis_list = [g_id for g_id, _, _ in parsed_gis if g_id not in matched_gis_ids]

        logger.info(
            f"FeatureMatcher: Complete. Matches: {len([m for m in matched_items if m.match_status == 'matched'])}, "
            f"Unmatched Detections: {len(unmatched_det_list)}, Unmatched GIS Features: {len(unmatched_gis_list)}"
        )
        return matched_items, unmatched_det_list, unmatched_gis_list


# Singleton instance
feature_matcher = FeatureMatcher()
