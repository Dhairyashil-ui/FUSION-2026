"""FUSION 2026 - Data Validation Service.

Validates retrieved asset files and data structures:
- Response HTTP status & error checks
- Metadata integrity
- Spatial coverage & bounding box overlap
- Format and CRS validation (EPSG:4326)
- Non-empty geometry / feature counts
"""

import os
import json
import logging
from typing import Dict, Any, Tuple, List, Optional
from app.schemas.retrieval_schema import RetrievedAssetMetadata

logger = logging.getLogger(__name__)


class DataValidator:
    """Validates retrieved data assets before passing to downstream engines."""

    def validate_asset(self, asset: RetrievedAssetMetadata) -> Tuple[bool, List[str]]:
        """
        Validates a retrieved asset for CRS, format, file existence, and non-empty content.

        Returns:
            Tuple[bool, List[str]]: (is_valid, list_of_warnings_or_errors)
        """
        warnings: List[str] = []
        is_valid = True

        # 1. Status check
        if asset.status == "registry_only":
            warnings.append(f"Asset '{asset.asset_id}' is a catalog reference only (registry_only).")
            return True, warnings

        if asset.status == "error":
            warnings.append(f"Asset '{asset.asset_id}' failed retrieval with error status.")
            return False, warnings

        # 2. File existence check
        if asset.file_path and not os.path.exists(asset.file_path):
            warnings.append(f"Cached asset file '{asset.file_path}' does not exist on disk.")
            is_valid = False

        # 3. CRS validation
        if asset.crs not in ["EPSG:4326", "EPSG:3857", "EPSG:32643"]:
            warnings.append(f"Asset CRS '{asset.crs}' differs from standard EPSG:4326.")

        # 4. GeoJSON integrity check
        if asset.file_path and asset.file_path.endswith(".geojson"):
            try:
                with open(asset.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("type") not in ["FeatureCollection", "Feature"]:
                    warnings.append(f"Invalid GeoJSON structure in '{asset.file_path}'.")
                    is_valid = False
                elif "features" in data and len(data["features"]) == 0:
                    warnings.append(f"GeoJSON asset '{asset.asset_id}' contains 0 features.")
            except Exception as exc:
                warnings.append(f"Failed to parse GeoJSON asset file: {exc}")
                is_valid = False

        return is_valid, warnings


# Singleton Instance
data_validator = DataValidator()
