"""Allowlist and safety registry for GEOAI-05 Query Execution Plans.

Ensures LLM-generated plans strictly utilize validated datasets, connectors,
vision models, and spatial operations. Prevents arbitrary code or query injection.
"""

from typing import Tuple, List, Set, Dict, Any
from app.schemas.planner_schema import QueryPlan

# Six common data categories
DATA_CATEGORIES = [
    "Boundaries / AOI",
    "Optical Imagery",
    "Vector GIS Data",
    "Radar / SAR",
    "Elevation / 3D",
    "Thematic / Temporal Data",
]

# Authoritative Data Source Registry
DATA_SOURCE_REGISTRY: Dict[str, Dict[str, Any]] = {
    # 1. Boundaries / AOI
    "OSM_Nominatim_Boundary": {
        "category": "Boundaries / AOI",
        "dataset_id": "admin_boundaries",
        "dataset_name": "OpenStreetMap Nominatim Administrative Boundaries",
        "provider": "OpenStreetMap",
        "capabilities": ["Geocoding", "Bounding Box Extraction", "Administrative Polygons"],
        "coverage": "Global",
        "auth_required": False,
        "default_format": "GeoJSON",
        "fallback_api": "GADM_Admin_Boundaries",
    },
    "GADM_Admin_Boundaries": {
        "category": "Boundaries / AOI",
        "dataset_id": "admin_boundaries",
        "dataset_name": "GADM Global Administrative Areas",
        "provider": "GADM",
        "capabilities": ["National / Subnational Boundaries", "Level 0-3 Polygons"],
        "coverage": "Global",
        "auth_required": False,
        "default_format": "GeoJSON",
        "fallback_api": "OSM_Nominatim_Boundary",
    },

    # 2. Optical Imagery
    "STAC_EarthSearch_Sentinel2": {
        "category": "Optical Imagery",
        "dataset_id": "sentinel_2_l2a",
        "dataset_name": "Sentinel-2 MSI Level-2A Surface Reflectance",
        "provider": "ESA / Element84 STAC",
        "capabilities": ["Multispectral Imagery", "10m Spatial Resolution", "Cloud Filtering", "NDVI / Spectral Indices"],
        "coverage": "Global",
        "auth_required": False,
        "default_format": "Cloud-Optimized GeoTIFF (COG)",
        "fallback_api": "Landsat_8_9_STAC",
    },
    "Landsat_8_9_STAC": {
        "category": "Optical Imagery",
        "dataset_id": "landsat_8_9",
        "dataset_name": "Landsat 8-9 OLI/TIRS Surface Reflectance",
        "provider": "USGS / AWS STAC",
        "capabilities": ["30m Multispectral", "Thermal Infrared", "16-day Repeat Pass"],
        "coverage": "Global",
        "auth_required": False,
        "default_format": "Cloud-Optimized GeoTIFF (COG)",
        "fallback_api": "STAC_EarthSearch_Sentinel2",
    },
    "PlanetScope_API": {
        "category": "Optical Imagery",
        "dataset_id": "planet_scope",
        "dataset_name": "PlanetScope Daily Dove Imagery",
        "provider": "Planet Labs",
        "capabilities": ["3m High-Resolution Optical", "Daily Cadence", "RGB+NIR"],
        "coverage": "Global",
        "auth_required": True,
        "default_format": "GeoTIFF",
        "fallback_api": "STAC_EarthSearch_Sentinel2",
    },

    # 3. Vector GIS Data
    "OSM_Overpass_API": {
        "category": "Vector GIS Data",
        "dataset_id": "osm_buildings",
        "dataset_name": "OpenStreetMap Overpass Vector API",
        "provider": "OpenStreetMap",
        "capabilities": ["Building Footprints", "Drainage Lines & Waterways", "Road Networks", "Infrastructure"],
        "coverage": "Global",
        "auth_required": False,
        "default_format": "GeoJSON",
        "fallback_api": "Geofabrik_Vector_Extract",
    },
    "Geofabrik_Vector_Extract": {
        "category": "Vector GIS Data",
        "dataset_id": "osm_structures",
        "dataset_name": "Geofabrik OSM Regional Vector Extracts",
        "provider": "Geofabrik",
        "capabilities": ["Regional OpenStreetMap Shapefiles / PBF", "Bulk Vector Layers"],
        "coverage": "Global",
        "auth_required": False,
        "default_format": "GeoJSON",
        "fallback_api": "OSM_Overpass_API",
    },

    # 4. Radar / SAR
    "STAC_Sentinel1_SAR": {
        "category": "Radar / SAR",
        "dataset_id": "sentinel_1_sar",
        "dataset_name": "Sentinel-1 C-Band Synthetic Aperture Radar (GRD)",
        "provider": "ESA / ASF STAC",
        "capabilities": ["All-Weather / Cloud-Penetrating Radar", "Flood & Water Inundation Mapping", "VV/VH Polarization", "10m Resolution"],
        "coverage": "Global",
        "auth_required": False,
        "default_format": "Cloud-Optimized GeoTIFF (COG)",
        "fallback_api": "None",
    },

    # 5. Elevation / 3D
    "Copernicus_DEM_API": {
        "category": "Elevation / 3D",
        "dataset_id": "copernicus_dem",
        "dataset_name": "Copernicus Digital Elevation Model (GLO-30)",
        "provider": "ESA / AWS Open Data",
        "capabilities": ["30m Global Elevation", "Slope & Aspect Calculation", "Flood Inundation & Topography"],
        "coverage": "Global",
        "auth_required": False,
        "default_format": "Cloud-Optimized GeoTIFF (COG)",
        "fallback_api": "SRTM_DEM_30m",
    },
    "SRTM_DEM_30m": {
        "category": "Elevation / 3D",
        "dataset_id": "srtm_dem",
        "dataset_name": "Shuttle Radar Topography Mission (SRTM) DEM",
        "provider": "NASA / USGS",
        "capabilities": ["30m Spatial Resolution Digital Elevation", "Land Surface Contours"],
        "coverage": "Latitude -56° to +60°",
        "auth_required": False,
        "default_format": "GeoTIFF",
        "fallback_api": "Copernicus_DEM_API",
    },
    "USGS_3DEP_PointCloud": {
        "category": "Elevation / 3D",
        "dataset_id": "usgs_3dep_lidar",
        "dataset_name": "USGS 3D Elevation Program High-Density LiDAR",
        "provider": "USGS",
        "capabilities": ["High-Density 3D Point Cloud", "Building Height & Canopy Extraction", "1m DEM"],
        "coverage": "United States & Territories",
        "auth_required": False,
        "default_format": "Point Cloud (LAS/LAZ)",
        "fallback_api": "Copernicus_DEM_API",
    },

    # 6. Thematic / Temporal Data
    "Landslide_Hazard_Registry": {
        "category": "Thematic / Temporal Data",
        "dataset_id": "landslide_hazard_zones",
        "dataset_name": "Landslide Risk Hazard & Susceptibility Polygons (2024)",
        "provider": "Geological Survey of India / ISRO Bhuvan",
        "capabilities": ["Landslide Susceptibility Mapping", "Hazard Polygons", "2024 Temporal Assessment"],
        "coverage": "Pune District & Regional",
        "auth_required": False,
        "default_format": "GeoJSON",
        "fallback_api": "GSI_Landslide_Susceptibility",
    },
    "ESA_WorldCover_10m": {
        "category": "Thematic / Temporal Data",
        "dataset_id": "global_landcover",
        "dataset_name": "ESA WorldCover 10m Land Cover Classification",
        "provider": "ESA",
        "capabilities": ["10m Global Land Cover", "11 Land Cover Classes", "Temporal Baseline"],
        "coverage": "Global",
        "auth_required": False,
        "default_format": "GeoTIFF",
        "fallback_api": "MODIS_Thermal_Anomalies",
    },
    "MODIS_Thermal_Anomalies": {
        "category": "Thematic / Temporal Data",
        "dataset_id": "modis_firms",
        "dataset_name": "FIRMS Thermal Anomalies & Wildfire Hotspots",
        "provider": "NASA FIRMS",
        "capabilities": ["Daily Fire Hotspot Detection", "Active Thermal Monitoring"],
        "coverage": "Global",
        "auth_required": False,
        "default_format": "GeoJSON",
        "fallback_api": "ESA_WorldCover_10m",
    },
}

