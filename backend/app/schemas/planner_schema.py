"""Pydantic schemas for GEOAI-05 Multimodal AI Query Planner (Part 1 Architecture)."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class DataRetrievalStep(BaseModel):
    """Specifies dataset to retrieve, coverage, resolution, registered API, parameters, and dependencies."""
    category: str = Field(
        default="Vector GIS Data",
        description="One of: 'Boundaries / AOI', 'Optical Imagery', 'Vector GIS Data', 'Radar / SAR', 'Elevation / 3D', 'Thematic / Temporal Data'"
    )
    dataset_id: str = Field(..., description="ID of dataset (e.g. osm_buildings, sentinel_2_l2a, srtm_dem)")
    dataset_name: str = Field(default="", description="Human readable name of the dataset")
    requirement_level: str = Field(default="required", description="Requirement level: 'required', 'optional', or 'unnecessary'")
    purpose: str = Field(..., description="Purpose of retrieving this dataset")
    registered_source_api: str = Field(default="OSM_Overpass_API", description="Registered source/API from Data Source Registry")
    search_parameters: Dict[str, Any] = Field(default_factory=dict, description="Search parameters passed to API")
    spatial_coverage: str = Field(..., description="Spatial boundary or AOI")
    time_range: str = Field(default="Latest available", description="Relevant temporal range")
    resolution_requirements: str = Field(default="vector", description="Spatial/temporal resolution requirements")
    expected_format: str = Field(default="GeoJSON", description="Expected output format")
    priority: int = Field(default=1, description="Execution priority order")
    downstream_consumer: str = Field(default="spatial_analysis", description="Downstream component or step consuming this data")
    fallback_source: str = Field(default="None", description="Fallback provider API if primary fails")
    dependencies: List[str] = Field(default_factory=list, description="Prior steps or datasets required")


class VisualSearchStep(BaseModel):
    """Specifies object, scene, or change detection using registered vision & foundation models."""
    target_entity: str = Field(..., description="Target object, class, or scene to detect/segment/compare")
    model: str = Field(..., description="Supported vision model (e.g. grounding_dino, sam_2, segformer, prithvi, changeformer, remote_clip)")
    task: str = Field(default="instance_segmentation", description="Task: zero_shot_object_detection, instance_segmentation, semantic_segmentation, bi_temporal_change_detection, vision_language_retrieval")
    text_prompt: str = Field(..., description="Natural language prompt or class label descriptor")
    input_requirements: Dict[str, Any] = Field(default_factory=dict, description="Input imagery requirements (e.g. RGB, multispectral tensor, T1/T2 pair)")
    expected_geometry: str = Field(default="MultiPolygon", description="Expected geometry type (e.g. Polygon, BoundingBox, RasterMask)")
    confidence_threshold: float = Field(default=0.75, ge=0.0, le=1.0, description="Minimum detection confidence score")
    output_format: str = Field(default="georeferenced_vector", description="Output spatial format")


class SpatialAnalysisStep(BaseModel):
    """Specifies spatial join, buffer, proximity, alignment, raster math, or change analysis operation."""
    operation: str = Field(..., description="Supported spatial operation (e.g. distance_buffer_filter, spatial_join, raster_zonal_stats)")
    input_layers: List[str] = Field(..., description="Input layer names or step IDs")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Operation parameters (e.g. threshold_meters: 200, target_crs: EPSG:4326)")
    output_layer: str = Field(..., description="Result layer name")
    dependencies: List[str] = Field(default_factory=list, description="Dependencies required before running operation")
    expected_outputs: List[str] = Field(default_factory=list, description="Output layer artifacts")
    tools_used: List[str] = Field(default_factory=lambda: ["GeoPandas", "Shapely"], description="GIS tools used (GeoPandas, Shapely, pyproj, PostGIS)")


class OutputSpecificationStep(BaseModel):
    """Specifies result fields, map layers, geometry types, and export formats following user requested OUTPUT."""
    result_fields: List[str] = Field(default_factory=list, description="Schema fields in final output")
    map_layers: List[str] = Field(default_factory=list, description="Layers to display on map")
    geometry_types: List[str] = Field(default_factory=list, description="Geometry types (e.g. Polygon, MultiPolygon)")
    coordinates_or_bbox: Optional[str] = Field(default=None, description="AOI bounding box or coordinate bounds")
    summary_statistics: List[str] = Field(default_factory=list, description="Summary metrics to compute")
    export_formats: List[str] = Field(default_factory=list, description="Requested export formats")
    visualization_style: str = Field(default="choropleth_and_symbols", description="Map style configuration")


class ValidationFallbackStep(BaseModel):
    """Specifies data availability checks, spatial coverage, CRS validation, and fallback strategy."""
    data_availability_checks: List[str] = Field(default_factory=list, description="Checks verifying dataset availability")
    spatial_coverage_checks: List[str] = Field(default_factory=list, description="Checks verifying boundary containment")
    crs_validation: str = Field(default="EPSG:4326", description="Target Coordinate Reference System")
    geometry_validity_checks: List[str] = Field(default_factory=list, description="Checks for self-intersecting or invalid polygons")
    duplicate_detection_checks: List[str] = Field(default_factory=list, description="Spatial deduplication checks")
    confidence_threshold_checks: List[str] = Field(default_factory=list, description="Confidence threshold checks")
    uncertain_classification_handling: str = Field(default="Flag low-confidence detections for manual review", description="Handling of uncertain classifications")
    unmatched_feature_handling: str = Field(default="Log unmatched features and notify user", description="Handling of unmatched features")
    fallback_strategy: Optional[str] = Field(default=None, description="Action taken if primary data/model fails")


class ExecutionStep(BaseModel):
    """Single node in the execution dependency graph."""
    step_id: str = Field(..., description="Unique step identifier (e.g. step_1)")
    step_name: str = Field(..., description="Human-readable step title")
    step_type: str = Field(..., description="Category: retrieval, visual_search, spatial_analysis, validation, export")
    operation: str = Field(..., description="Specific operation or connector executed")
    inputs: List[str] = Field(default_factory=list, description="Step IDs or layer names required as input")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Step parameters")
    expected_outputs: List[str] = Field(default_factory=list, description="Output layer names or artifacts")
    failure_conditions: List[str] = Field(default_factory=list, description="Conditions under which step fails")
    dependencies: List[str] = Field(default_factory=list, description="Prior step IDs")


class FivePlans(BaseModel):
    """Container for the Five Structured Plans."""
    data_retrieval_plan: List[DataRetrievalStep] = Field(default_factory=list)
    visual_detection_plan: List[VisualSearchStep] = Field(default_factory=list)
    spatial_analysis_plan: List[SpatialAnalysisStep] = Field(default_factory=list)
    validation_plan: ValidationFallbackStep = Field(default_factory=ValidationFallbackStep)
    output_and_visualization_plan: OutputSpecificationStep = Field(default_factory=OutputSpecificationStep)


class QuerySummary(BaseModel):
    """Canonical 6-field query summary."""
    query_text: str = Field(default="", description="Original query string")
    what: str = Field(default="", description="Analytical problem or intent")
    where: str = Field(default="", description="Area of interest (AOI)")
    when: str = Field(default="Latest available", description="Temporal range or date")
    target: List[str] = Field(default_factory=list, description="Target entities")
    measurements: str = Field(default="", description="Spatial relationships, constraints, filters and operations")
    output: List[str] = Field(default_factory=list, description="Requested deliverables")


class QueryPlan(BaseModel):
    """Complete machine-readable execution plan for GEOAI-05 Multimodal GeoAI Query Engine."""
    plan_id: str = Field(..., description="Unique plan identifier")
    query_summary: QuerySummary = Field(default_factory=QuerySummary)
    what: str = Field(..., description="Analytical task")
    where: str = Field(..., description="Area of interest")
    when: str = Field(default="Latest available", description="Temporal range")
    target: List[str] = Field(default_factory=list, description="Target entities")
    measurement: str = Field(..., description="Spatial relationships, constraints, filters and operations")
    output_format: List[str] = Field(default_factory=list, description="Requested deliverables")
    data_retrieval: List[DataRetrievalStep] = Field(default_factory=list)
    visual_search: List[VisualSearchStep] = Field(default_factory=list)
    spatial_analysis: List[SpatialAnalysisStep] = Field(default_factory=list)
    output_specification: OutputSpecificationStep = Field(default_factory=OutputSpecificationStep)
    validation_and_fallback: ValidationFallbackStep = Field(default_factory=ValidationFallbackStep)
    five_plans: FivePlans = Field(default_factory=FivePlans)
    execution_graph: List[ExecutionStep] = Field(default_factory=list)
    dataset_requirements: Dict[str, List[str]] = Field(default_factory=dict, description="Categorized as required, optional, unnecessary")
    selected_models_and_tools: Dict[str, Any] = Field(default_factory=dict, description="Selected vision models & GIS tools with validation status")
    expected_outputs_and_failure_conditions: Dict[str, Any] = Field(default_factory=dict, description="Outputs and failure handling summary")
    missing_data_flags: List[str] = Field(default_factory=list, description="Flagged missing datasets unsupported by Data Source Registry")
    is_valid: bool = Field(default=True, description="True if plan satisfies allowlist and schema checks")
    validation_warnings: List[str] = Field(default_factory=list, description="Any warnings or fallback notices")
