import re
import json

with open('backend/app/services/retrieval_connectors.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_fetch = '''    def fetch(
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

pattern = re.compile(r'    def fetch\(\s*self,\s*spatial_coverage: str,\s*search_parameters: Dict\[str, Any\],\s*output_dir: str\s*\) -> RetrievedAssetMetadata:.*?        return RetrievedAssetMetadata\([^)]*\)', re.DOTALL)
new_content, count = pattern.subn(new_fetch, content, count=1)

if count > 0:
    with open('backend/app/services/retrieval_connectors.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f'Replaced successfully. Count={count}')
else:
    print('Failed to match pattern')