# Allowlist of supported data connectors & datasets
ALLOWED_DATASETS: Set[str] = {
    "osm_buildings",
    "osm_roads",
    "osm_waterways",
    "osm_drainage",
    "osm_hospitals",
    "osm_fire_stations",
    "osm_structures",
    "osm_infrastructure",
    "landslide_hazard_zones",
    "landslide_risk_polygons",
    "landslide_susceptibility",
    "sentinel_2_l2a",
    "landsat_8_9",
    "planet_scope",
    "naip_aerial",
    "srtm_dem",
    "copernicus_dem",
    "usgs_3dep_lidar",
    "sentinel_1_sar",
    "admin_boundaries",
    "global_landcover",
    "modis_firms",
}

# Allowlist of supported vision models and detectors
ALLOWED_VISION_MODELS: Set[str] = {
    "grounding_dino",
    "grounding_dino_geo",
    "yolo_world",
    "yolov8_geo",
    "sam_2",
    "segment_anything_geo",
    "segformer",
    "prithvi",
    "changeformer",
    "remote_clip",
    "clip_geo",
    "mask_rcnn_geo",
    "building_footprint_extractor",
}

# Allowlist of supported GIS analysis tools
ALLOWED_GIS_TOOLS: Set[str] = {
    "geopandas",
    "shapely",
    "pyproj",
    "postgis",
}

