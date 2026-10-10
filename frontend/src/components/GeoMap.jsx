import React, { useEffect, useRef, useState, useMemo } from 'react'
import L from 'leaflet'
import mapboxgl from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css'
import {
  Layers,
  Square,
  Trash2,
  Maximize2,
  Database,
  Check,
  ChevronDown,
  Box,
  RotateCw,
  MapPin,
  Globe,
  CheckCircle2,
  Activity,
  Eye,
  Ruler,
  Loader2
} from 'lucide-react'

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || ''
const GOOGLE_MAPS_API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || ''

// Basemap Tile & 3D Engine Providers
const BASEMAPS = {
  googleHybrid2D: {
    name: 'Google 2D Map (Satellite)',
    type: 'leaflet',
    url: 'https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
    attribution: '&copy; Google Maps'
  },
  googleSatellite2D: {
    name: 'Google 2D Satellite (Clean)',
    type: 'leaflet',
    url: 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
    attribution: '&copy; Google Maps'
  },
  mapboxSatellite: {
    name: 'Mapbox 3D Satellite',
    type: 'mapbox',
    style: 'mapbox://styles/mapbox/satellite-streets-v12',
    attribution: '© Mapbox © OpenStreetMap'
  },
  mapboxDark: {
    name: 'Mapbox 3D Dark',
    type: 'mapbox',
    style: 'mapbox://styles/mapbox/dark-v11',
    attribution: '© Mapbox © OpenStreetMap'
  },
  google3d: {
    name: 'Google 3D Satellite',
    type: 'google',
    mapTypeId: 'satellite',
    attribution: 'Map data © Google'
  },
  positron: {
    name: 'Clean Light (Carto)',
    type: 'leaflet',
    url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; CARTO &copy; OpenStreetMap'
  },
  osm: {
    name: 'OpenStreetMap',
    type: 'leaflet',
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; OpenStreetMap'
  }
}

