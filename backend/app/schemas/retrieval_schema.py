"""Pydantic schemas for GEOAI-05 Data Retrieval Execution Engine."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class DataSourceRegistryEntry(BaseModel):
    """Entry describing a registered data source in the Data Source Registry."""
    source_id: str = Field(..., description="Unique identifier of data source")
    name: str = Field(..., description="Human readable provider and dataset name")
    provider: str = Field(..., description="Data provider organization")
    categories: List[str] = Field(..., description="One or more of the 6 common categories")
    supported_datasets: List[str] = Field(..., description="List of supported dataset IDs or feature types")
    spatial_coverage: str = Field(default="Global", description="Geographic coverage area")
    temporal_coverage: str = Field(default="Latest / Historical", description="Available time range")
    api_endpoint: Optional[str] = Field(default=None, description="Base API endpoint or URL")
    supported_formats: List[str] = Field(default_factory=list, description="Output formats (GeoJSON, GeoTIFF, COG, CSV, LAS/LAZ)")
    auth_required: bool = Field(default=False, description="True if credentials/token required")
    auth_type: str = Field(default="None", description="Authentication type: None, API_Key, Bearer_Token, OAuth")
    license: str = Field(default="Open Data / Public Domain", description="Licence and usage terms")
    usage_limits: str = Field(default="Standard rate limits apply", description="Rate limits and access restrictions")
    connector_status: str = Field(
        default="implemented",
        description="One of: 'implemented', 'requires_credentials', 'registry_only', 'unsupported'"
    )
    fallback_sources: List[str] = Field(default_factory=list, description="List of fallback source IDs")


class DatasetDiscoveryQuery(BaseModel):
    """Parameters for discovering datasets across registered sources."""
    aoi_name: Optional[str] = Field(default=None, description="Location name or city")
    bbox: Optional[List[float]] = Field(default=None, description="Bounding box [min_lon, min_lat, max_lon, max_lat]")
    category: Optional[str] = Field(default=None, description="Target category filter")
    dataset_type: Optional[str] = Field(default=None, description="Target dataset type (e.g. drainage, buildings, dem, thermal)")
    time_range: Optional[str] = Field(default=None, description="Desired temporal window")
    resolution_requirements: Optional[str] = Field(default=None, description="Resolution requirements")


class DatasetDiscoveryResult(BaseModel):
    """Result of catalog discovery search."""
    query: DatasetDiscoveryQuery
    matching_sources: List[DataSourceRegistryEntry] = Field(default_factory=list)
    total_matches: int = Field(default=0)


class RetrievedAssetMetadata(BaseModel):
    """Metadata detailing a single retrieved asset."""
    asset_id: str = Field(..., description="Unique asset ID")
    source_id: str = Field(..., description="Source API or connector ID")
    category: str = Field(..., description="Data category")
    provider: str = Field(..., description="Provider name")
    format: str = Field(..., description="Format of retrieved file or data structure")
    crs: str = Field(default="EPSG:4326", description="Coordinate Reference System")
    spatial_bounds: Optional[Dict[str, float]] = Field(default=None, description="Spatial bounding box dict")
    item_count: int = Field(default=0, description="Count of features/records retrieved")
    file_path: Optional[str] = Field(default=None, description="Absolute or relative path to cached asset file")
    status: str = Field(default="success", description="Status: 'success', 'cached', 'registry_only', 'error', 'unsupported'")
    execution_time_ms: float = Field(default=0.0, description="Time taken in milliseconds")
    provenance: Dict[str, Any] = Field(default_factory=dict, description="Metadata trace & download parameters")
    warnings: List[str] = Field(default_factory=list, description="Warnings or notices")


class RetrievalExecutionResult(BaseModel):
    """Complete response from Data Retrieval Engine execution."""
    plan_id: str = Field(..., description="Target execution plan ID")
    status: str = Field(..., description="Execution status: 'completed', 'partial_success', 'failed'")
    total_assets_retrieved: int = Field(default=0)
    assets: List[RetrievedAssetMetadata] = Field(default_factory=list)
    missing_data_flags: List[str] = Field(default_factory=list)
    execution_summary: str = Field(default="")
    warnings: List[str] = Field(default_factory=list)