# Authoritative Capability Registry for Spatial Operations
SPATIAL_CAPABILITY_REGISTRY: Dict[str, Dict[str, Any]] = {
    "point_in_polygon_exposure": {
        "name": "Point-in-Polygon Exposure Analysis",
        "description": "Evaluates exact containment and boundary relationships between verified point/footprint targets and hazard polygons.",
        "required_inputs": ["target_features", "hazard_polygons"],
        "expected_outputs": ["exposure_classification_layer"],
        "dependencies": ["osm_hospitals", "landslide_hazard_zones"],
        "tools": ["GeoPandas", "Shapely", "PyProj"]
    },
    "distance_buffer_filter": {
        "name": "Distance Buffer Proximity Filter",
        "description": "Calculates metric distance in EPSG:3857 and filters target features within proximity buffer threshold.",
        "required_inputs": ["target_features", "reference_linear_feature"],
        "expected_outputs": ["proximity_buffer_layer"],
        "dependencies": ["osm_buildings", "osm_drainage"],
        "tools": ["GeoPandas", "Shapely"]
    },
    "spatial_join": {
        "name": "Spatial Join",
        "description": "Joins feature attributes based on spatial intersection or containment within AOI boundary.",
        "required_inputs": ["target_features", "boundary_features"],
        "expected_outputs": ["joined_spatial_layer"],
        "dependencies": ["admin_boundaries"],
        "tools": ["GeoPandas"]
    },
    "change_detection": {
        "name": "Bi-Temporal Change Detection",
        "description": "Compares bi-temporal imagery pairs to identify urban building growth and land cover changes.",
        "required_inputs": ["bitemporal_imagery"],
        "expected_outputs": ["change_vector_layer"],
        "dependencies": ["sentinel_2_l2a"],
        "tools": ["GeoPandas", "Shapely"]
    }
}

# Allowlist of supported spatial analysis operations
ALLOWED_SPATIAL_OPERATIONS: Set[str] = {
    "point_in_polygon_exposure",
    "exposure_analysis",
    "point_in_polygon",
    "distance_buffer_filter",
    "spatial_join",
    "spatial_intersection",
    "attribute_filter",
    "raster_zonal_stats",
    "convex_hull",
    "area_threshold_filter",
    "proximity_analysis",
    "change_detection_comparison",
    "density_heatmap_generation",
    "coordinate_reproject",
    "extract_aoi_boundary",
    "format_export_deliverable",
    "buffer",
    "intersect",
    "intersection",
    "union",
    "spatial_union",
    "difference",
    "dissolve",
    "overlay",
    "clip",
    "distance",
    "spatial_filter",
    "filter",
    "join",
    "crop",
    "mask",
    "reproject",
    "visual_detection",
    "compute_nbr",
    "delta_nbr",
    "compute_ndvi",
    "spectral_index",
    "raster_math",
    "threshold",
    "threshold_filter",
    "change_detection",
    "anomaly_detection",
    "clustering",
    "vectorize",
    "polygonize",
    "raster_to_vector",
    "aggregate",
    "spatial_aggregate",
    "summarize",
    "statistics",
}


