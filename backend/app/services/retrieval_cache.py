"""FUSION 2026 - Data Retrieval Cache & Storage Service.

Reuses downloaded assets, stores file artifacts, and tracks provenance:
- Storage path: backend/storage/retrieval_cache/
- Deterministic SHA-256 asset hashing
- Reuses valid downloaded assets to avoid redundant downloads & rate limits
"""

import os
import json
import hashlib
import logging
from typing import Optional, Dict, Any
from app.schemas.retrieval_schema import RetrievedAssetMetadata

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "storage", "retrieval_cache")
)


class RetrievalCacheStorage:
    """Manages file storage and persistent caching for retrieved GIS assets."""

    def __init__(self, cache_dir: str = CACHE_DIR):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        self._manifest_path = os.path.join(self.cache_dir, "cache_manifest.json")
        self._manifest: Dict[str, Dict[str, Any]] = self._load_manifest()

    def _load_manifest(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(self._manifest_path):
            try:
                with open(self._manifest_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as exc:
                logger.warning(f"RetrievalCacheStorage: Error loading manifest ({exc}). Resetting.")
        return {}

    def _save_manifest(self):
        try:
            with open(self._manifest_path, "w", encoding="utf-8") as f:
                json.dump(self._manifest, f, indent=2)
        except Exception as exc:
            logger.warning(f"RetrievalCacheStorage: Error saving manifest: {exc}")

    def compute_key(self, source_id: str, spatial_coverage: str, params: Dict[str, Any]) -> str:
        """Computes a deterministic hash key for a retrieval request."""
        raw = f"{source_id}:{spatial_coverage}:{json.dumps(params, sort_keys=True)}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def get(self, key: str) -> Optional[RetrievedAssetMetadata]:
        """Retrieves asset metadata if cached and file exists on disk."""
        if key in self._manifest:
            entry = self._manifest[key]
            file_path = entry.get("file_path")
            if file_path and os.path.exists(file_path):
                try:
                    orig_status = entry.get("status", "success")
                    if orig_status in ["blocked_missing_data", "registry_only", "error", "failed"]:
                        asset.status = orig_status
                    else:
                        asset.status = "cached"
                    logger.info(f"RetrievalCacheStorage: Cache hit for key '{key}' ({asset.asset_id})")
                    return asset
                except Exception:
                    pass
        return None

    def put(self, key: str, asset: RetrievedAssetMetadata):
        """Stores asset metadata in the cache manifest."""
        self._manifest[key] = asset.model_dump()
        self._save_manifest()
        logger.info(f"RetrievalCacheStorage: Cached asset '{asset.asset_id}' under key '{key}'")

    def get_cache_dir(self) -> str:
        return self.cache_dir


# Singleton Instance
retrieval_cache_storage = RetrievalCacheStorage()
