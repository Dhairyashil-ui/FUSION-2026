"""Model and Tool Registry for GEOAI-05 Multimodal GeoAI Query Engine.

Machine-readable registry of vision models, foundation models, change detection models,
and GIS analysis tools. Tracks supported tasks, dependencies, installation status,
input/output formats, hardware requirements, and availability.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class ModelRegistryEntry(BaseModel):
    """Machine-readable registry entry for vision/foundation models."""
    id: str = Field(..., description="Unique model identifier")
    name: str = Field(..., description="Human-readable model name")
    category: str = Field(..., description="Model category (e.g. vision_model, foundation_model, change_detection_model)")
    supported_tasks: List[str] = Field(default_factory=list, description="Supported tasks (e.g. zero_shot_detection, segmentation)")
    dependencies: List[str] = Field(default_factory=list, description="Python package dependencies")
    installation_status: str = Field(default="requires_setup", description="One of: 'installed', 'requires_setup', 'not_installed', 'mocked_fallback'")
    input_formats: List[str] = Field(default_factory=list, description="Supported input formats (e.g. RGB Image, GeoTIFF, Text Prompt)")
    output_formats: List[str] = Field(default_factory=list, description="Supported output formats (e.g. Bounding Boxes, Segmentation Masks, GeoJSON)")
    hardware_requirements: str = Field(default="CPU / GPU", description="Hardware requirement (e.g. CUDA GPU >= 8GB VRAM)")
    availability: str = Field(default="available", description="Model availability: 'available', 'requires_weights', 'experimental'")


class GISToolRegistryEntry(BaseModel):
    """Machine-readable registry entry for GIS analytical tools."""
    id: str = Field(..., description="Unique GIS tool identifier")
    name: str = Field(..., description="Human-readable tool name")
    category: str = Field(default="gis_tool", description="Category: gis_tool or spatial_database")
    supported_operations: List[str] = Field(default_factory=list, description="Supported spatial operations")
    dependencies: List[str] = Field(default_factory=list, description="Dependencies")
    installation_status: str = Field(default="installed", description="Installation status")
    input_formats: List[str] = Field(default_factory=list, description="Input data types")
    output_formats: List[str] = Field(default_factory=list, description="Output data types")
    hardware_requirements: str = Field(default="CPU / Memory", description="Hardware requirement")


# Authoritative Machine-Readable Vision & Foundation Model Registry
MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "grounding_dino": {
        "id": "grounding_dino",
        "name": "Grounding DINO",
        "category": "vision_model",
        "supported_tasks": ["zero_shot_object_detection", "open_vocabulary_detection", "text_prompted_detection", "bounding_box_extraction"],
        "dependencies": ["torch", "transformers", "groundingdino-py"],
        "installation_status": "installed",
        "input_formats": ["RGB Image", "Cloud-Optimized GeoTIFF", "Natural Language Prompt"],
        "output_formats": ["Bounding Boxes", "Confidence Scores", "GeoJSON Polygons"],
        "hardware_requirements": "CUDA GPU (VRAM >= 8GB)",
        "availability": "available",
    },
    "yolo_world": {
        "id": "yolo_world",
        "name": "YOLO-World",
        "category": "vision_model",
        "supported_tasks": ["real_time_open_vocabulary_detection", "fast_object_detection", "bounding_box_extraction"],
        "dependencies": ["ultralytics", "torch"],
        "installation_status": "requires_setup",
        "input_formats": ["RGB Image", "Class Labels"],
        "output_formats": ["Bounding Boxes", "Class Indices"],
        "hardware_requirements": "CUDA GPU or High-End CPU",
        "availability": "available",
    },
    "sam_2": {
        "id": "sam_2",
        "name": "SAM 2 (Segment Anything Model 2)",
        "category": "vision_model",
        "supported_tasks": ["instance_segmentation", "zero_shot_promptable_segmentation", "building_footprint_refinement", "mask_extraction"],
        "dependencies": ["torch", "sam2", "torchvision"],
        "installation_status": "installed",
        "input_formats": ["RGB Image", "GeoTIFF", "Bounding Box Prompts", "Point Prompts"],
        "output_formats": ["Segmentation Masks", "GeoJSON MultiPolygons"],
        "hardware_requirements": "CUDA GPU (VRAM >= 12GB)",
        "availability": "available",
    },
    "segformer": {
        "id": "segformer",
        "name": "SegFormer",
        "category": "vision_model",
        "supported_tasks": ["semantic_segmentation", "land_cover_classification", "urban_green_space_segmentation", "water_body_extraction"],
        "dependencies": ["torch", "transformers"],
        "installation_status": "installed",
        "input_formats": ["Multispectral Satellite Imagery", "RGB Image"],
        "output_formats": ["Semantic Segmentation Raster", "GeoJSON Polygons"],
        "hardware_requirements": "CUDA GPU or CPU",
        "availability": "available",
    },
    "prithvi": {
        "id": "prithvi",
        "name": "Prithvi (IBM-NASA Geospatial Foundation Model)",
        "category": "foundation_model",
        "supported_tasks": ["multi_temporal_land_cover", "burn_severity_assessment", "crop_yield_monitoring", "flood_inundation_foundation_analysis"],
        "dependencies": ["torch", "huggingface_hub", "rasterio"],
        "installation_status": "requires_setup",
        "input_formats": ["Sentinel-2 HLS Multispectral Time-Series Tensors (6-Band)"],
        "output_formats": ["Dense Classification Raster", "Change Probability Map"],
        "hardware_requirements": "CUDA GPU (VRAM >= 16GB)",
        "availability": "requires_weights",
    },
    "changeformer": {
        "id": "changeformer",
        "name": "ChangeFormer",
        "category": "change_detection_model",
        "supported_tasks": ["bi_temporal_change_detection", "urban_expansion_tracking", "building_construction_detection", "demolition_tracking"],
        "dependencies": ["torch", "einops"],
        "installation_status": "requires_setup",
        "input_formats": ["Co-Registered Optical Image Pair (Date T1, Date T2)"],
        "output_formats": ["Change Binary Mask", "Building Growth Polygons", "GeoJSON"],
        "hardware_requirements": "CUDA GPU (VRAM >= 8GB)",
        "availability": "requires_weights",
    },
    "remote_clip": {
        "id": "remote_clip",
        "name": "RemoteCLIP",
        "category": "foundation_model",
        "supported_tasks": ["vision_language_satellite_retrieval", "semantic_image_search", "zero_shot_scene_classification"],
        "dependencies": ["torch", "open_clip_torch"],
        "installation_status": "installed",
        "input_formats": ["Natural Language Text Query", "Satellite Tile RGB Embeddings"],
        "output_formats": ["Similarity Scores", "Ranked Image Tiles", "Embedding Vectors"],
        "hardware_requirements": "CUDA GPU or CPU",
        "availability": "available",
    },
}

# Authoritative Machine-Readable GIS Tool Registry
GIS_TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "geopandas": {
        "id": "geopandas",
        "name": "GeoPandas",
        "category": "gis_tool",
        "supported_operations": [
            "distance_buffer_filter", "spatial_join", "spatial_intersection",
            "attribute_filter", "spatial_union", "area_threshold_filter",
            "proximity_analysis", "coordinate_reproject"
        ],
        "dependencies": ["geopandas", "shapely", "fiona", "pyproj"],
        "installation_status": "installed",
        "input_formats": ["GeoJSON", "Shapefile", "GeoPackage", "GeoDataFrame"],
        "output_formats": ["GeoDataFrame", "GeoJSON", "Export Files"],
        "hardware_requirements": "CPU / Memory",
    },
    "shapely": {
        "id": "shapely",
        "name": "Shapely",
        "category": "gis_tool",
        "supported_operations": [
            "buffer", "intersection", "union", "difference", "convex_hull",
            "geometry_validation", "contains_check"
        ],
        "dependencies": ["shapely", "GEOS"],
        "installation_status": "installed",
        "input_formats": ["Shapely Geometries", "WKT", "WKB"],
        "output_formats": ["Shapely Geometries", "WKT"],
        "hardware_requirements": "CPU",
    },
    "pyproj": {
        "id": "pyproj",
        "name": "pyproj",
        "category": "gis_tool",
        "supported_operations": [
            "coordinate_reproject", "crs_normalization", "geodetic_distance"
        ],
        "dependencies": ["pyproj", "PROJ"],
        "installation_status": "installed",
        "input_formats": ["EPSG Codes", "PROJ Strings", "Coordinate Arrays"],
        "output_formats": ["Transformed Coordinates", "Target CRS Metadata"],
        "hardware_requirements": "CPU",
    },
    "postgis": {
        "id": "postgis",
        "name": "PostGIS Spatial Database Engine",
        "category": "spatial_database",
        "supported_operations": [
            "spatial_join", "spatial_index_query", "st_buffer", "st_intersection",
            "large_scale_aggregation"
        ],
        "dependencies": ["postgresql", "postgis", "psycopg2"],
        "installation_status": "requires_setup",
        "input_formats": ["PostgreSQL Tables", "Spatial SQL Queries"],
        "output_formats": ["SQL Query Result Sets", "GeoJSON"],
        "hardware_requirements": "Database Server",
    },
}


def get_registered_model(model_name: str) -> Optional[ModelRegistryEntry]:
    """Retrieves a ModelRegistryEntry by ID or alias."""
    name_clean = model_name.lower().replace("_geo", "").replace("-", "_")
    if name_clean in MODEL_REGISTRY:
        return ModelRegistryEntry.model_validate(MODEL_REGISTRY[name_clean])
    for entry in MODEL_REGISTRY.values():
        if entry["id"].lower() == name_clean or entry["name"].lower() == name_clean:
            return ModelRegistryEntry.model_validate(entry)
    return None


def get_registered_tool(tool_name: str) -> Optional[GISToolRegistryEntry]:
    """Retrieves a GISToolRegistryEntry by ID or alias."""
    name_clean = tool_name.lower().replace("-", "_")
    if name_clean in GIS_TOOL_REGISTRY:
        return GISToolRegistryEntry.model_validate(GIS_TOOL_REGISTRY[name_clean])
    for entry in GIS_TOOL_REGISTRY.values():
        if entry["id"].lower() == name_clean or entry["name"].lower() == name_clean:
            return GISToolRegistryEntry.model_validate(entry)
    return None


def list_registered_models() -> List[ModelRegistryEntry]:
    """Lists all registered vision and foundation models."""
    return [ModelRegistryEntry.model_validate(val) for val in MODEL_REGISTRY.values()]


def list_registered_tools() -> List[GISToolRegistryEntry]:
    """Lists all registered GIS tools and spatial database engines."""
    return [GISToolRegistryEntry.model_validate(val) for val in GIS_TOOL_REGISTRY.values()]


def find_models_for_task(task_keyword: str) -> List[ModelRegistryEntry]:
    """Finds registered models that support a given task keyword."""
    task_lower = task_keyword.lower()
    matches: List[ModelRegistryEntry] = []
    for entry in MODEL_REGISTRY.values():
        if any(task_lower in t.lower() for t in entry["supported_tasks"]):
            matches.append(ModelRegistryEntry.model_validate(entry))
    return matches
