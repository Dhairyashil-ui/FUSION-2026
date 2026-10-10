"""Pydantic schemas for GEOAI-05 Part 3 GIS Engine, Spatial Analysis, Validation and Output Generation."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class FeatureMatchItem(BaseModel):
    """Structured record connecting an AI visual detection to a mapped GIS feature."""
    match_id: str = Field(..., description="Unique match identifier")
    detection_id: str = Field(..., description="ID of AI detection or segmentation mask")
    gis_feature_id: str = Field(..., description="ID of mapped vector GIS feature (e.g. OSM ID)")
    target_class: str = Field(default="feature", description="Feature class name")
    matching_method: str = Field(default="spatial_distance", description="Matching method: spatial_distance, geometry_iou, attribute_similarity")
    spatial_distance_meters: Optional[float] = Field(default=None, description="Calculated metric distance in metres")
    geometry_iou: Optional[float] = Field(default=None, description="Geometry Intersection-over-Union score (0.0 to 1.0)")
    detection_confidence: float = Field(..., ge=0.0, le=1.0, description="Model vision detection confidence score")
    matching_confidence: float = Field(..., ge=0.0, le=1.0, description="Spatial evidence matching confidence score")
    match_status: str = Field(default="matched", description="Status: 'matched', 'unmatched_detection', 'unmatched_gis_feature', 'uncertain'")
    matched_geometry: Dict[str, Any] = Field(default_factory=dict, description="Georeferenced GeoJSON geometry in EPSG:4326")
    original_name: Optional[str] = Field(default=None, description="Original feature name from GIS data")
    provenance: str = Field(default="", description="Spatial evidence description")


class SpatialAnalysisLayerResult(BaseModel):
    """Output layer result for a single spatial operation step in the Spatial Analysis Plan."""
    layer_id: str = Field(..., description="Unique layer identifier")
    operation: str = Field(..., description="Executed spatial operation (e.g. distance_buffer_filter, spatial_join, raster_to_vector)")
    input_layers: List[str] = Field(default_factory=list, description="Inputs consumed")
    output_layer_name: str = Field(..., description="Result layer name")
    item_count: int = Field(default=0, description="Number of resulting spatial features")
    crs: str = Field(default="EPSG:4326", description="Output Coordinate Reference System")
    projected_crs_used: str = Field(default="EPSG:3857", description="Metric projected CRS used for distance math")
    geojson_data: Dict[str, Any] = Field(default_factory=dict, description="GeoJSON FeatureCollection payload")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Parameters passed (e.g. threshold_meters: 200)")
    tools_used: List[str] = Field(default_factory=lambda: ["GeoPandas", "Shapely"], description="GIS tools executed")
    execution_time_ms: float = Field(default=0.0, description="Execution time in milliseconds")
    status: str = Field(default="completed", description="Status: completed, partial, error")


class SpatialEngineResult(BaseModel):
    """Structured result container for Spatial Engine & Feature Matching execution."""
    plan_id: str = Field(..., description="QueryPlan identifier")
    status: str = Field(default="completed", description="Execution status: completed, partial_success, error")
    total_features_processed: int = Field(default=0, description="Total features processed across layers")
    matched_features: List[FeatureMatchItem] = Field(default_factory=list, description="AI-to-Map matched feature records")
    unmatched_detections: List[str] = Field(default_factory=list, description="List of unmatched detection IDs")
    unmatched_gis_features: List[str] = Field(default_factory=list, description="List of unmatched GIS feature IDs")
    analysis_layers: List[SpatialAnalysisLayerResult] = Field(default_factory=list, description="Result layers from spatial operations")
    execution_summary: str = Field(default="", description="Human-readable summary of spatial engine execution")
    warnings: List[str] = Field(default_factory=list, description="Execution warnings")


class FinalValidationReport(BaseModel):
    """Validation and provenance report for final spatial deliverables."""
    is_valid: bool = Field(default=True, description="True if output satisfies CRS and geometry checks")
    crs_validated: str = Field(default="EPSG:4326", description="Validated Coordinate Reference System")
    geometry_validity_passed: bool = Field(default=True, description="True if all geometries are valid")
    invalid_geometries_repaired: int = Field(default=0, description="Number of self-intersecting geometries repaired via Shapely")
    duplicate_features_removed: int = Field(default=0, description="Number of duplicate spatial features removed")
    completeness_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Data completeness score")
    confidence_summary: Dict[str, float] = Field(default_factory=dict, description="Summary of detection & matching confidence levels")
    provenance_records: List[Dict[str, Any]] = Field(default_factory=list, description="Lineage and processing history records")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    errors: List[str] = Field(default_factory=list, description="Validation errors")


class FinalOutputDeliverable(BaseModel):
    """Final output deliverable container for GeoJSON exports, CSV tabular data, and map layers."""
    plan_id: str = Field(..., description="QueryPlan identifier")
    title: str = Field(..., description="Deliverable title")
    query_summary: Dict[str, Any] = Field(default_factory=dict, description="Canonical 6-field query summary")
    geojson_export: Optional[Dict[str, Any]] = Field(default=None, description="Exportable GeoJSON FeatureCollection")
    csv_export: Optional[str] = Field(default=None, description="Exportable CSV formatted text")
    map_layers: List[Dict[str, Any]] = Field(default_factory=list, description="Interactive map layer specifications for UI")
    summary_statistics: Dict[str, Any] = Field(default_factory=dict, description="Tabular and spatial summary metrics")
    validation_report: FinalValidationReport = Field(default_factory=FinalValidationReport)
    status: str = Field(default="completed", description="Overall execution status: completed, partial_success, error")
