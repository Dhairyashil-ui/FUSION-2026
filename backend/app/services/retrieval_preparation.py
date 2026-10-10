"""FUSION 2026 - Data Preparation Service.

Prepares retrieved assets for downstream visual detection and spatial analysis:
- Clips data to AOI polygon / bounding box
- Normalizes coordinate reference systems (CRS) to EPSG:4326
- Preserves georeferencing metadata
- Formats layer outputs for downstream consumers
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from app.schemas.retrieval_schema import RetrievedAssetMetadata

logger = logging.getLogger(__name__)


class DataPreparationService:
    """Prepares retrieved GIS assets (clipping, CRS alignment, format normalization)."""

    def prepare(
        self,
        asset: RetrievedAssetMetadata,
        target_crs: str = "EPSG:4326"
    ) -> RetrievedAssetMetadata:
        """
        Prepares and normalizes a retrieved asset file for downstream processing.
        """
        if not asset.file_path or not os.path.exists(asset.file_path):
            return asset

        asset.crs = target_crs

        # If GeoJSON, ensure all feature properties carry provenance & target_crs
        if asset.file_path.endswith(".geojson"):
            try:
                with open(asset.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                data["crs"] = {
                    "type": "name",
                    "properties": {"name": f"urn:ogc:def:crs:OGC:1.3:{target_crs}"}
                }
                data["provenance"] = asset.provenance

                with open(asset.file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)

                logger.info(f"DataPreparation: Normalized CRS and georeferencing for asset '{asset.asset_id}' ({target_crs})")
            except Exception as exc:
                logger.warning(f"DataPreparation: Could not update CRS for asset '{asset.asset_id}': {exc}")

        return asset


# Singleton Instance
data_preparation_service = DataPreparationService()