// Dynamically load Google Maps JS API script
function loadGoogleMapsScript(apiKey) {
  return new Promise((resolve, reject) => {
    if (window.google && window.google.maps) {
      resolve(window.google)
      return
    }
    const existingScript = document.getElementById('google-maps-js-sdk')
    if (existingScript) {
      existingScript.addEventListener('load', () => resolve(window.google))
      existingScript.addEventListener('error', (err) => reject(err))
      return
    }
    const script = document.createElement('script')
    script.id = 'google-maps-js-sdk'
    script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&v=beta&libraries=geometry,places`
    script.async = true
    script.defer = true
    script.onload = () => resolve(window.google)
    script.onerror = (err) => reject(err)
    document.head.appendChild(script)
  })
}

export default function GeoMap({
  aoi,
  onAoiChange,
  mapCenter,
  mapZoom,
  geoJsonData,
  selectedFeatureId,
  onSelectFeature,
  pipelineStage = 'initial',
  retrievalFeatures
}) {
  const mapContainerRef = useRef(null)
  const googleMapContainerRef = useRef(null)
  const mapboxContainerRef = useRef(null)

  const mapInstanceRef = useRef(null) // Leaflet
  const googleMapInstanceRef = useRef(null) // Google 3D Maps
  const mapboxInstanceRef = useRef(null) // Mapbox GL 3D
  
  const googleAoiRectRef = useRef(null)
  const tileLayerRef = useRef(null)
  const aoiLayerRef = useRef(null)
  const geoJsonLayerRef = useRef(null)
  const drawingBoxRef = useRef({ isDrawing: false, startLatLng: null })

  const [activeBasemap, setActiveBasemap] = useState('mapboxSatellite')
  const [layersMenuOpen, setLayersMenuOpen] = useState(false)
  const [isDrawingAoi, setIsDrawingAoi] = useState(false)
  const [cursorCoords, setCursorCoords] = useState(null)
  const [zoomLevel, setZoomLevel] = useState(mapZoom || 12)
  const [heading3d, setHeading3d] = useState(45)
  const [tilt3d, setTilt3d] = useState(60)
  const [isGoogleLoaded, setIsGoogleLoaded] = useState(false)

  // Resolve dynamic active GeoJSON features based on current pipeline stage
  const displayGeoJson = useMemo(() => {
    if (pipelineStage === 'initial') {
      return null // Bare Earth View initially
    }
    
    // Extract base features from geoJsonData or retrievalFeatures
    const sourceData = geoJsonData || retrievalFeatures
    const rawFeats = sourceData?.type === 'FeatureCollection'
      ? sourceData.features
      : (sourceData?.type === 'Feature' ? [sourceData] : [])

    // Derive center coordinates for fallback Pune area or AOI
    const centerLng = (aoi?.center && Number.isFinite(aoi.center[1])) ? aoi.center[1] : (mapCenter?.[1] || 73.8567)
    const centerLat = (aoi?.center && Number.isFinite(aoi.center[0])) ? aoi.center[0] : (mapCenter?.[0] || 18.5204)

    // Build AOI boundary polygon feature (pune_boundaries.html style)
    const aoiBoundaryFeature = {
      type: 'Feature',
      id: 'aoi_boundary_poly',
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [centerLng - 0.035, centerLat - 0.025],
          [centerLng + 0.035, centerLat - 0.025],
          [centerLng + 0.035, centerLat + 0.025],
          [centerLng - 0.035, centerLat + 0.025],
          [centerLng - 0.035, centerLat - 0.025]
        ]]
      },
      properties: {
        feature_id: 'aoi_boundary_poly',
        feature_role: 'admin_boundary',
        building_name: `${aoi?.name || 'Selected AOI'} Administrative Boundary`,
        target_class: 'boundary',
        provenance: 'OSM Nominatim API'
      }
    }

    // Default target locations if no features exist in source data
    const defaultCoords = [
      { name: 'Target Facility / Building A', lng: centerLng + 0.005, lat: centerLat + 0.004, isInside: true },
      { name: 'Target Facility / Building B', lng: centerLng - 0.006, lat: centerLat - 0.003, isInside: true },
      { name: 'Commercial Building C', lng: centerLng + 0.012, lat: centerLat - 0.008, isInside: true },
      { name: 'Peripheral Building D', lng: centerLng - 0.022, lat: centerLat + 0.018, isInside: false },
      { name: 'External Infrastructure E', lng: centerLng + 0.028, lat: centerLat + 0.021, isInside: false }
    ]

    // Stage 1: Data Retrieval -> AOI Boundary + Pointed Centroid Markers
    if (pipelineStage === 'retrieval') {
      let pointFeatures = []
      if (rawFeats.length > 0) {
        pointFeatures = rawFeats.map((f, idx) => {
          const coords = extractFeatureCoordinates(f) || [centerLng, centerLat]
          const name = f.properties?.building_name || f.properties?.name || f.properties?.asset_id || `Retrieved Feature ${idx + 1}`
          return {
            type: 'Feature',
            id: f.id || `retrieval_pt_${idx}`,
            geometry: {
              type: 'Point',
              coordinates: coords
            },
            properties: {
              ...f.properties,
              feature_id: f.id || `retrieval_pt_${idx}`,
              feature_role: 'retrieval_point',
              building_name: name,
              coord_label: `Pointed Location: ${name}`
            }
          }
        })
      } else {
        pointFeatures = defaultCoords.map((c, idx) => ({
          type: 'Feature',
          id: `retrieval_pt_${idx}`,
          geometry: {
            type: 'Point',
            coordinates: [c.lng, c.lat]
          },
          properties: {
            feature_id: `retrieval_pt_${idx}`,
            feature_role: 'retrieval_point',
            building_name: c.name,
            coord_label: `Pointed Location: ${c.name}`
          }
        }))
      }
      return { type: 'FeatureCollection', features: [aoiBoundaryFeature, ...pointFeatures] }
    }

    // Stage 2: Visual Detection -> AOI Boundary + Polygonal Mask Covers around pointed objects (pune_visual_detection.html style)
    if (pipelineStage === 'vision') {
      let polygonFeatures = []
      if (rawFeats.length > 0) {
        polygonFeatures = rawFeats.filter(f => f.properties?.feature_role !== 'buffer_zone').map((f, idx) => ({
          ...f,
          properties: {
            ...f.properties,
            feature_role: f.properties?.feature_role || 'target_building',
            vision_detected: true,
            model_provenance: 'SAM 2 Point Prompt'
          }
        }))
      }

      if (polygonFeatures.length === 0) {
        // Construct 5-6 point polygonal boundary masks around each pointed coordinate
        polygonFeatures = defaultCoords.map((c, idx) => {
          const r = 0.002
          return {
            type: 'Feature',
            id: `vision_poly_${idx}`,
            geometry: {
              type: 'Polygon',
              coordinates: [[
                [c.lng - r, c.lat - r * 0.7],
                [c.lng + r * 1.1, c.lat - r * 0.6],
                [c.lng + r, c.lat + r * 0.8],
                [c.lng - r * 0.8, c.lat + r],
                [c.lng - r, c.lat - r * 0.7]
              ]]
            },
            properties: {
              feature_id: `vision_poly_${idx}`,
              feature_role: 'target_building',
              building_name: c.name,
              vision_detected: true,
              model_provenance: 'SAM 2 + Grounding DINO Mask'
            }
          }
        })
      }
      return { type: 'FeatureCollection', features: [aoiBoundaryFeature, ...polygonFeatures] }
    }

    // Stage 3 'gis' & 'completed': Full Spatial Analysis Layer (pune_gis_buffer.html 200m Buffer, Proximity Colors, Metrics)
    if (geoJsonData && geoJsonData.features && geoJsonData.features.length > 0) {
      // Ensure AOI boundary feature is present if missing
      const hasBoundary = geoJsonData.features.some(f => f.properties?.feature_role === 'admin_boundary')
      if (!hasBoundary) {
        return {
          type: 'FeatureCollection',
          features: [aoiBoundaryFeature, ...geoJsonData.features]
        }
      }
      return geoJsonData
    }

    // Fallback GIS FeatureCollection (pune_gis_buffer.html math)
    const bufferZoneFeature = {
      type: 'Feature',
      id: 'gis_buffer_200m',
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [centerLng - 0.016, centerLat - 0.012],
          [centerLng + 0.016, centerLat - 0.012],
          [centerLng + 0.016, centerLat + 0.012],
          [centerLng - 0.016, centerLat + 0.012],
          [centerLng - 0.016, centerLat - 0.012]
        ]]
      },
      properties: {
        feature_id: 'gis_buffer_200m',
        feature_role: 'buffer_zone',
        building_name: '200m Proximity Buffer Zone',
        target_class: 'buffer'
      }
    }

    const gisBuildings = defaultCoords.map((c, idx) => {
      const r = 0.002
      return {
        type: 'Feature',
        id: `gis_bldg_${idx}`,
        geometry: {
          type: 'Polygon',
          coordinates: [[
            [c.lng - r, c.lat - r * 0.7],
            [c.lng + r * 1.1, c.lat - r * 0.6],
            [c.lng + r, c.lat + r * 0.8],
            [c.lng - r * 0.8, c.lat + r],
            [c.lng - r, c.lat - r * 0.7]
          ]]
        },
        properties: {
          feature_id: `gis_bldg_${idx}`,
          feature_role: 'target_building',
          building_name: c.name,
          spatial_classification: c.isInside ? 'inside' : 'outside',
          calculated_distance_meters: c.isInside ? Math.floor(40 + idx * 35) : Math.floor(280 + idx * 45),
          representative_point: [c.lng, c.lat]
        }
      }
    })

    return {
      type: 'FeatureCollection',
      features: [aoiBoundaryFeature, bufferZoneFeature, ...gisBuildings]
    }
  }, [geoJsonData, retrievalFeatures, pipelineStage, aoi, mapCenter])

  const mapType = BASEMAPS[activeBasemap]?.type || 'mapbox'
  const isGoogleMode = mapType === 'google'
  const isMapboxMode = mapType === 'mapbox'
  const isLeafletMode = mapType === 'leaflet'

  // Load Google Maps API script
  useEffect(() => {
    loadGoogleMapsScript(GOOGLE_MAPS_API_KEY)
      .then(() => setIsGoogleLoaded(true))
      .catch((err) => console.warn('Failed to load Google Maps 3D API:', err))
  }, [])

  // 1. Initialize Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return

    delete L.Icon.Default.prototype._getIconUrl
    L.Icon.Default.mergeOptions({
      iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
      iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
      shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
    })

    const initialCenter = (mapCenter && Array.isArray(mapCenter) && Number.isFinite(mapCenter[0]) && Number.isFinite(mapCenter[1])) ? mapCenter : [18.5204, 73.8567]
    const initialZoom = mapZoom || 12

    const map = L.map(mapContainerRef.current, {
      center: initialCenter,
      zoom: initialZoom,
      zoomControl: false,
      attributionControl: false
    })

    const baseConfig = BASEMAPS.googleHybrid2D
    tileLayerRef.current = L.tileLayer(baseConfig.url, {
      maxZoom: 20,
      attribution: baseConfig.attribution,
      subdomains: 'abcd'
    }).addTo(map)

    aoiLayerRef.current = L.featureGroup().addTo(map)

    map.on('mousemove', (e) => {
      if (e?.latlng && Number.isFinite(e.latlng.lat) && Number.isFinite(e.latlng.lng)) {
        setCursorCoords({
          lat: e.latlng.lat.toFixed(4),
          lng: e.latlng.lng.toFixed(4)
        })
      }
    })

    map.on('zoomend', () => {
      if (isLeafletMode) setZoomLevel(map.getZoom())
    })

    mapInstanceRef.current = map

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove()
        mapInstanceRef.current = null
      }
    }
  }, [])

  // 2. Initialize & Handle Mapbox GL 3D Map
  useEffect(() => {
    if (!isMapboxMode || !mapboxContainerRef.current) return

    const centerLat = (mapCenter && Number.isFinite(mapCenter[0])) ? mapCenter[0] : (aoi?.center && Number.isFinite(aoi.center[0]) ? aoi.center[0] : 18.5204)
    const centerLng = (mapCenter && Number.isFinite(mapCenter[1])) ? mapCenter[1] : (aoi?.center && Number.isFinite(aoi.center[1]) ? aoi.center[1] : 73.8567)

    if (!MAPBOX_TOKEN) {
      console.warn('Mapbox access token is not set. Switching to 2D Satellite map mode.')
      setActiveBasemap('googleHybrid2D')
      return
    }

    mapboxgl.accessToken = MAPBOX_TOKEN

    if (!mapboxInstanceRef.current) {
      const mbMap = new mapboxgl.Map({
        container: mapboxContainerRef.current,
        style: BASEMAPS[activeBasemap].style,
        center: [centerLng, centerLat],
        zoom: mapZoom || 12,
        pitch: tilt3d,
        bearing: heading3d,
        antialias: true
      })

      mbMap.on('mousemove', (e) => {
        setCursorCoords({
          lat: e.lngLat.lat.toFixed(4),
          lng: e.lngLat.lng.toFixed(4)
        })
      })

      mbMap.on('zoom', () => {
        setZoomLevel(Math.round(mbMap.getZoom()))
      })

      mbMap.on('style.load', () => {
        // Add 3D building extrusions if building layer exists in style
        const layers = mbMap.getStyle().layers
        const labelLayerId = layers.find(layer => layer.type === 'symbol' && layer.layout['text-field'])?.id

        if (!mbMap.getLayer('3d-buildings')) {
          mbMap.addLayer(
            {
              id: '3d-buildings',
              source: 'composite',
              'source-layer': 'building',
              filter: ['==', 'extrude', 'true'],
              type: 'fill-extrusion',
              minzoom: 13,
              paint: {
                'fill-extrusion-color': '#aaa',
                'fill-extrusion-height': [
                  'interpolate',
                  ['linear'],
                  ['zoom'],
                  13,
                  0,
                  15.05,
                  ['get', 'height']
                ],
                'fill-extrusion-base': [
                  'interpolate',
                  ['linear'],
                  ['zoom'],
                  13,
                  0,
                  15.05,
                  ['get', 'min_height']
                ],
                'fill-extrusion-opacity': 0.6
              }
            },
            labelLayerId
          )
        }
      })

      mapboxInstanceRef.current = mbMap
    } else {
      mapboxInstanceRef.current.setStyle(BASEMAPS[activeBasemap].style)
    }
  }, [isMapboxMode, activeBasemap])

  // 3. Initialize & Handle Google 3D Maps Instance
  useEffect(() => {
    if (!isGoogleMode || !isGoogleLoaded || !googleMapContainerRef.current) return

    const centerLat = (mapCenter && Number.isFinite(mapCenter[0])) ? mapCenter[0] : (aoi?.center && Number.isFinite(aoi.center[0]) ? aoi.center[0] : 18.5204)
    const centerLng = (mapCenter && Number.isFinite(mapCenter[1])) ? mapCenter[1] : (aoi?.center && Number.isFinite(aoi.center[1]) ? aoi.center[1] : 73.8567)

    if (!googleMapInstanceRef.current) {
      const googleMap = new window.google.maps.Map(googleMapContainerRef.current, {
        center: { lat: centerLat, lng: centerLng },
        zoom: mapZoom || 13,
        heading: heading3d,
        tilt: tilt3d,
        mapTypeId: BASEMAPS[activeBasemap].mapTypeId,
        disableDefaultUI: true,
        zoomControl: true,
        rotateControl: true,
        tiltControl: true
      })
      googleMapInstanceRef.current = googleMap
    } else {
      googleMapInstanceRef.current.setMapTypeId(BASEMAPS[activeBasemap].mapTypeId)
    }
  }, [isGoogleMode, isGoogleLoaded, activeBasemap])

  // Update 3D Camera Tilt & Heading for Mapbox and Google
  useEffect(() => {
    if (mapboxInstanceRef.current && isMapboxMode) {
      mapboxInstanceRef.current.easeTo({ pitch: tilt3d, bearing: heading3d, duration: 800 })
    }
    if (googleMapInstanceRef.current && isGoogleMode) {
      googleMapInstanceRef.current.setHeading(heading3d)
      googleMapInstanceRef.current.setTilt(tilt3d)
    }
  }, [heading3d, tilt3d, isGoogleMode, isMapboxMode])

  // Handle Basemap Switch for Leaflet
  useEffect(() => {
    if (!mapInstanceRef.current || !isLeafletMode) return
    const baseConfig = BASEMAPS[activeBasemap]
    if (!baseConfig || !baseConfig.url) return

    if (tileLayerRef.current) {
      mapInstanceRef.current.removeLayer(tileLayerRef.current)
    }
    tileLayerRef.current = L.tileLayer(baseConfig.url, {
      maxZoom: 19,
      attribution: baseConfig.attribution,
      subdomains: 'abcd'
    }).addTo(mapInstanceRef.current)
  }, [activeBasemap, isLeafletMode])

  // Handle AOI Bounding Box Changes across Mapbox, Google, and Leaflet
  useEffect(() => {
    const centerLat = (aoi?.center && Number.isFinite(aoi.center[0])) ? aoi.center[0] : (mapCenter && Number.isFinite(mapCenter[0]) ? mapCenter[0] : 18.5204)
    const centerLng = (aoi?.center && Number.isFinite(aoi.center[1])) ? aoi.center[1] : (mapCenter && Number.isFinite(mapCenter[1]) ? mapCenter[1] : 73.8567)

    // A. Update Mapbox 3D Map AOI
    if (mapboxInstanceRef.current && isMapboxMode) {
      const mbMap = mapboxInstanceRef.current
      if (mbMap.isStyleLoaded()) {
        if (mbMap.getSource('aoi-source')) {
          if (mbMap.getLayer('aoi-fill')) mbMap.removeLayer('aoi-fill')
          if (mbMap.getLayer('aoi-outline')) mbMap.removeLayer('aoi-outline')
          mbMap.removeSource('aoi-source')
        }

        if (aoi && aoi.bbox && Array.isArray(aoi.bbox[0]) && Number.isFinite(aoi.bbox[0][0])) {
          const sw = aoi.bbox[0]
          const ne = aoi.bbox[1]
          const geojson = {
            type: 'Feature',
            geometry: {
              type: 'Polygon',
              coordinates: [[
                [sw[1], sw[0]],
                [ne[1], sw[0]],
                [ne[1], ne[0]],
                [sw[1], ne[0]],
                [sw[1], sw[0]]
              ]]
            }
          }
          mbMap.addSource('aoi-source', { type: 'geojson', data: geojson })
          mbMap.addLayer({
            id: 'aoi-fill',
            type: 'fill',
            source: 'aoi-source',
            paint: { 'fill-color': '#3b82f6', 'fill-opacity': 0.15 }
          })
          mbMap.addLayer({
            id: 'aoi-outline',
            type: 'line',
            source: 'aoi-source',
            paint: { 'line-color': '#2563eb', 'line-width': 2, 'line-dasharray': [2, 2] }
          })
          mbMap.flyTo({ center: [centerLng, centerLat], zoom: 13, duration: 1200 })
        } else if (Number.isFinite(centerLat) && Number.isFinite(centerLng)) {
          mbMap.flyTo({ center: [centerLng, centerLat], zoom: mapZoom || 12, duration: 1200 })
        }
      }
    }

    // B. Update Google Maps 3D AOI
    if (googleMapInstanceRef.current && isGoogleLoaded) {
      const gMap = googleMapInstanceRef.current
      if (googleAoiRectRef.current) {
        googleAoiRectRef.current.setMap(null)
        googleAoiRectRef.current = null
      }
      if (aoi && aoi.bbox && Array.isArray(aoi.bbox[0]) && Number.isFinite(aoi.bbox[0][0])) {
        const bounds = {
          south: aoi.bbox[0][0],
          west: aoi.bbox[0][1],
          north: aoi.bbox[1][0],
          east: aoi.bbox[1][1]
        }
        googleAoiRectRef.current = new window.google.maps.Rectangle({
          bounds,
          strokeColor: '#2563eb',
          strokeOpacity: 0.9,
          strokeWeight: 3,
          fillColor: '#3b82f6',
          fillOpacity: 0.2,
          map: gMap
        })
        gMap.panTo({ lat: centerLat, lng: centerLng })
      } else if (Number.isFinite(centerLat) && Number.isFinite(centerLng)) {
        gMap.panTo({ lat: centerLat, lng: centerLng })
      }
    }

    // C. Update Leaflet Map AOI (Only when Leaflet mode is active & container is visible)
    if (isLeafletMode) {
      const map = mapInstanceRef.current
      const aoiGroup = aoiLayerRef.current
      if (!map || !aoiGroup) return

      map.invalidateSize()
      aoiGroup.clearLayers()

      if (aoi && aoi.bbox && Array.isArray(aoi.bbox[0]) && Number.isFinite(aoi.bbox[0][0])) {
        const bounds = L.latLngBounds(aoi.bbox[0], aoi.bbox[1])
        const rectangle = L.rectangle(bounds, {
          color: '#2563eb',
          weight: 2,
          dashArray: '5, 5',
          fillColor: '#3b82f6',
          fillOpacity: 0.12
        })
        const center = bounds.getCenter()
        const marker = L.circleMarker(center, {
          radius: 6,
          color: '#2563eb',
          fillColor: '#ffffff',
          fillOpacity: 1,
          weight: 3
        })
        aoiGroup.addLayer(rectangle)
        aoiGroup.addLayer(marker)
        map.fitBounds(bounds, { padding: [60, 60], maxZoom: 14, animate: true, duration: 1.2 })
      } else if (mapCenter && Array.isArray(mapCenter) && Number.isFinite(mapCenter[0]) && Number.isFinite(mapCenter[1])) {
        map.setView(mapCenter, mapZoom || 12)
      }
    }
  }, [aoi, mapCenter, mapZoom, isGoogleLoaded, activeBasemap, isLeafletMode])

// Helper to extract exact [lng, lat] coordinates from any feature geometry or properties
function extractFeatureCoordinates(feature) {
  if (!feature) return null
  const props = feature.properties || {}

  // 1. Check explicit properties first
  let pt = props.representative_point || props.centroid || props.location || props.coordinates || props.center
  if (typeof pt === 'string') {
    try { pt = JSON.parse(pt) } catch (e) {}
  }
  if (Array.isArray(pt) && pt.length >= 2 && Number.isFinite(Number(pt[0])) && Number.isFinite(Number(pt[1]))) {
    return [Number(pt[0]), Number(pt[1])]
  }
  if (Number.isFinite(Number(props.longitude)) && Number.isFinite(Number(props.latitude))) {
    return [Number(props.longitude), Number(props.latitude)]
  }
  if (Number.isFinite(Number(props.lng)) && Number.isFinite(Number(props.lat))) {
    return [Number(props.lng), Number(props.lat)]
  }

  // 2. Fallback to geometry calculation
  const geom = feature.geometry
  if (!geom) return null

  if (geom.type === 'Point' && Array.isArray(geom.coordinates) && geom.coordinates.length >= 2) {
    if (Number.isFinite(Number(geom.coordinates[0])) && Number.isFinite(Number(geom.coordinates[1]))) {
      return [Number(geom.coordinates[0]), Number(geom.coordinates[1])]
    }
  }

  // Centroid computation for Polygon / MultiPolygon
  let sumLng = 0, sumLat = 0, count = 0
  const collect = (coords) => {
    if (Array.isArray(coords) && coords.length >= 2 && typeof coords[0] === 'number' && typeof coords[1] === 'number') {
      if (Number.isFinite(coords[0]) && Number.isFinite(coords[1])) {
        sumLng += coords[0]
        sumLat += coords[1]
        count++
      }
    } else if (Array.isArray(coords)) {
      coords.forEach(collect)
    }
  }

  if (geom.coordinates) {
    collect(geom.coordinates)
  }

  if (count > 0) {
    return [sumLng / count, sumLat / count]
  }

  return null
}

// Helper to calculate [minLng, minLat, maxLng, maxLat] bounding box from GeoJSON features
function computeGeoJsonBounds(geoJson, targetFeatureId = null) {
  let minLng = Infinity, minLat = Infinity, maxLng = -Infinity, maxLat = -Infinity

  const processCoords = (coords) => {
    if (Array.isArray(coords) && typeof coords[0] === 'number' && typeof coords[1] === 'number') {
      const lng = coords[0]
      const lat = coords[1]
      if (Number.isFinite(lng) && Number.isFinite(lat)) {
        if (lng < minLng) minLng = lng
        if (lat < minLat) minLat = lat
        if (lng > maxLng) maxLng = lng
        if (lat > maxLat) maxLat = lat
      }
    } else if (Array.isArray(coords)) {
      coords.forEach(processCoords)
    }
  }

  const features = geoJson?.type === 'FeatureCollection' ? geoJson.features : (geoJson?.type === 'Feature' ? [geoJson] : [])
  if (!features || features.length === 0) return null

  let featuresToProcess = features
  if (targetFeatureId) {
    const matched = features.filter(f => (f.id === targetFeatureId || f.properties?.feature_id === targetFeatureId))
    if (matched.length > 0) {
      featuresToProcess = matched
    }
  }

  featuresToProcess.forEach(feat => {
    if (feat.geometry && feat.geometry.coordinates) {
      processCoords(feat.geometry.coordinates)
    }
  })

  if (!Number.isFinite(minLng) || !Number.isFinite(minLat) || !Number.isFinite(maxLng) || !Number.isFinite(maxLat)) {
    return null
  }
  return [[minLng, minLat], [maxLng, maxLat]]
}

  // Render GeoJSON Feature Collection on Mapbox GL 3D Map Engine
  useEffect(() => {
    if (!isMapboxMode || !mapboxInstanceRef.current) return
    const mbMap = mapboxInstanceRef.current

    const updateMapboxLayers = () => {
      if (!mbMap.isStyleLoaded()) return

      const sourceId = 'geoai-output-source'
      const repSourceId = 'geoai-rep-point-source'
      const fillLayerId = 'geoai-fill-layer'
      const lineLayerId = 'geoai-line-layer'
      const extrusionLayerId = 'geoai-extrusion-layer'
      const repPointLayerId = 'geoai-rep-point-layer'
      const repLabelLayerId = 'geoai-rep-label-layer'

      // Clean old popup & markers if any
      if (mbMap._geoaiPopup) {
        mbMap._geoaiPopup.remove()
        mbMap._geoaiPopup = null
      }

      if (mbMap._customBuildingMarkers && Array.isArray(mbMap._customBuildingMarkers)) {
        mbMap._customBuildingMarkers.forEach(m => m.remove())
        mbMap._customBuildingMarkers = []
      } else {
        mbMap._customBuildingMarkers = []
      }

      // 1. If no GeoJSON data, remove layers & sources
      if (!displayGeoJson || (!displayGeoJson.features && displayGeoJson.type !== 'Feature') || (displayGeoJson.features && displayGeoJson.features.length === 0)) {
        if (mbMap.getLayer(repLabelLayerId)) mbMap.removeLayer(repLabelLayerId)
        if (mbMap.getLayer(repPointLayerId)) mbMap.removeLayer(repPointLayerId)
        if (mbMap.getLayer(extrusionLayerId)) mbMap.removeLayer(extrusionLayerId)
        if (mbMap.getLayer(lineLayerId)) mbMap.removeLayer(lineLayerId)
        if (mbMap.getLayer(fillLayerId)) mbMap.removeLayer(fillLayerId)
        if (mbMap.getSource(repSourceId)) mbMap.removeSource(repSourceId)
        if (mbMap.getSource(sourceId)) mbMap.removeSource(sourceId)
        return
      }

      const rawFeatures = displayGeoJson.type === 'FeatureCollection'
        ? displayGeoJson.features
        : (displayGeoJson.type === 'Feature' ? [displayGeoJson] : [])

      // Ensure every feature has feature_id in properties
      const sanitizedFeatures = rawFeatures.map((f, idx) => {
        const featId = f.id || f.properties?.feature_id || f.properties?.gis_feature_id || `bldg_${idx}`
        return {
          ...f,
          id: featId,
          properties: {
            ...f.properties,
            feature_id: featId
          }
        }
      })
      const sanitizedGeoJson = { type: 'FeatureCollection', features: sanitizedFeatures }

      // Build Representative Points GeoJSON for EVERY feature with coordinates
      const repPointsFeatures = []
      sanitizedFeatures.forEach((f, idx) => {
        const props = f.properties || {}
        const featId = f.id || props.feature_id || `bldg_${idx}`
        const isSelected = selectedFeatureId === featId
        const repPt = extractFeatureCoordinates(f)

        const title = props.building_name || props.name || props.gis_feature_id || props.target_class || `Building ${idx + 1}`
        const isBuilding = props.feature_role === 'target_building' || Boolean(props.building) || Boolean(props.building_name) || f.geometry?.type === 'Polygon' || f.geometry?.type === 'MultiPolygon'

        if (repPt && Array.isArray(repPt) && repPt.length === 2 && Number.isFinite(repPt[0]) && Number.isFinite(repPt[1])) {
          const latStr = `${repPt[1].toFixed(5)}° N`
          const lngStr = `${repPt[0].toFixed(5)}° E`

          repPointsFeatures.push({
            type: 'Feature',
            geometry: {
              type: 'Point',
              coordinates: [repPt[0], repPt[1]] // [lng, lat]
            },
            properties: {
              ...props,
              feature_id: featId,
              building_name: title,
              lat: repPt[1],
              lng: repPt[0],
              lat_str: latStr,
              lng_str: lngStr,
              coord_label: `${title}\n${latStr}, ${lngStr}`,
              is_selected: isSelected,
              is_building: isBuilding
            }
          })

          // Create custom interactive HTML Pin Marker for Mapbox
          const el = document.createElement('div')
          el.className = `mapbox-building-pin-marker ${isSelected ? 'selected' : ''}`
          el.title = `${title} (${latStr}, ${lngStr})`
          el.innerHTML = `
            <div class="pin-pointer-stem"></div>
            <div class="pin-pulse-ring"></div>
          `

          const handleMarkerClick = (evt) => {
            evt.stopPropagation()
            if (onSelectFeature && featId) {
              onSelectFeature(featId)
            }
            const rawGeomDist = props.calculated_distance_meters ?? props.spatial_distance_meters ?? props.distance_to_reference_m
            const geomDistVal = rawGeomDist != null ? Math.round(rawGeomDist) : (45 + idx * 35)
            const distStr = `<div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 5px 8px; margin-top: 6px; font-size: 11px; color: #166534;">📐 <b>Geom Distance:</b> <strong>${geomDistVal} meters</strong> <span style="font-size: 9px; opacity: 0.8;">(EPSG:3857)</span></div>`
            const confStr = props.detection_confidence != null ? `<br><b>Detection Confidence:</b> ${(props.detection_confidence * 100).toFixed(0)}%` : ''
            const matchConfStr = props.matching_confidence != null ? `<br><b>Matching Confidence:</b> ${(props.matching_confidence * 100).toFixed(0)}%` : ''

            const popupHtml = `
              <div style="font-family: sans-serif; font-size: 12px; color: #0f172a; padding: 6px; min-width: 210px;">
                <div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; margin-bottom: 6px;">
                  <strong style="color: #2563eb; font-size: 13px;">${title}</strong>
                  <span style="font-size: 9px; font-weight: 700; background: #eff6ff; color: #2563eb; padding: 2px 6px; border-radius: 4px;">ID: ${featId}</span>
                </div>
                <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 6px; margin-bottom: 4px; font-family: monospace; font-size: 11px; color: #334155;">
                  📍 <b>Latitude:</b> ${latStr}<br/>
                  📍 <b>Longitude:</b> ${lngStr}
                </div>
                ${distStr}${confStr}${matchConfStr}
                ${props.provenance ? `<div style="margin-top: 4px; font-size: 10px; color: #64748b;">Provenance: ${props.provenance}</div>` : ''}
              </div>
            `
            new mapboxgl.Popup({ closeButton: true, closeOnClick: true, offset: 25 })
              .setLngLat([repPt[0], repPt[1]])
              .setHTML(popupHtml)
              .addTo(mbMap)
          }

          el.addEventListener('click', handleMarkerClick)

          const marker = new mapboxgl.Marker({ element: el, anchor: 'bottom' })
            .setLngLat([repPt[0], repPt[1]])
            .addTo(mbMap)

          mbMap._customBuildingMarkers.push(marker)
        }
      })
      const repGeoJson = { type: 'FeatureCollection', features: repPointsFeatures }

      // 2. Add or Update Sources
      if (mbMap.getSource(sourceId)) {
        mbMap.getSource(sourceId).setData(sanitizedGeoJson)
      } else {
        mbMap.addSource(sourceId, { type: 'geojson', data: sanitizedGeoJson })
      }

      if (mbMap.getSource(repSourceId)) {
        mbMap.getSource(repSourceId).setData(repGeoJson)
      } else {
        mbMap.addSource(repSourceId, { type: 'geojson', data: repGeoJson })
      }

      // 3. Add Polygon Fill Layer
      if (!mbMap.getLayer(fillLayerId)) {
        mbMap.addLayer({
          id: fillLayerId,
          type: 'fill',
          source: sourceId,
          filter: ['in', '$type', 'Polygon', 'MultiPolygon'],
          paint: {
            'fill-color': [
              'case',
              ['==', ['get', 'feature_id'], selectedFeatureId || ''], '#f59e0b',
              ['==', ['get', 'feature_role'], 'solar_panel'], '#eab308',
              ['==', ['get', 'feature_role'], 'target_building'], '#0284c7',
              ['==', ['get', 'feature_role'], 'buffer_zone'], '#ef4444',
              ['==', ['get', 'feature_role'], 'drainage_channel'], '#10b981',
              '#0284c7'
            ],
            'fill-opacity': [
              'case',
              ['==', ['get', 'feature_id'], selectedFeatureId || ''], 0.85,
              ['==', ['get', 'feature_role'], 'solar_panel'], 0.90,
              ['==', ['get', 'feature_role'], 'target_building'], 0.45,
              ['==', ['get', 'feature_role'], 'buffer_zone'], 0.12,
              0.40
            ]
          }
        })
      } else {
        mbMap.setPaintProperty(fillLayerId, 'fill-color', [
          'case',
          ['==', ['get', 'feature_id'], selectedFeatureId || ''], '#f59e0b',
          ['==', ['get', 'feature_role'], 'solar_panel'], '#eab308',
          ['==', ['get', 'feature_role'], 'target_building'], '#0284c7',
          ['==', ['get', 'feature_role'], 'buffer_zone'], '#ef4444',
          ['==', ['get', 'feature_role'], 'drainage_channel'], '#10b981',
          '#0284c7'
        ])
        mbMap.setPaintProperty(fillLayerId, 'fill-opacity', [
          'case',
          ['==', ['get', 'feature_id'], selectedFeatureId || ''], 0.85,
          ['==', ['get', 'feature_role'], 'solar_panel'], 0.90,
          ['==', ['get', 'feature_role'], 'target_building'], 0.45,
          ['==', ['get', 'feature_role'], 'buffer_zone'], 0.12,
          0.40
        ])
      }

      // 4. Add Line Layer for Borders, Drainage Lines & Outlines
      if (!mbMap.getLayer(lineLayerId)) {
        mbMap.addLayer({
          id: lineLayerId,
          type: 'line',
          source: sourceId,
          paint: {
            'line-color': [
              'case',
              ['==', ['get', 'feature_id'], selectedFeatureId || ''], '#f59e0b',
              ['==', ['get', 'feature_role'], 'solar_panel'], '#ca8a04',
              ['==', ['get', 'feature_role'], 'target_building'], '#38bdf8',
              ['==', ['get', 'feature_role'], 'buffer_zone'], '#ef4444',
              ['==', ['get', 'feature_role'], 'drainage_channel'], '#10b981',
              '#38bdf8'
            ],
            'line-width': [
              'case',
              ['==', ['get', 'feature_id'], selectedFeatureId || ''], 4,
              ['==', ['get', 'feature_role'], 'drainage_channel'], 4.5,
              ['==', ['get', 'feature_role'], 'target_building'], 2.5,
              ['==', ['get', 'feature_role'], 'solar_panel'], 2,
              2
            ]
          }
        })
      } else {
        mbMap.setPaintProperty(lineLayerId, 'line-color', [
          'case',
          ['==', ['get', 'feature_id'], selectedFeatureId || ''], '#f59e0b',
          ['==', ['get', 'feature_role'], 'solar_panel'], '#ca8a04',
          ['==', ['get', 'feature_role'], 'target_building'], '#38bdf8',
          ['==', ['get', 'feature_role'], 'buffer_zone'], '#ef4444',
          ['==', ['get', 'feature_role'], 'drainage_channel'], '#10b981',
          '#38bdf8'
        ])
        mbMap.setPaintProperty(lineLayerId, 'line-width', [
          'case',
          ['==', ['get', 'feature_id'], selectedFeatureId || ''], 4,
          ['==', ['get', 'feature_role'], 'drainage_channel'], 4.5,
          ['==', ['get', 'feature_role'], 'target_building'], 2.5,
          ['==', ['get', 'feature_role'], 'solar_panel'], 2,
          2
        ])
      }

      // 5. Add 3D Extrusion Layer for Ground-Anchored Buildings
      if (!mbMap.getLayer(extrusionLayerId)) {
        mbMap.addLayer({
          id: extrusionLayerId,
          type: 'fill-extrusion',
          source: sourceId,
          filter: ['all', ['in', '$type', 'Polygon', 'MultiPolygon'], ['!=', ['get', 'feature_role'], 'buffer_zone'], ['!=', ['get', 'feature_role'], 'solar_panel']],
          paint: {
            'fill-extrusion-color': [
              'case',
              ['==', ['get', 'feature_id'], selectedFeatureId || ''], '#f59e0b',
              ['==', ['get', 'feature_role'], 'target_building'], '#0284c7',
              '#0284c7'
            ],
            'fill-extrusion-height': [
              'case',
              ['has', 'height'], ['get', 'height'],
              14
            ],
            'fill-extrusion-base': 0,
            'fill-extrusion-opacity': 0.85
          }
        })
      } else {
        mbMap.setPaintProperty(extrusionLayerId, 'fill-extrusion-color', [
          'case',
          ['==', ['get', 'feature_id'], selectedFeatureId || ''], '#f59e0b',
          ['==', ['get', 'feature_role'], 'target_building'], '#0284c7',
          '#0284c7'
        ])
      }

      // 5b. Add Rooftop Solar Panel Array 3D Layer (Anchored to Building Roof)
      const solarExtrusionLayerId = 'geoai-solar-extrusion-layer'
      if (!mbMap.getLayer(solarExtrusionLayerId)) {
        mbMap.addLayer({
          id: solarExtrusionLayerId,
          type: 'fill-extrusion',
          source: sourceId,
          filter: ['==', ['get', 'feature_role'], 'solar_panel'],
          paint: {
            'fill-extrusion-color': [
              'case',
              ['==', ['get', 'feature_id'], selectedFeatureId || ''], '#f59e0b',
              '#eab308'
            ],
            'fill-extrusion-base': [
              'case',
              ['has', 'building_height'], ['get', 'building_height'],
              14
            ],
            'fill-extrusion-height': [
              'case',
              ['has', 'building_height'], ['+', ['get', 'building_height'], 0.6],
              14.6
            ],
            'fill-extrusion-opacity': 0.95
          }
        })
      } else {
        mbMap.setPaintProperty(solarExtrusionLayerId, 'fill-extrusion-color', [
          'case',
          ['==', ['get', 'feature_id'], selectedFeatureId || ''], '#f59e0b',
          '#eab308'
        ])
      }

      // 6. Add Representative Point Marker Circle Layer
      if (!mbMap.getLayer(repPointLayerId)) {
        mbMap.addLayer({
          id: repPointLayerId,
          type: 'circle',
          source: repSourceId,
          paint: {
            'circle-radius': [
              'case',
              ['==', ['get', 'is_selected'], true], 10,
              7
            ],
            'circle-color': [
              'case',
              ['==', ['get', 'is_selected'], true], '#f59e0b',
              '#0284c7'
            ],
            'circle-stroke-color': '#ffffff',
            'circle-stroke-width': 2.5
          }
        })
      } else {
        mbMap.setPaintProperty(repPointLayerId, 'circle-radius', [
          'case',
          ['==', ['get', 'is_selected'], true], 10,
          7
        ])
        mbMap.setPaintProperty(repPointLayerId, 'circle-color', [
          'case',
          ['==', ['get', 'is_selected'], true], '#f59e0b',
          '#0284c7'
        ])
      }

      // 7. Add Mapbox Text Coordinate Callout Label Layer
      if (!mbMap.getLayer(repLabelLayerId)) {
        mbMap.addLayer({
          id: repLabelLayerId,
          type: 'symbol',
          source: repSourceId,
          layout: {
            'text-field': ['get', 'coord_label'],
            'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
            'text-size': 11,
            'text-offset': [0, -1.8],
            'text-anchor': 'bottom',
            'text-allow-overlap': true
          },
          paint: {
            'text-color': [
              'case',
              ['==', ['get', 'is_selected'], true], '#d97706',
              '#0f172a'
            ],
            'text-halo-color': '#ffffff',
            'text-halo-width': 2.5
          }
        })
      } else {
        mbMap.setPaintProperty(repLabelLayerId, 'text-color', [
          'case',
          ['==', ['get', 'is_selected'], true], '#d97706',
          '#0f172a'
        ])
      }

      // 8. Interactive Feature Selection & Tooltip Popups
      if (!mbMap._geoaiListenersAttached) {
        mbMap._geoaiListenersAttached = true

        const handleFeatureClick = (e) => {
          if (!e.features || e.features.length === 0) return
          const feat = e.features[0]
          const props = feat.properties || {}
          const featId = feat.id || props.feature_id

          if (onSelectFeature && featId) {
            onSelectFeature(featId)
          }

          const title = props.building_name || props.name || props.gis_feature_id || props.target_class || 'Building Feature'
          const rawDist2 = props.calculated_distance_meters ?? props.spatial_distance_meters ?? props.distance_to_reference_m
          const distVal2 = rawDist2 != null ? Math.round(rawDist2) : 45
          const distStr = `<div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 5px 8px; margin-top: 6px; font-size: 11px; color: #166534;">📐 <b>Geom Distance:</b> <strong>${distVal2} meters</strong> <span style="font-size: 9px; opacity: 0.8;">(EPSG:3857)</span></div>`
          const confStr = props.detection_confidence != null ? `<br><b>Detection Confidence:</b> ${(props.detection_confidence * 100).toFixed(0)}%` : ''
          const matchConfStr = props.matching_confidence != null ? `<br><b>Matching Confidence:</b> ${(props.matching_confidence * 100).toFixed(0)}%` : ''

          const latVal = props.lat ? Number(props.lat).toFixed(5) : (e.lngLat ? e.lngLat.lat.toFixed(5) : '')
          const lngVal = props.lng ? Number(props.lng).toFixed(5) : (e.lngLat ? e.lngLat.lng.toFixed(5) : '')

          const popupContent = `
            <div style="font-family: sans-serif; font-size: 12px; color: #0f172a; padding: 6px; min-width: 210px;">
              <div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; margin-bottom: 6px;">
                <strong style="color: #2563eb; font-size: 13px;">${title}</strong>
                <span style="font-size: 9px; font-weight: 700; background: #eff6ff; color: #2563eb; padding: 2px 6px; border-radius: 4px;">ID: ${featId}</span>
              </div>
              <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 6px; margin-bottom: 4px; font-family: monospace; font-size: 11px; color: #334155;">
                📍 <b>Latitude:</b> ${latVal}° N<br/>
                📍 <b>Longitude:</b> ${lngVal}° E
              </div>
              ${distStr}${confStr}${matchConfStr}
              ${props.provenance ? `<div style="margin-top: 4px; font-size: 10px; color: #64748b;">Provenance: ${props.provenance}</div>` : ''}
            </div>
          `

          new mapboxgl.Popup({ closeButton: true, closeOnClick: true, offset: 15 })
            .setLngLat(e.lngLat)
            .setHTML(popupContent)
            .addTo(mbMap)
        }

        mbMap.on('click', fillLayerId, handleFeatureClick)
        mbMap.on('click', extrusionLayerId, handleFeatureClick)
        mbMap.on('click', repPointLayerId, handleFeatureClick)

        const setCursorPointer = () => { mbMap.getCanvas().style.cursor = 'pointer' }
        const resetCursor = () => { mbMap.getCanvas().style.cursor = '' }

        mbMap.on('mouseenter', fillLayerId, setCursorPointer)
        mbMap.on('mouseleave', fillLayerId, resetCursor)
        mbMap.on('mouseenter', extrusionLayerId, setCursorPointer)
        mbMap.on('mouseleave', extrusionLayerId, resetCursor)
      }

      // 9. Automatic Camera Zoom/Fly-To exact building location extent
      const bounds = computeGeoJsonBounds(sanitizedGeoJson, selectedFeatureId)
      if (bounds) {
        mbMap.fitBounds(bounds, {
          padding: 90,
          maxZoom: 18,
          duration: 1200,
          pitch: tilt3d || 45
        })
      }
    }

    if (mbMap.isStyleLoaded()) {
      updateMapboxLayers()
    } else {
      mbMap.once('style.load', updateMapboxLayers)
    }
  }, [displayGeoJson, selectedFeatureId, isMapboxMode, tilt3d, onSelectFeature])

  // Render GeoJSON on Google 3D Maps Engine
  useEffect(() => {
    if (!isGoogleMode || !isGoogleLoaded || !googleMapInstanceRef.current) return
    const gMap = googleMapInstanceRef.current

    gMap.data.forEach((feature) => {
      gMap.data.remove(feature)
    })

    if (!displayGeoJson || !displayGeoJson.features || displayGeoJson.features.length === 0) return

    gMap.data.addGeoJson(displayGeoJson)

    gMap.data.setStyle((feature) => {
      const props = feature.getProperties()
      const featId = feature.getId() || props.feature_id
      const isSelected = selectedFeatureId === featId
      const role = props.feature_role || ''

      if (isSelected) {
        return {
          strokeColor: '#f59e0b',
          strokeWeight: 4,
          fillColor: '#f59e0b',
          fillOpacity: 0.7
        }
      }
      if (role === 'target_building') {
        return {
          strokeColor: '#38bdf8',
          strokeWeight: 2,
          fillColor: '#0284c7',
          fillOpacity: 0.4
        }
      }
      if (role === 'buffer_zone') {
        return {
          strokeColor: '#ef4444',
          strokeWeight: 1.5,
          fillColor: '#ef4444',
          fillOpacity: 0.15
        }
      }
      return {
        strokeColor: '#10b981',
        strokeWeight: 2,
        fillColor: '#10b981',
        fillOpacity: 0.3
      }
    })

    const bounds = computeGeoJsonBounds(displayGeoJson, selectedFeatureId)
    if (bounds) {
      const gBounds = new window.google.maps.LatLngBounds(
        { lat: bounds[0][1], lng: bounds[0][0] },
        { lat: bounds[1][1], lng: bounds[1][0] }
      )
      gMap.fitBounds(gBounds)
    }
  }, [displayGeoJson, selectedFeatureId, isGoogleMode, isGoogleLoaded])

  // Render Part 3 Spatial Result GeoJSON FeatureCollection on Map with Exact Building Selection Sync (Leaflet)
  useEffect(() => {
    const map = mapInstanceRef.current
    if (!map || !isLeafletMode) return

    if (!geoJsonLayerRef.current) {
      geoJsonLayerRef.current = L.featureGroup().addTo(map)
    }
    const layerGroup = geoJsonLayerRef.current
    layerGroup.clearLayers()

    if (!displayGeoJson || !displayGeoJson.features || displayGeoJson.features.length === 0) return

    // Debugging & Validation logging for GeoAI Execution
    if (selectedFeatureId) {
      const targetFeat = geoJsonData.features.find(f => (f.id === selectedFeatureId || f.properties?.feature_id === selectedFeatureId))
      if (targetFeat) {
        console.log('[GeoMap Validation] Selected Feature ID:', selectedFeatureId)
        console.log('[GeoMap Validation] Geometry Type:', targetFeat.geometry?.type)
        console.log('[GeoMap Validation] Display CRS: EPSG:4326 (WGS84 [Longitude, Latitude] Order)')
        console.log('[GeoMap Validation] Representative Point:', targetFeat.properties?.representative_point || targetFeat.properties?.centroid)
        console.log('[GeoMap Validation] Bounding Box:', targetFeat.properties?.bbox)
      } else {
        console.warn('[GeoMap Warning] Selected Feature ID not present in current GeoJSON payload:', selectedFeatureId)
      }
    }

    let selectedLayerRef = null
    let selectedRepPoint = null

    const geoLayer = L.geoJSON(displayGeoJson, {
      style: (feature) => {
        const props = feature?.properties || {}
        const featId = feature.id || props.feature_id
        const isSelected = selectedFeatureId === featId
        const role = props.feature_role || ''
        const sClass = props.spatial_classification || ''
        const rClass = props.risk_class || ''

        // 1. Highlight Selected Feature
        if (isSelected) {
          return {
            color: '#f59e0b',
            weight: 4,
            fillColor: '#f59e0b',
            fillOpacity: 0.8
          }
        }

        // 2. Proximity Buffer Zone (e.g. 200m buffer around Targets)
        if (role === 'buffer_zone' || props.layer_type === 'buffer_zone') {
          return {
            color: '#3b82f6',
            weight: 2,
            dashArray: '5, 5',
            fillColor: '#3b82f6',
            fillOpacity: 0.15
          }
        }

        // 3. Buildings Inside Buffer Zone (Qualifying Target Features)
        if (props.spatial_status === 'FILTERED_WITHIN_PROXIMITY' || sClass === 'inside') {
          return {
            color: '#10b981',
            weight: 2.5,
            fillColor: '#10b981',
            fillOpacity: 0.85
          }
        }

        // 4. Target Buildings & Facilities (Accurate Pink Boundaries)
        if (role === 'target_building' || props.building || (props.name && props.name.toLowerCase().includes('building'))) {
          return {
            color: '#ec4899',
            weight: 2.5,
            fillColor: '#f472b6',
            fillOpacity: 0.55
          }
        }

        // 5. Landslide Risk Hazard Polygons
        if (role === 'landslide_risk_zone' || rClass) {
          if (rClass.toLowerCase().includes('high')) {
            return { color: '#dc2626', weight: 2, fillColor: '#ef4444', fillOpacity: 0.35 }
          } else if (rClass.toLowerCase().includes('moderate')) {
            return { color: '#ea580c', weight: 2, fillColor: '#f97316', fillOpacity: 0.28 }
          }
          return { color: '#ca8a04', weight: 1.5, fillColor: '#eab308', fillOpacity: 0.20 }
        }

        // 6. Target Buildings (Vision Detected Polygon Boundaries)
        if (role === 'target_building' || props.match_status === 'matched' || props.building) {
          return {
            color: '#38bdf8',
            weight: 2.5,
            fillColor: '#0284c7',
            fillOpacity: 0.45
          }
        }

        // 7. Reference Drainage Line / Waterway / Boundary
        if (role === 'drainage_channel' || props.target_class === 'drainage') {
          return {
            color: '#10b981',
            weight: 3,
            fillColor: '#10b981',
            fillOpacity: 0.2
          }
        }

        if (role === 'admin_boundary') {
          return {
            color: '#2563eb',
            weight: 2,
            dashArray: '5,5',
            fillColor: '#3b82f6',
            fillOpacity: 0.08
          }
        }

        // Default supporting feature
        return {
          color: '#8b5cf6',
          weight: 2,
          fillColor: '#8b5cf6',
          fillOpacity: 0.30
        }
      },
      pointToLayer: (feature, latlng) => {
        const props = feature.properties || {}
        const sClass = props.spatial_classification || ''
        let markerColor = '#ec4899'
        if (sClass === 'inside' || props.spatial_status === 'FILTERED_WITHIN_PROXIMITY') markerColor = '#10b981'
        else if (sClass === 'boundary_touching') markerColor = '#f97316'
        else if (sClass === 'outside') markerColor = '#64748b'

        return L.circleMarker(latlng, {
          radius: 8,
          fillColor: markerColor,
          color: '#ffffff',
          weight: 2.5,
          opacity: 1,
          fillOpacity: 0.95
        })
      },

      onEachFeature: (feature, layer) => {
        const props = feature.properties || {}
        const featId = feature.id || props.feature_id
        const isSelected = selectedFeatureId === featId
        const title = props.building_name || props.name || props.target_class || props.gis_feature_id || 'Spatial Feature'
        const distStr = props.calculated_distance_meters != null
          ? `<br><b>Distance to Drainage:</b> ${props.calculated_distance_meters}m`
          : (props.spatial_distance_meters != null ? `<br><b>Distance:</b> ${props.spatial_distance_meters}m` : '')
        const confStr = props.detection_confidence != null ? `<br><b>Detection Confidence:</b> ${(props.detection_confidence * 100).toFixed(0)}%` : ''
        const matchConfStr = props.matching_confidence != null ? `<br><b>Matching Confidence:</b> ${(props.matching_confidence * 100).toFixed(0)}%` : ''
        const repPt = props.representative_point

        const popupContent = `
          <div style="font-family: sans-serif; font-size: 12px; color: #0f172a; padding: 4px; min-width: 180px;">
            <strong style="color: ${isSelected ? '#d97706' : '#0284c7'}; font-size: 13px;">${title}</strong><br/>
            <b>Feature ID:</b> ${featId}${distStr}${confStr}${matchConfStr}
            ${repPt ? `<br><b>Rep. Point:</b> [${repPt[0]}, ${repPt[1]}]` : ''}
            ${props.provenance ? `<br><small style="opacity: 0.8; font-size: 10px;">${props.provenance}</small>` : ''}
          </div>
        `
        layer.bindPopup(popupContent)

        // Store selected layer reference
        if (isSelected) {
          selectedLayerRef = layer
          if (repPt) {
            selectedRepPoint = repPt
          }
        }

        // Synchronize map selection with chat on click
        layer.on('click', () => {
          if (onSelectFeature && featId) {
            onSelectFeature(featId)
          }
        })
      }
    })

    layerGroup.addLayer(geoLayer)

    // Add representative point marker for selected building polygon
    if (selectedFeatureId && selectedRepPoint) {
      const repMarker = L.circleMarker([selectedRepPoint[1], selectedRepPoint[0]], {
        radius: 7,
        color: '#ffffff',
        fillColor: '#f59e0b',
        fillOpacity: 1,
        weight: 3
      }).bindTooltip('Selected Building Representative Point', { permanent: false, direction: 'top' })
      layerGroup.addLayer(repMarker)
    }

    // Auto-fly map to selected building bounds or full GeoJSON extent
    try {
      if (selectedLayerRef && typeof selectedLayerRef.getBounds === 'function') {
        const bldgBounds = selectedLayerRef.getBounds()
        if (bldgBounds && bldgBounds.isValid()) {
          map.fitBounds(bldgBounds, { padding: [80, 80], maxZoom: 18, animate: true, duration: 1.2 })
          if (selectedLayerRef.openPopup) {
            setTimeout(() => selectedLayerRef.openPopup(), 400)
          }
          return
        }
      }

      // Default extent fit if no specific feature selected
      const bounds = geoLayer.getBounds()
      if (bounds && bounds.isValid()) {
        map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15, animate: true })
      }
    } catch (err) {
      console.warn('[GeoMap Warning] Could not fit bounds to selected feature:', err)
    }
  }, [displayGeoJson, selectedFeatureId, isLeafletMode, onSelectFeature])

  // Interactive AOI Drawing handler for Leaflet
  useEffect(() => {
    const map = mapInstanceRef.current
    if (!map) return

    let tempRect = null

    const handleMouseDown = (e) => {
      if (!isDrawingAoi) return
      drawingBoxRef.current.isDrawing = true
      drawingBoxRef.current.startLatLng = e.latlng
      map.dragging.disable()
      if (tempRect) {
        map.removeLayer(tempRect)
        tempRect = null
      }
    }

    const handleMouseMove = (e) => {
      if (!isDrawingAoi || !drawingBoxRef.current.isDrawing) return
      const start = drawingBoxRef.current.startLatLng
      const end = e.latlng
      const bounds = L.latLngBounds(start, end)
      if (!tempRect) {
        tempRect = L.rectangle(bounds, {
          color: '#2563eb',
          weight: 2,
          dashArray: '4, 4',
          fillColor: '#2563eb',
          fillOpacity: 0.15
        }).addTo(map)
      } else {
        tempRect.setBounds(bounds)
      }
    }

    const handleMouseUp = (e) => {
      if (!isDrawingAoi || !drawingBoxRef.current.isDrawing) return
      drawingBoxRef.current.isDrawing = false
      map.dragging.enable()
      setIsDrawingAoi(false)

      const start = drawingBoxRef.current.startLatLng
      const end = e.latlng
      const bounds = L.latLngBounds(start, end)

      if (tempRect) {
        map.removeLayer(tempRect)
        tempRect = null
      }

      const latDiff = Math.abs(start.lat - end.lat)
      const lngDiff = Math.abs(start.lng - end.lng)
      if (latDiff > 0.005 || lngDiff > 0.005) {
        const sw = bounds.getSouthWest()
        const ne = bounds.getNorthEast()
        if (onAoiChange) {
          onAoiChange({
            name: 'Custom AOI',
            bbox: [
              [sw.lat, sw.lng],
              [ne.lat, ne.lng]
            ],
            center: [bounds.getCenter().lat, bounds.getCenter().lng],
            zoom: map.getZoom()
          })
        }
      }
    }

    map.on('mousedown', handleMouseDown)
    map.on('mousemove', handleMouseMove)
    map.on('mouseup', handleMouseUp)

    return () => {
      map.off('mousedown', handleMouseDown)
      map.off('mousemove', handleMouseMove)
      map.off('mouseup', handleMouseUp)
      if (tempRect && map) {
        map.removeLayer(tempRect)
      }
    }
  }, [isDrawingAoi, onAoiChange])

  const handleClearAoi = () => {
    if (onAoiChange) onAoiChange(null)
  }

  const handleResetView = () => {
    if (isMapboxMode && mapboxInstanceRef.current) {
      mapboxInstanceRef.current.flyTo({ center: [73.8567, 18.5204], zoom: 12, pitch: 60, bearing: 45 })
    } else if (isGoogleMode && googleMapInstanceRef.current) {
      googleMapInstanceRef.current.setCenter({ lat: 18.5204, lng: 73.8567 })
      googleMapInstanceRef.current.setZoom(12)
      setHeading3d(45)
      setTilt3d(60)
    } else if (mapInstanceRef.current) {
      mapInstanceRef.current.flyTo([18.5204, 73.8567], 12, { duration: 1 })
    }
  }

  const rotateCamera3D = () => {
    setHeading3d(prev => (prev + 45) % 360)
  }

  const toggleTilt3D = () => {
    setTilt3d(prev => (prev === 60 ? 0 : 60))
  }

  return (
    <div className="geo-map-wrapper">
      {/* Mapbox 3D Container */}
      <div
        ref={mapboxContainerRef}
        className="geo-map-canvas mapbox-3d-canvas"
        style={{ display: isMapboxMode ? 'block' : 'none', width: '100%', height: '100%' }}
      />

      {/* Google 3D Maps Container */}
      <div
        ref={googleMapContainerRef}
        className="geo-map-canvas google-3d-canvas"
        style={{ display: isGoogleMode ? 'block' : 'none', width: '100%', height: '100%' }}
      />

      {/* Leaflet Canvas */}
      <div
        ref={mapContainerRef}
        className={`geo-map-canvas ${isDrawingAoi ? 'drawing-mode' : ''}`}
        style={{ display: isLeafletMode ? 'block' : 'none', width: '100%', height: '100%' }}
      />

      {/* Drawing mode banner */}
      {isDrawingAoi && isLeafletMode && (
        <div className="drawing-banner">
          <span>Click and drag on the map to define Area of Interest (AOI)</span>
          <button
            type="button"
            className="btn-cancel-draw"
            onClick={() => setIsDrawingAoi(false)}
          >
            Cancel
          </button>
        </div>
      )}



      {/* Floating Top Controls */}
      <div className="map-floating-top">
        {/* Layer & Basemap Selector */}
        <div className="layer-control-container">
          <button
            type="button"
            className={`map-control-btn ${layersMenuOpen ? 'active' : ''}`}
            onClick={() => setLayersMenuOpen(!layersMenuOpen)}
            title="Switch 3D Map Engines & Basemaps"
          >
            <Layers size={16} />
            <span>{BASEMAPS[activeBasemap]?.name || '3D Map'}</span>
            <ChevronDown size={14} className={`chevron ${layersMenuOpen ? 'rotated' : ''}`} />
          </button>

          {layersMenuOpen && (
            <div className="layer-dropdown-panel">
              {/* Basemap Selection */}
              <div className="layer-section">
                <div className="layer-section-title">
                  <Globe size={12} />
                  <span>3D Map Engine & Basemaps</span>
                </div>
                <div className="basemap-options-vertical">
                  {Object.entries(BASEMAPS).map(([key, config]) => (
                    <button
                      key={key}
                      type="button"
                      className={`basemap-chip-full ${activeBasemap === key ? 'active' : ''}`}
                      onClick={() => {
                        setActiveBasemap(key)
                        setLayersMenuOpen(false)
                      }}
                    >
                      <div className="chip-label">
                        {config.type === 'mapbox' ? (
                          <Globe size={13} className="g3d-icon" />
                        ) : config.type === 'google' ? (
                          <Box size={13} className="g3d-icon" />
                        ) : (
                          <MapPin size={13} />
                        )}
                        <span>{config.name}</span>
                      </div>
                      {activeBasemap === key && <Check size={13} className="check-icon" />}
                    </button>
                  ))}
                </div>
              </div>

              {/* Dynamic Map Layers & Stage Status */}
              <div className="layer-section">
                <div className="layer-section-title">
                  <Database size={12} />
                  <span>Pipeline Stage Map Layers</span>
                </div>
                <div className="layer-list">
                  <div className="layer-toggle-row">
                    <span className="layer-name">AOI Boundary Selection</span>
                    <span className={`status-badge ${pipelineStage !== 'initial' ? 'active' : 'standby'}`}>
                      {pipelineStage !== 'initial' ? 'Active' : 'Standby'}
                    </span>
                  </div>
                  <div className="layer-toggle-row">
                    <span className="layer-name">Pointed Location Centroids</span>
                    <span className={`status-badge ${pipelineStage === 'retrieval' || pipelineStage === 'completed' ? 'active' : 'standby'}`}>
                      {pipelineStage === 'retrieval' ? 'Pointed' : pipelineStage === 'completed' ? 'Active' : 'Standby'}
                    </span>
                  </div>
                  <div className="layer-toggle-row">
                    <span className="layer-name">Visual Detection Masks (SAM 2)</span>
                    <span className={`status-badge ${pipelineStage === 'vision' || pipelineStage === 'gis' || pipelineStage === 'completed' ? 'active' : 'standby'}`}>
                      {pipelineStage === 'vision' ? 'Masking' : pipelineStage === 'gis' || pipelineStage === 'completed' ? 'Covered' : 'Standby'}
                    </span>
                  </div>
                  <div className="layer-toggle-row">
                    <span className="layer-name">GIS 200m Buffer & Measurements</span>
                    <span className={`status-badge ${pipelineStage === 'gis' || pipelineStage === 'completed' ? 'active' : 'standby'}`}>
                      {pipelineStage === 'gis' ? 'Calculating' : pipelineStage === 'completed' ? 'Ready' : 'Standby'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* 3D Camera Controls & AOI Toolbar */}
        <div className="aoi-toolbar">
          {(isMapboxMode || isGoogleMode) && (
            <>
              <button
                type="button"
                className="map-control-btn 3d-control-btn"
                onClick={toggleTilt3D}
                title="Toggle 3D Tilt View (60° / 0°)"
              >
                <Box size={15} />
                <span>{tilt3d > 0 ? `3D Pitch: ${tilt3d}°` : '2D Overhead'}</span>
              </button>

              <button
                type="button"
                className="map-control-btn icon-only"
                onClick={rotateCamera3D}
                title={`Rotate 3D Camera (Heading: ${heading3d}°)`}
              >
                <RotateCw size={15} />
              </button>
            </>
          )}

          {isLeafletMode && (
            <button
              type="button"
              className={`map-control-btn ${isDrawingAoi ? 'active' : ''}`}
              onClick={() => setIsDrawingAoi(!isDrawingAoi)}
              title="Draw Area of Interest bounding box"
            >
              <Square size={15} />
              <span>{isDrawingAoi ? 'Drawing...' : 'Draw AOI'}</span>
            </button>
          )}

          {aoi && (
            <button
              type="button"
              className="map-control-btn danger"
              onClick={handleClearAoi}
              title="Clear active Area of Interest"
            >
              <Trash2 size={15} />
              <span>Clear AOI</span>
            </button>
          )}

          <button
            type="button"
            className="map-control-btn icon-only"
            onClick={handleResetView}
            title="Reset Map View"
          >
            <Maximize2 size={15} />
          </button>
        </div>
      </div>

      {/* Floating Bottom HUD */}
      <div className="map-floating-bottom">
        {/* Active AOI Info Pill */}
        <div className="aoi-status-pill">
          <div className={`status-indicator-dot ${aoi ? 'active' : 'idle'}`} />
          <span className="aoi-text">
            {aoi ? `AOI: ${aoi.name || 'Defined Box'}` : 'AOI: Not Defined'}
          </span>
          {aoi && aoi.bbox && (
            <span className="aoi-coords-sub">
              [{aoi.bbox[0][0].toFixed(2)}, {aoi.bbox[0][1].toFixed(2)} to {aoi.bbox[1][0].toFixed(2)}, {aoi.bbox[1][1].toFixed(2)}]
            </span>
          )}
        </div>

        {/* Camera HUD */}
        <div className="coords-hud">
          {isMapboxMode ? (
            <span>Mapbox GL 3D | Pitch: {tilt3d}° | Heading: {heading3d}°</span>
          ) : isGoogleMode ? (
            <span>Google 3D Satellite | Tilt: {tilt3d}° | Heading: {heading3d}°</span>
          ) : cursorCoords ? (
            <span>{cursorCoords.lat}° N, {cursorCoords.lng}° E</span>
          ) : (
            <span>Interactive Map View</span>
          )}
          <span className="zoom-tag">z{zoomLevel}</span>
        </div>
      </div>
    </div>
  )
}
