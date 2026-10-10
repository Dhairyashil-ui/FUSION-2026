import re

with open('backend/app/services/retrieval_connectors.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Original Nominatim fetch block from my first view_file
original_nominatim_fetch = '''    def fetch(
        self,
        spatial_coverage: str,
        search_parameters: Dict[str, Any],
        output_dir: str
    ) -> RetrievedAssetMetadata:
        t0 = time.time()
        location_name = search_parameters.get("query") or spatial_coverage or "Pune"
        query_encoded = urllib.parse.quote(location_name)
        url = f"https://nominatim.openstreetmap.org/search?q={query_encoded}&format=geojson&polygon_geojson=1&limit=1"

        headers = {"User-Agent": USER_AGENT}
        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT_SEC) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            
            features = data.get("features", [])
            item_count = len(features)
            
            # Save GeoJSON asset to cache directory
            file_name = f"nominatim_{location_name.lower().replace(' ', '_')}.geojson"
            file_path = os.path.join(output_dir, file_name)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            bbox = None
            if features:
                geometry = features[0].get("geometry", {})
                bbox_raw = features[0].get("bbox", [])
                if len(bbox_raw) == 4:
                    bbox = {"min_lon": bbox_raw[0], "min_lat": bbox_raw[1], "max_lon": bbox_raw[2], "max_lat": bbox_raw[3]}

            elapsed = (time.time() - t0) * 1000

            return RetrievedAssetMetadata(
                asset_id=f"boundary_{location_name.lower().replace(' ', '_')}",
                source_id=self.source_id,
                category=self.category,
                provider=self.provider,
                format="GeoJSON",
                crs="EPSG:4326",
                spatial_bounds=bbox,
                item_count=item_count,
                file_path=file_path,
                status="success" if item_count > 0 else "cached",
                execution_time_ms=elapsed,
                provenance={"url": url, "query": location_name, "connector": "NominatimBoundaryConnector"}
            )
        except Exception as exc:
            logger.warning(f"NominatimBoundaryConnector fetch error for '{location_name}': {exc}")
            elapsed = (time.time() - t0) * 1000
            # Construct robust fallback GeoJSON polygon for requested AOI
            fallback_geojson = {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"name": location_name, "type": "administrative_boundary"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[73.7, 18.4], [73.95, 18.4], [73.95, 18.65], [73.7, 18.65], [73.7, 18.4]]]
                        }
                    }
                ]
            }
            file_name = f"nominatim_fallback_{location_name.lower().replace(' ', '_')}.geojson"
            file_path = os.path.join(output_dir, file_name)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(fallback_geojson, f, indent=2)

            return RetrievedAssetMetadata(
                asset_id=f"boundary_fallback_{location_name.lower().replace(' ', '_')}",
                source_id=self.source_id,
                category=self.category,
                provider=self.provider,
                format="GeoJSON",
                crs="EPSG:4326",
                spatial_bounds={"min_lon": 73.7, "min_lat": 18.4, "max_lon": 73.95, "max_lat": 18.65},
                item_count=1,
                file_path=file_path,
                status="success",
                execution_time_ms=elapsed,
                provenance={"fallback": True, "error": str(exc), "query": location_name}
            )'''

new_overpass_fetch = '''    def fetch(
        self,
        spatial_coverage: str,
        search_parameters: Dict[str, Any],
        output_dir: str
    ) -> RetrievedAssetMetadata:
        t0 = time.time()
        area_name = search_parameters.get("area") or spatial_coverage or "Pune"
        
        # Determine the key and value to search for
        search_key = "building"
        search_val = ""
        
        if "amenity" in search_parameters:
            search_key = "amenity"
            search_val = f'="{search_parameters["amenity"]}"'
        elif "building" in search_parameters:
            search_key = "building"
            search_val = f'="{search_parameters["building"]}"'
        else:
            tags = search_parameters.get("tags", [])
            if isinstance(tags, list) and len(tags) > 0:
                tag = tags[0]
                if "=" in tag:
                    search_key, val = tag.split("=", 1)
                    search_val = f'="{val}"'
                else:
                    search_key = tag
                    search_val = ""

        ql_query = f"""
        [out:json][timeout:25];
        area["name"="{area_name}"]["boundary"="administrative"]->.searchArea;
        (
          node["{search_key}"{search_val}](area.searchArea);
          way["{search_key}"{search_val}](area.searchArea);
          relation["{search_key}"{search_val}](area.searchArea);
        );
        out center;
        """

        import urllib.request, urllib.parse
        try:
            req = urllib.request.Request(
                'https://overpass-api.de/api/interpreter',
                data=ql_query.encode('utf-8'),
                headers={'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'FUSION-2026-GeoAI-Engine/1.0'}
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(f"Overpass API failed: {exc}")
            result = {"elements": []}

        elements = result.get("elements", [])
        features = []
        min_lon, min_lat, max_lon, max_lat = float("inf"), float("inf"), float("-inf"), float("-inf")

        for el in elements:
            lat = el.get("lat") or (el.get("center") and el["center"].get("lat"))
            lon = el.get("lon") or (el.get("center") and el["center"].get("lon"))
            
            if lat and lon:
                lat, lon = float(lat), float(lon)
                if lon < min_lon: min_lon = lon
                if lat < min_lat: min_lat = lat
                if lon > max_lon: max_lon = lon
                if lat > max_lat: max_lat = lat
                
                tags_dict = el.get("tags", {})
                feat_id = f"{el.get('type')}/{el.get('id')}"
                
                features.append({
                    "type": "Feature",
                    "id": feat_id,
                    "properties": {
                        "feature_id": feat_id,
                        **tags_dict
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [lon, lat]
                    }
                })

        geojson = {
            "type": "FeatureCollection",
            "features": features
        }

        import os
        file_name = f"overpass_{area_name.lower().replace(' ', '_')}.geojson"
        file_path = os.path.join(output_dir, file_name)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(geojson, f, indent=2)

        elapsed = (time.time() - t0) * 1000
        bounds_dict = None
        if min_lon != float("inf"):
            bounds_dict = {"min_lon": round(min_lon, 6), "min_lat": round(min_lat, 6), "max_lon": round(max_lon, 6), "max_lat": round(max_lat, 6)}

        return RetrievedAssetMetadata(
            asset_id=f"overpass_{area_name.lower().replace(' ', '_')}",
            source_id=self.source_id,
            category=self.category,
            provider=self.provider,
            format="GeoJSON",
            crs="EPSG:4326",
            spatial_bounds=bounds_dict,
            item_count=len(features),
            file_path=file_path,
            status="success" if len(features) > 0 else "empty",
            execution_time_ms=elapsed,
            provenance={"api": "overpass-api.de", "area": area_name, "query": search_key}
        )'''

# Find the first and second fetch methods using simple regex
pattern = re.compile(r'    def fetch\(\s*self,\s*spatial_coverage: str,\s*search_parameters: Dict\[str, Any\],\s*output_dir: str\s*\) -> RetrievedAssetMetadata:.*?        return RetrievedAssetMetadata\([^)]*\)', re.DOTALL)
matches = list(pattern.finditer(content))

if len(matches) >= 2:
    # First match is the broken NominatimBoundaryConnector fetch
    content = content[:matches[0].start()] + original_nominatim_fetch + content[matches[0].end():]
    
    # Re-evaluate matches since string length changed
    matches2 = list(pattern.finditer(content))
    # Second match is the old OverpassVectorConnector fetch
    content = content[:matches2[1].start()] + new_overpass_fetch + content[matches2[1].end():]
    
    # Fix the unmatched } error by removing any leftover string from the bad replacement
    # The bad replacement left `).replace(' ', '_')}", ...` from original text because the regex ended too early
    # But replacing by strictly the original_nominatim_fetch will fix it entirely.
    
    with open('backend/app/services/retrieval_connectors.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed.")
else:
    print(f"Error finding matches, found {len(matches)}")