# Default fallback mappings if requested dataset or model is unsupported
DATASET_FALLBACK_MAP = {
    "custom_drone_imagery": "planet_scope",
    "commercial_highres_sat": "planet_scope",
    "unknown_vector": "osm_buildings",
}

MODEL_FALLBACK_MAP = {
    "custom_cnn": "yolov8_geo",
    "gpt4_vision": "grounding_dino_geo",
}


def validate_plan_against_allowlist(plan: QueryPlan) -> Tuple[bool, List[str]]:
    """
    Strictly validates a QueryPlan against allowlists and the Data Source Registry.
    Rejects unauthorized operations/connectors and applies safe fallbacks when appropriate.
    Flags missing data if no suitable source exists in the registry.

    Args:
        plan: QueryPlan Pydantic model.

    Returns:
        Tuple[bool, List[str]]: (is_valid, list_of_warnings_or_errors)
    """
    warnings: List[str] = []
    is_valid = True

    # 1. Validate Data Retrieval Datasets against Registry and Allowlist
    for step in plan.data_retrieval:
        ds = step.dataset_id.lower()

        # Check if dataset_id is directly allowed or matched in registry
        is_direct_allowed = ds in ALLOWED_DATASETS
        matched_api = None
        for key, val in DATA_SOURCE_REGISTRY.items():
            if val["dataset_id"].lower() == ds:
                matched_api = key
                break

        # If dataset_id is NOT allowed or registered, apply fallback or missing data flag first
        if not is_direct_allowed and not matched_api:
            if ds in DATASET_FALLBACK_MAP:
                fallback = DATASET_FALLBACK_MAP[ds]
                warnings.append(f"Requested dataset '{ds}' is unavailable; applied valid fallback '{fallback}'.")
                step.dataset_id = fallback
                ds = fallback.lower()
                for key, val in DATA_SOURCE_REGISTRY.items():
                    if val["dataset_id"].lower() == ds:
                        matched_api = key
                        break
            else:
                # Safe fuzzy fallback matching or missing data flag
                if "sonar" in ds or "bathymetry" in ds or "hyperspectral" in ds or "unsupported" in ds:
                    flag_msg = f"Requested data '{ds}' has no registered API in Data Source Registry. Flagged missing data."
                    if flag_msg not in plan.missing_data_flags:
                        plan.missing_data_flags.append(flag_msg)
                    warnings.append(flag_msg)
                    step.requirement_level = "unnecessary"
                elif "osm" in ds or "building" in ds or "structure" in ds or "drain" in ds:
                    step.dataset_id = "osm_buildings"
                    ds = "osm_buildings"
                    matched_api = "OSM_Overpass_API"
                    warnings.append(f"Substituted dataset '{step.dataset_id}' with 'osm_buildings' (OSM_Overpass_API).")
                elif "sat" in ds or "image" in ds or "sentinel" in ds or "landsat" in ds:
                    step.dataset_id = "sentinel_2_l2a"
                    ds = "sentinel_2_l2a"
                    matched_api = "STAC_EarthSearch_Sentinel2"
                    warnings.append(f"Substituted dataset '{step.dataset_id}' with 'sentinel_2_l2a'.")
                elif "dem" in ds or "elevation" in ds:
                    step.dataset_id = "srtm_dem"
                    ds = "srtm_dem"
                    matched_api = "SRTM_DEM_30m"
                    warnings.append(f"Substituted dataset '{step.dataset_id}' with 'srtm_dem'.")
                elif "sar" in ds or "radar" in ds:
                    step.dataset_id = "sentinel_1_sar"
                    ds = "sentinel_1_sar"
                    matched_api = "STAC_Sentinel1_SAR"
                    warnings.append(f"Substituted dataset '{step.dataset_id}' with 'sentinel_1_sar'.")
                else:
                    step.dataset_id = "osm_buildings"
                    ds = "osm_buildings"
                    matched_api = "OSM_Overpass_API"
                    warnings.append(f"Defaulted dataset '{step.dataset_id}' to 'osm_buildings'.")

        # Now update step attributes by looking up step.dataset_id in DATA_SOURCE_REGISTRY
        matched_api = None
        for key, val in DATA_SOURCE_REGISTRY.items():
            reg_ds_id = val.get("dataset_id", "") if isinstance(val, dict) else getattr(val, "dataset_id", "")
            reg_supp = val.get("supported_datasets", []) if isinstance(val, dict) else getattr(val, "supported_datasets", [])
            if reg_ds_id.lower() == ds or any(d.lower() == ds for d in reg_supp):
                matched_api = key
                break

        api_to_use = matched_api or (step.registered_source_api if step.registered_source_api and step.registered_source_api != "OSM_Overpass_API" else "OSM_Overpass_API")
        if api_to_use in DATA_SOURCE_REGISTRY:
            reg_entry = DATA_SOURCE_REGISTRY[api_to_use]
            step.registered_source_api = api_to_use
            step.category = reg_entry["category"]
            step.dataset_name = reg_entry["dataset_name"]
            if not step.fallback_source or step.fallback_source == "None":
                step.fallback_source = reg_entry["fallback_api"]
            if not step.expected_format or step.expected_format == "GeoJSON":
                step.expected_format = reg_entry.get("default_format", "GeoJSON")

    # 2. Validate Visual Search Models
    for step in plan.visual_search:
        model = step.model.lower()
        if model not in ALLOWED_VISION_MODELS:
            if model in MODEL_FALLBACK_MAP:
                fallback = MODEL_FALLBACK_MAP[model]
                warnings.append(f"Requested model '{model}' unavailable; applied fallback '{fallback}'.")
                step.model = fallback
            else:
                step.model = "grounding_dino_geo"
                warnings.append(f"Model '{model}' is unsupported; defaulted to 'grounding_dino_geo'.")

    # Helper for fuzzy matching spatial operations
    def sanitize_spatial_op(op: str) -> str:
        if "exposure" in op or "point_in_polygon" in op or "landslide" in op or "containment" in op:
            return "point_in_polygon_exposure"
        elif "buffer" in op or "distance" in op or "proximity" in op:
            return "distance_buffer_filter"
        elif "join" in op:
            return "spatial_join"
        elif "intersect" in op:
            return "spatial_intersection"
        elif "union" in op:
            return "spatial_union"
        elif "change" in op:
            return "change_detection"
        elif "nbr" in op or "burn" in op:
            return "compute_nbr"
        elif "ndvi" in op or "index" in op or "spectral" in op:
            return "spectral_index"
        elif "thresh" in op:
            return "threshold"
        elif "anomaly" in op:
            return "anomaly_detection"
        elif "cluster" in op or "density" in op:
            return "clustering"
        elif "math" in op or "calc" in op:
            return "raster_math"
        elif "diff" in op:
            return "difference"
        elif "dissolv" in op:
            return "dissolve"
        elif "overlay" in op:
            return "overlay"
        elif "clip" in op or "crop" in op:
            return "clip"
        elif "vector" in op or "poly" in op:
            return "vectorize"
        elif "agg" in op or "summar" in op or "stat" in op:
            return "aggregate"
        elif "filter" in op:
            return "attribute_filter"
        return op

    # 3. Validate Spatial Operations
    for step in plan.spatial_analysis:
        op = step.operation.lower()
        if op not in ALLOWED_SPATIAL_OPERATIONS:
            sanitized = sanitize_spatial_op(op)
            if sanitized in ALLOWED_SPATIAL_OPERATIONS:
                step.operation = sanitized
                warnings.append(f"Substituted spatial operation '{op}' with '{sanitized}'.")
            else:
                is_valid = False
                warnings.append(f"Error: Spatial operation '{step.operation}' is not in the allowlist of supported spatial operations.")

    # 4. Validate Execution Graph Steps
    for step in plan.execution_graph:
        op = step.operation.lower()
        if step.step_type == "spatial_analysis" and op not in ALLOWED_SPATIAL_OPERATIONS:
            sanitized = sanitize_spatial_op(op)
            if sanitized in ALLOWED_SPATIAL_OPERATIONS:
                step.operation = sanitized
                warnings.append(f"Execution graph step '{step.step_id}' operation '{op}' substituted with '{sanitized}'.")
            else:
                is_valid = False
                warnings.append(f"Error: Execution graph step '{step.step_id}' uses unauthorized operation '{step.operation}'.")

    plan.is_valid = is_valid
    plan.validation_warnings = warnings

    return is_valid, warnings
