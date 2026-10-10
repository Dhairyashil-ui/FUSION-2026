"""FUSION 2026 - Data Source Registry Service.

Maintains verified data sources across all six geospatial data categories:
1. Boundaries / AOI
2. Optical Imagery
3. Vector GIS Data
4. Radar / SAR
5. Elevation / 3D
6. Thematic / Temporal Data

Stores capabilities, endpoints, formats, credentials, usage limits, and connector statuses.
Explicitly excludes Copernicus API integration (catalog entries marked 'registry_only').
"""

import logging
from typing import List, Dict, Optional, Any
from app.schemas.retrieval_schema import DataSourceRegistryEntry
from app.config import settings

logger = logging.getLogger(__name__)

# Six Common Data Categories
DATA_CATEGORIES = [
    "Boundaries / AOI",
    "Optical Imagery",
    "Vector GIS Data",
    "Radar / SAR",
    "Elevation / 3D",
    "Thematic / Temporal Data",
]


class DataSourceRegistry:
    """Central registry of all verified geospatial data sources."""

    def __init__(self):
        self._sources: Dict[str, DataSourceRegistryEntry] = {}
        self._load_default_registry()

    def _load_default_registry(self):
        """Populates default verified registry entries across the six categories."""
        entries = [
            # Category 1 — Boundaries / AOI
            DataSourceRegistryEntry(
                source_id="OSM_Nominatim_Boundary",
                name="OpenStreetMap Nominatim Geocoder & Boundary Service",
                provider="OpenStreetMap",
                categories=["Boundaries / AOI"],
                supported_datasets=["admin_boundaries", "aoi_polygon", "place_search"],
                spatial_coverage="Global",
                temporal_coverage="Current",
                api_endpoint="https://nominatim.openstreetmap.org/search",
                supported_formats=["GeoJSON", "JSON"],
                auth_required=False,
                auth_type="None",
                license="Open Database License (ODbL)",
                usage_limits="1 request/sec max, valid User-Agent required",
                connector_status="implemented",
                fallback_sources=["GADM_Admin_Boundaries"]
            ),
            DataSourceRegistryEntry(
                source_id="GADM_Admin_Boundaries",
                name="GADM Global Administrative Areas Catalog",
                provider="GADM",
                categories=["Boundaries / AOI"],
                supported_datasets=["admin_boundaries", "national_boundaries", "subnational_polygons"],
                spatial_coverage="Global",
                temporal_coverage="2018 - 2024",
                api_endpoint="https://gadm.org/data.html",
                supported_formats=["GeoJSON", "Shapefile", "Geopackage"],
                auth_required=False,
                auth_type="None",
                license="Free for academic and non-commercial use",
                usage_limits="Bulk download catalog access",
                connector_status="registry_only",
                fallback_sources=["OSM_Nominatim_Boundary"]
            ),
            DataSourceRegistryEntry(
                source_id="User_Provided_Geometry",
                name="User Provided Polygon / BBOX Input",
                provider="User Session",
                categories=["Boundaries / AOI"],
                supported_datasets=["aoi_polygon", "user_bbox"],
                spatial_coverage="User Defined",
                temporal_coverage="User Defined",
                api_endpoint=None,
                supported_formats=["GeoJSON", "WKT", "BBOX"],
                auth_required=False,
                auth_type="None",
                license="User Owned",
                usage_limits="N/A",
                connector_status="implemented",
                fallback_sources=[]
            ),

            # Category 2 — Optical Imagery
            DataSourceRegistryEntry(
                source_id="STAC_EarthSearch_Sentinel2",
                name="Element84 AWS STAC Catalog (Sentinel-2 L2A)",
                provider="Element84 / AWS Open Data",
                categories=["Optical Imagery"],
                supported_datasets=["sentinel_2_l2a", "optical_multispectral", "ndvi_baseline"],
                spatial_coverage="Global",
                temporal_coverage="2015 - Present",
                api_endpoint="https://earth-search.aws.element84.com/v1",
                supported_formats=["Cloud-Optimized GeoTIFF (COG)", "GeoTIFF", "JSON"],
                auth_required=False,
                auth_type="None",
                license="CC-BY 4.0 / Public Open Data",
                usage_limits="Public STAC API",
                connector_status="implemented",
                fallback_sources=["USGS_EarthExplorer_Optical"]
            ),
            DataSourceRegistryEntry(
                source_id="Copernicus_Data_Space",
                name="Copernicus Data Space Ecosystem Catalog",
                provider="ESA Copernicus",
                categories=["Optical Imagery", "Radar / SAR"],
                supported_datasets=["sentinel_2_l2a", "sentinel_1_sar", "sentinel_3_olci"],
                spatial_coverage="Global",
                temporal_coverage="2014 - Present",
                api_endpoint="https://dataspace.copernicus.eu/",
                supported_formats=["SAFE", "GeoTIFF", "COG"],
                auth_required=True,
                auth_type="OAuth2",
                license="Copernicus Open Access License",
                usage_limits="Copernicus API integration is explicitly excluded by specification. Catalog reference only.",
                connector_status="registry_only",  # EXPLICIT REQUIREMENT: Do not implement Copernicus API
                fallback_sources=["STAC_EarthSearch_Sentinel2", "STAC_ASF_Sentinel1_SAR"]
            ),
            DataSourceRegistryEntry(
                source_id="USGS_EarthExplorer_Optical",
                name="USGS EarthExplorer Landsat & Historical Optical Catalog",
                provider="USGS",
                categories=["Optical Imagery", "Thematic / Temporal Data"],
                supported_datasets=["landsat_8_9", "landsat_7", "historical_aerial"],
                spatial_coverage="Global",
                temporal_coverage="1972 - Present",
                api_endpoint="https://m2m.cr.usgs.gov/api/api/json/stable/",
                supported_formats=["GeoTIFF", "TAR"],
                auth_required=True,
                auth_type="API_Token",
                license="Public Domain",
                usage_limits="Requires USGS M2M API Credentials",
                connector_status="requires_credentials",
                fallback_sources=["STAC_EarthSearch_Sentinel2"]
            ),
            DataSourceRegistryEntry(
                source_id="PlanetScope_API",
                name="PlanetScope High-Resolution Daily Imagery API",
                provider="Planet Labs",
                categories=["Optical Imagery"],
                supported_datasets=["planet_scope", "planet_basemap", "highres_optical"],
                spatial_coverage="Global",
                temporal_coverage="2016 - Present",
                api_endpoint="https://api.planet.com/data/v1/",
                supported_formats=["GeoTIFF", "COG"],
                auth_required=True,
                auth_type="API_Key",
                license="Commercial License Required",
                usage_limits="Quota dependent on Planet API Key",
                connector_status="requires_credentials",
                fallback_sources=["STAC_EarthSearch_Sentinel2"]
            ),

            # Category 3 — Vector GIS Data
            DataSourceRegistryEntry(
                source_id="OSM_Overpass_API",
                name="OpenStreetMap Overpass Vector Query API",
                provider="OpenStreetMap",
                categories=["Vector GIS Data"],
                supported_datasets=["osm_buildings", "osm_drainage", "osm_roads", "osm_structures", "osm_waterways", "osm_infrastructure"],
                spatial_coverage="Global",
                temporal_coverage="Current",
                api_endpoint="https://overpass-api.de/api/interpreter",
                supported_formats=["GeoJSON", "JSON", "OSM XML"],
                auth_required=False,
                auth_type="None",
                license="Open Database License (ODbL)",
                usage_limits="10,000 nodes per query limit, rate limited",
                connector_status="implemented",
                fallback_sources=["Geofabrik_Vector_Extract"]
            ),
            DataSourceRegistryEntry(
                source_id="Municipal_GIS_Portals",
                name="Municipal & Authorized Utility GIS Portals",
                provider="Local Municipalities",
                categories=["Vector GIS Data", "Boundaries / AOI"],
                supported_datasets=["underground_utilities", "detailed_drainage", "property_parcels"],
                spatial_coverage="Municipal / Regional",
                temporal_coverage="Varies",
                api_endpoint=None,
                supported_formats=["GeoJSON", "Shapefile", "Esri Feature Layer"],
                auth_required=True,
                auth_type="API_Key or OAuth",
                license="Municipal Terms of Service",
                usage_limits="Varies by local municipality",
                connector_status="registry_only",
                fallback_sources=["OSM_Overpass_API"]
            ),
            DataSourceRegistryEntry(
                source_id="Geofabrik_Vector_Extract",
                name="Geofabrik OpenStreetMap Regional Extracts",
                provider="Geofabrik",
                categories=["Vector GIS Data"],
                supported_datasets=["osm_vector_bulk", "regional_extracts"],
                spatial_coverage="Global Regional Extracts",
                temporal_coverage="Updated Daily",
                api_endpoint="https://download.geofabrik.de/",
                supported_formats=["PBF", "Shapefile"],
                auth_required=False,
                auth_type="None",
                license="ODbL",
                usage_limits="Bulk file download only",
                connector_status="registry_only",
                fallback_sources=["OSM_Overpass_API"]
            ),

            # Category 4 — Radar / SAR
            DataSourceRegistryEntry(
                source_id="STAC_ASF_Sentinel1_SAR",
                name="Alaska Satellite Facility (ASF) Sentinel-1 STAC API",
                provider="ASF / NASA / ESA",
                categories=["Radar / SAR"],
                supported_datasets=["sentinel_1_sar", "sar_grd", "flood_inundation_radar"],
                spatial_coverage="Global",
                temporal_coverage="2014 - Present",
                api_endpoint="https://stac.asf.alaska.edu/",
                supported_formats=["Cloud-Optimized GeoTIFF (COG)", "GeoTIFF", "JSON"],
                auth_required=False,
                auth_type="None",
                license="Open Data Policy",
                usage_limits="Public ASF STAC API search",
                connector_status="implemented",
                fallback_sources=["USGS_Sentinel1_Radar"]
            ),
            DataSourceRegistryEntry(
                source_id="USGS_Sentinel1_Radar",
                name="USGS Sentinel-1 Radar Route",
                provider="USGS",
                categories=["Radar / SAR"],
                supported_datasets=["sentinel_1_sar", "usgs_radar"],
                spatial_coverage="North America & Global",
                temporal_coverage="2014 - Present",
                api_endpoint="https://m2m.cr.usgs.gov/api/api/json/stable/",
                supported_formats=["GeoTIFF"],
                auth_required=True,
                auth_type="API_Token",
                license="Public Domain",
                usage_limits="USGS M2M Authentication Required",
                connector_status="requires_credentials",
                fallback_sources=["STAC_ASF_Sentinel1_SAR"]
            ),

            # Category 5 — Elevation / 3D
            DataSourceRegistryEntry(
                source_id="OpenTopography_GlobalDEM",
                name="OpenTopography High-Resolution & Global DEM API",
                provider="OpenTopography / NSF",
                categories=["Elevation / 3D"],
                supported_datasets=["copernicus_dem", "srtm_dem", "nasadem", "dem_global"],
                spatial_coverage="Global",
                temporal_coverage="2000 - Present",
                api_endpoint="https://portal.opentopography.org/API/globaldem",
                supported_formats=["GeoTIFF", "AAIGrid"],
                auth_required=True,
                auth_type="API_Key",
                license="Creative Commons Attribution",
                usage_limits="Requires API Key (OPENTOPOGRAPHY_API_KEY)",
                connector_status="implemented",
                fallback_sources=["SRTM_DEM_30m"]
            ),
            DataSourceRegistryEntry(
                source_id="SRTM_DEM_30m",
                name="NASA Shuttle Radar Topography Mission 30m DEM",
                provider="NASA / USGS",
                categories=["Elevation / 3D"],
                supported_datasets=["srtm_dem", "elevation_contours"],
                spatial_coverage="Latitude -56° to +60°",
                temporal_coverage="2000 Baseline",
                api_endpoint="https://portal.opentopography.org/API/globaldem",
                supported_formats=["GeoTIFF"],
                auth_required=False,
                auth_type="None",
                license="Public Domain",
                usage_limits="30m spatial resolution",
                connector_status="implemented",
                fallback_sources=["OpenTopography_GlobalDEM"]
            ),
            DataSourceRegistryEntry(
                source_id="USGS_3DEP_PointCloud",
                name="USGS 3D Elevation Program High-Density LiDAR & Point Cloud",
                provider="USGS",
                categories=["Elevation / 3D"],
                supported_datasets=["usgs_3dep_lidar", "point_cloud", "building_height_3d"],
                spatial_coverage="United States & Territories",
                temporal_coverage="2010 - Present",
                api_endpoint="https://rockyweb.usgs.gov/vdelivery/Datasets/Staged/Elevation/",
                supported_formats=["Point Cloud (LAS/LAZ)", "GeoTIFF"],
                auth_required=False,
                auth_type="None",
                license="Public Domain",
                usage_limits="Bulk Point Cloud / AWS S3 Entwine access",
                connector_status="requires_credentials",
                fallback_sources=["OpenTopography_GlobalDEM"]
            ),

            # Category 6 — Thematic / Temporal Data
            DataSourceRegistryEntry(
                source_id="NASA_FIRMS_Thermal",
                name="NASA FIRMS Thermal Anomalies & Wildfire Hotspots API",
                provider="NASA FIRMS / LANCE",
                categories=["Thematic / Temporal Data"],
                supported_datasets=["modis_firms", "active_fires", "thermal_anomalies"],
                spatial_coverage="Global",
                temporal_coverage="2000 - Present (Real-time 3hr delay)",
                api_endpoint="https://firms.modaps.eosdis.nasa.gov/api/area/",
                supported_formats=["GeoJSON", "CSV", "KML"],
                auth_required=True,
                auth_type="API_Key",
                license="Public Domain / NASA LANCE License",
                usage_limits="MAP_KEY required (NASA_FIRMS_KEY)",
                connector_status="implemented",
                fallback_sources=["ESA_WorldCover_10m"]
            ),
            DataSourceRegistryEntry(
                source_id="NASA_CMR_Earthdata",
                name="NASA Common Metadata Repository (CMR) & Earthdata API",
                provider="NASA Earthdata",
                categories=["Thematic / Temporal Data", "Optical Imagery"],
                supported_datasets=["nasa_earthdata", "modis_landcover", "gpm_precipitation", "environmental_indices"],
                spatial_coverage="Global",
                temporal_coverage="1980 - Present",
                api_endpoint="https://cmr.earthdata.nasa.gov/search/",
                supported_formats=["GeoJSON", "JSON", "HDF", "NetCDF"],
                auth_required=True,
                auth_type="Bearer_Token",
                license="NASA Data Policy",
                usage_limits="Bearer Token authentication (NASA_EARTHDATA_TOKEN)",
                connector_status="implemented",
                fallback_sources=["ESA_WorldCover_10m"]
            ),
            DataSourceRegistryEntry(
                source_id="ESA_WorldCover_10m",
                name="ESA WorldCover 10m Land Cover Baseline Catalog",
                provider="ESA / VITO",
                categories=["Thematic / Temporal Data"],
                supported_datasets=["global_landcover", "land_use_classification"],
                spatial_coverage="Global",
                temporal_coverage="2020 - 2021 Baseline",
                api_endpoint="https://esa-worldcover.org/",
                supported_formats=["GeoTIFF", "COG"],
                auth_required=False,
                auth_type="None",
                license="CC-BY 4.0",
                usage_limits="Open land cover baseline",
                connector_status="implemented",
                fallback_sources=["NASA_CMR_Earthdata"]
            ),
            DataSourceRegistryEntry(
                source_id="Copernicus_EMS",
                name="Copernicus Emergency Management Service Catalog",
                provider="ESA / European Commission",
                categories=["Thematic / Temporal Data"],
                supported_datasets=["flood_inundation_vector", "disaster_damage_grading", "delineation_maps"],
                spatial_coverage="Global Activation Events",
                temporal_coverage="2012 - Present",
                api_endpoint="https://emergency.copernicus.eu/",
                supported_formats=["GeoJSON", "Shapefile", "PDF Vector Map"],
                auth_required=False,
                auth_type="None",
                license="Copernicus EMS Open Access",
                usage_limits="Copernicus API integration is explicitly excluded by specification. Product catalog access only.",
                connector_status="registry_only",  # EXPLICIT REQUIREMENT: Do not implement Copernicus API
                fallback_sources=["NASA_FIRMS_Thermal", "NASA_CMR_Earthdata"]
            ),
            DataSourceRegistryEntry(
                source_id="Landslide_Hazard_Registry",
                name="Geological Survey of India / ISRO Bhuvan Landslide Susceptibility Registry",
                provider="Geological Survey of India / ISRO Bhuvan",
                categories=["Thematic / Temporal Data", "Vector GIS Data"],
                supported_datasets=["landslide_hazard_zones", "landslide_susceptibility", "hazard_polygons"],
                spatial_coverage="India / Regional (Pune District)",
                temporal_coverage="2014 - Present",
                api_endpoint="https://bhuvan-app1.nrsc.gov.in/gsi_landslide/",
                supported_formats=["GeoJSON", "Shapefile"],
                auth_required=False,
                auth_type="None",
                license="Open Government Data License - India",
                usage_limits="Open Public Access",
                connector_status="implemented",
                fallback_sources=[]
            ),
        ]

        for entry in entries:
            self._sources[entry.source_id] = entry

    def register_source(self, entry: DataSourceRegistryEntry) -> DataSourceRegistryEntry:
        """Registers or updates a data source in the registry."""
        self._sources[entry.source_id] = entry
        logger.info(f"Registered data source '{entry.source_id}' ({entry.name}) under categories: {entry.categories}")
        return entry

    def get_source(self, source_id: str) -> Optional[DataSourceRegistryEntry]:
        """Retrieves a single source by ID."""
        return self._sources.get(source_id)

    def list_sources(
        self,
        category: Optional[str] = None,
        connector_status: Optional[str] = None
    ) -> List[DataSourceRegistryEntry]:
        """Lists sources filtered by category and/or connector status."""
        result = list(self._sources.values())
        if category:
            result = [s for s in result if category in s.categories]
        if connector_status:
            result = [s for s in result if s.connector_status == connector_status]
        return result

    def find_matching_source(
        self,
        category: str,
        dataset_type: Optional[str] = None
    ) -> Optional[DataSourceRegistryEntry]:
        """Finds the best implemented or credentials-ready source for a given category/dataset."""
        candidates = [s for s in self._sources.values() if category in s.categories]
        
        # Priority 1: Match dataset_type in supported_datasets and connector_status == 'implemented'
        if dataset_type:
            for s in candidates:
                if s.connector_status == "implemented" and any(ds.lower() in dataset_type.lower() or dataset_type.lower() in ds.lower() for ds in s.supported_datasets):
                    return s

        # Priority 2: Implemented connector in category
        for s in candidates:
            if s.connector_status == "implemented":
                return s

        # Priority 3: Credentials ready connector in category
        for s in candidates:
            if s.connector_status == "requires_credentials":
                return s

        # Priority 4: Return any matching registry entry
        return candidates[0] if candidates else None


# Singleton Instance
retrieval_registry = DataSourceRegistry()
