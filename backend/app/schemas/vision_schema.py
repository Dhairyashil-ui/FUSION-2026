"""Pydantic schemas for GEOAI-05 Visual Detection Engine (Part 2)."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class DetectionResultItem(BaseModel):
    """Single detection or segmentation result from a vision/foundation model."""
    detection_id: str = Field(..., description="Unique detection identifier")
    model_id: str = Field(..., description="Model identifier (e.g. grounding_dino, sam_2, segformer, changeformer)")
    model_version: str = Field(default="v1.0-geospatial", description="Model version or checkpoint name")
    target_class: str = Field(..., description="Target entity class name")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    geometry_type: str = Field(default="Polygon", description="Geometry type: Polygon, MultiPolygon, BoundingBox")
    pixel_coordinates: Optional[Dict[str, Any]] = Field(default=None, description="Pixel bounds in source image tile (x_min, y_min, x_max, y_max)")
    georeferenced_geometry: Dict[str, Any] = Field(default_factory=dict, description="GeoJSON geometry object in EPSG:4326")
    source_tile_id: str = Field(default="tile_01", description="Source image/tile identifier")
    crs: str = Field(default="EPSG:4326", description="Coordinate Reference System")
    georeferencing_status: str = Field(default="verified", description="One of: 'verified', 'approximated', 'unverified'")
    processing_status: str = Field(default="completed", description="One of: 'completed', 'fallback', 'error'")
    provenance: str = Field(default="", description="Provenance and model inference parameters")


class VisualDetectionResult(BaseModel):
    """Structured result container for Visual Detection Engine execution."""
    plan_id: str = Field(..., description="QueryPlan identifier")
    status: str = Field(default="completed", description="Execution status: completed, partial_success, error")
    total_detections: int = Field(default=0, description="Total count of object detections/segmentations")
    selected_models: List[str] = Field(default_factory=list, description="List of vision model IDs executed")
    detections: List[DetectionResultItem] = Field(default_factory=list, description="List of detection result items")
    execution_summary: str = Field(default="", description="Summary of visual detection execution")
    warnings: List[str] = Field(default_factory=list, description="Execution warnings or fallback notices")


class Part2ExecutionResult(BaseModel):
    """Combined structured output from Part 2 (Data Retrieval Result + Visual Detection Result)."""
    plan_id: str = Field(..., description="QueryPlan identifier")
    retrieval_result: Dict[str, Any] = Field(..., description="Data Retrieval Engine result structure")
    visual_detection_result: VisualDetectionResult = Field(..., description="Visual Detection Engine result structure")
    status: str = Field(default="completed", description="Overall Part 2 execution status")
    execution_summary: str = Field(default="", description="Human-readable summary of Part 2 execution")
