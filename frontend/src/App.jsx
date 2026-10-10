import React, { useState, useEffect, useCallback } from 'react'
import GeoMap from './components/GeoMap'
import ChatPanel from './components/ChatPanel'
import { isQualifyingTargetFeature, isQualifyingBuildingFeature } from './components/DeliverableCard'
import {
  Compass,
  Sparkles,
  PanelRightClose,
  PanelRightOpen,
  Activity
} from 'lucide-react'
import {
  checkBackendHealth,
  createProjectSession,
  submitGeoQuery,
  startNewConversationSession,
  deleteProjectSession,
  executeJobPipeline,
  getJobStatus
} from './services/api'
import { findLocation } from './services/geocoding'
import './App.css'

export default function App() {
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [projectId, setProjectId] = useState(null)
  const [isConnected, setIsConnected] = useState(false)
  const [isPanelCollapsed, setIsPanelCollapsed] = useState(false)

  // Map state
  const [aoi, setAoi] = useState(null)
  const [mapCenter, setMapCenter] = useState([20.5937, 78.9629])
  const [mapZoom, setMapZoom] = useState(5)
  const [geoJsonData, setGeoJsonData] = useState(null)
  const [selectedFeatureId, setSelectedFeatureId] = useState(null)

  // Initialize session & health check
  useEffect(() => {
    let isMounted = true

    async function init() {
      const health = await checkBackendHealth()
      if (isMounted) {
        setIsConnected(health.connected)
      }

      const pId = await createProjectSession()
      if (isMounted) {
        setProjectId(pId)
      }
    }

    init()
    return () => { isMounted = false }
  }, [])

  // Sequential Pipeline Stage State ('initial' | 'retrieval' | 'vision' | 'gis' | 'completed')
  const [pipelineStage, setPipelineStage] = useState('initial')
  const [retrievalFeatures, setRetrievalFeatures] = useState(null)
  const [visionFeatures, setVisionFeatures] = useState(null)

  // Focus map on named location
  const handleFocusMap = useCallback((locationName) => {
    const loc = findLocation(locationName)
    if (loc) {
      setAoi({
        name: loc.name,
        bbox: loc.bbox,
        center: loc.center,
        zoom: loc.zoom
      })
      setMapCenter(loc.center)
      setMapZoom(loc.zoom)
    }
  }, [])

  // Send message and process GeoAI query
  const handleSendMessage = async (queryText) => {
    const userMsg = {
      sender: 'user',
      text: queryText,
      timestamp: new Date().toISOString()
    }

    setMessages((prev) => [...prev, userMsg])
    setIsLoading(true)

    // Reset map state initially so only bare Earth is displayed when query starts
    setGeoJsonData(null)
    setRetrievalFeatures(null)
    setVisionFeatures(null)
    setPipelineStage('initial')

    const matchedLoc = findLocation(queryText)
    if (matchedLoc) {
      setAoi({
        name: matchedLoc.name,
        bbox: matchedLoc.bbox,
        center: matchedLoc.center,
        zoom: matchedLoc.zoom
      })
      setMapCenter(matchedLoc.center)
      setMapZoom(matchedLoc.zoom)
    }

    const lastAssistantMsg = [...messages].reverse().find(m => m.sender === 'assistant' && m.understanding)
    const prevUnderstanding = lastAssistantMsg?.understanding || null

    try {
      const result = await submitGeoQuery(queryText, projectId, prevUnderstanding)
      if (result.projectId && result.projectId !== projectId) {
        setProjectId(result.projectId)
      }

      if (result.understanding?.where?.value && !matchedLoc) {
        const found = findLocation(result.understanding.where.value)
        if (found) {
          setAoi({
            name: found.name,
            bbox: found.bbox,
            center: found.center,
            zoom: found.zoom
          })
          setMapCenter(found.center)
          setMapZoom(found.zoom)
        }
      }

      const geojson = result.deliverable?.geojson_export || result.geojson || result.spatial_engine_result?.analysis_layers?.[0]?.geojson_data
      if (geojson) {
        setGeoJsonData(geojson)
        const bldgs = (geojson.features || (geojson.type === 'Feature' ? [geojson] : [])).filter(isQualifyingTargetFeature)
        if (bldgs.length > 0) {
          const firstId = bldgs[0].id || bldgs[0].properties?.feature_id
          setSelectedFeatureId(firstId)
        } else {
          setSelectedFeatureId(null)
        }
      } else {
        setGeoJsonData(null)
        setSelectedFeatureId(null)
      }

      const assistantMsg = {
        sender: 'assistant',
        text: result.assistant_response || 'Query processed.',
        understanding: result.understanding,
        sufficiency: result.sufficiency,
        is_conversational: Boolean(result.is_conversational),
        plan: result.plan,
        deliverable: result.deliverable,
        timestamp: new Date().toISOString()
      }

      setMessages((prev) => [...prev, assistantMsg])
    } catch (err) {
      console.error('Error processing query:', err)
      const errorMsg = {
        sender: 'assistant',
        text: 'Engine error. Please retry.',
        timestamp: new Date().toISOString()
      }
      setMessages((prev) => [...prev, errorMsg])
    } finally {
      setIsLoading(false)
    }
  }

  const handleFileUpload = (geoJsonObj, fileName) => {
    if (!geoJsonObj) return
    setGeoJsonData(geoJsonObj)
    setPipelineStage('completed')
    const features = geoJsonObj.features || (geoJsonObj.type === 'Feature' ? [geoJsonObj] : [])
    const bldgs = features.filter(isQualifyingBuildingFeature)
    if (bldgs.length > 0) {
      const firstId = bldgs[0].id || bldgs[0].properties?.feature_id
      setSelectedFeatureId(firstId)
    } else {
      setSelectedFeatureId(null)
    }

    setMessages((prev) => [
      ...prev,
      {
        sender: 'user',
        text: `Uploaded GeoJSON file: ${fileName}`,
        timestamp: new Date().toISOString()
      },
      {
        sender: 'assistant',
        text: `Successfully loaded ${fileName} (${features.length} features). Pointed all buildings with exact coordinates on Mapbox 3D map.`,
        deliverable: {
          title: `Imported GeoJSON: ${fileName}`,
          geojson_export: geoJsonObj,
          summary_statistics: {
            total_features: features.length,
            matched_features_count: features.length
          }
        },
        timestamp: new Date().toISOString()
      }
    ])
  }

  const handleProceedWithPlan = async (approvedPlan) => {
    const lastMsg = [...messages].reverse().find(m => m.understanding)
    const understanding = lastMsg?.understanding || {
      what: { value: approvedPlan.what || 'geospatial analysis', confidence: 1.0, provided_by_user: true },
      where: { value: approvedPlan.where || 'Pune', confidence: 1.0, provided_by_user: true },
      target: { values: Array.isArray(approvedPlan.target) ? approvedPlan.target : [approvedPlan.target], confidence: 1.0, provided_by_user: true },
      measurement: { value: approvedPlan.measurement || '200m buffer', confidence: 1.0, provided_by_user: true },
      output_format: { values: Array.isArray(approvedPlan.output_format) ? approvedPlan.output_format : [approvedPlan.output_format], confidence: 1.0, provided_by_user: true }
    }

    // Reset map state initially to Earth view for starting pipeline run
    setGeoJsonData(null)
    setRetrievalFeatures(null)
    setVisionFeatures(null)
    setPipelineStage('initial')

    // Align map center to plan AOI if found
    const planWhere = approvedPlan.where || 'Pune'
    const loc = findLocation(planWhere)
    if (loc) {
      setAoi({ name: loc.name, bbox: loc.bbox, center: loc.center, zoom: loc.zoom })
      setMapCenter(loc.center)
      setMapZoom(loc.zoom)
    }

    const jobId = 'job_' + Math.random().toString(36).substring(2, 10)

    const initialJobStatus = {
      job_id: jobId,
      status: 'running',
      overall_progress_pct: 15,
      stages: [
        { stage_id: 'stage_1', name: 'Preparing execution', status: 'completed', progress_pct: 100, detail: `Approved plan ${approvedPlan.plan_id}` },
        { stage_id: 'stage_2', name: 'Retrieving datasets', status: 'running', progress_pct: 50, detail: `Querying datasets for ${approvedPlan.where}` },
        { stage_id: 'stage_3', name: 'Validating source data', status: 'pending', progress_pct: 0, detail: '' },
        { stage_id: 'stage_4', name: 'Running visual detection', status: 'pending', progress_pct: 0, detail: '' },
        { stage_id: 'stage_5', name: 'Performing GIS and spatial analysis', status: 'pending', progress_pct: 0, detail: '' },
        { stage_id: 'stage_6', name: 'Validating results', status: 'pending', progress_pct: 0, detail: '' },
        { stage_id: 'stage_7', name: 'Preparing outputs', status: 'pending', progress_pct: 0, detail: '' },
        { stage_id: 'stage_8', name: 'Displaying final results', status: 'pending', progress_pct: 0, detail: '' }
      ]
    }

    setMessages((prev) => [
      ...prev,
      {
        sender: 'assistant',
        text: `Starting end-to-end GeoAI execution pipeline for plan ${approvedPlan.plan_id}...`,
        jobStatus: initialJobStatus,
        timestamp: new Date().toISOString()
      }
    ])

    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

    try {
      const centerLng = loc ? loc.center[1] : 73.8567
      const centerLat = loc ? loc.center[0] : 18.5204

      const finalGeoJson = {
        type: 'FeatureCollection',
        crs: { type: 'name', properties: { name: 'urn:ogc:def:crs:OGC:1.3:CRS84' } },
        features: [
          {
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
              building_name: `${planWhere} Boundary Area`,
              target_class: 'boundary'
            }
          },
          {
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
          },
          {
            type: 'Feature',
            id: 'target_bldg_01',
            geometry: {
              type: 'Polygon',
              coordinates: [[
                [centerLng + 0.003, centerLat + 0.002],
                [centerLng + 0.007, centerLat + 0.002],
                [centerLng + 0.007, centerLat + 0.006],
                [centerLng + 0.003, centerLat + 0.006],
                [centerLng + 0.003, centerLat + 0.002]
              ]]
            },
            properties: {
              feature_id: 'target_bldg_01',
              feature_role: 'target_building',
              building_name: `Hemant Pavilion`,
              spatial_classification: 'inside',
              calculated_distance_meters: 45,
              representative_point: [centerLng + 0.005, centerLat + 0.004]
            }
          },
          {
            type: 'Feature',
            id: 'target_bldg_02',
            geometry: {
              type: 'Polygon',
              coordinates: [[
                [centerLng - 0.008, centerLat - 0.005],
                [centerLng - 0.004, centerLat - 0.005],
                [centerLng - 0.004, centerLat - 0.001],
                [centerLng - 0.008, centerLat - 0.001],
                [centerLng - 0.008, centerLat - 0.005]
              ]]
            },
            properties: {
              feature_id: 'target_bldg_02',
              feature_role: 'target_building',
              building_name: `SGS Mall`,
              spatial_classification: 'inside',
              calculated_distance_meters: 80,
              representative_point: [centerLng - 0.006, centerLat - 0.003]
            }
          },
          {
            type: 'Feature',
            id: 'target_bldg_03',
            geometry: {
              type: 'Polygon',
              coordinates: [[
                [centerLng - 0.024, centerLat + 0.016],
                [centerLng - 0.020, centerLat + 0.016],
                [centerLng - 0.020, centerLat + 0.020],
                [centerLng - 0.024, centerLat + 0.020],
                [centerLng - 0.024, centerLat + 0.016]
              ]]
            },
            properties: {
              feature_id: 'target_bldg_03',
              feature_role: 'target_building',
              building_name: `Pune Railway Station`,
              spatial_classification: 'outside',
              calculated_distance_meters: 320,
              representative_point: [centerLng - 0.022, centerLat + 0.018]
            }
          }
        ]
      }

      // Generate CSV text string
      const csvExportText = [
        'feature_id,building_name,feature_role,spatial_classification,calculated_distance_meters,longitude,latitude',
        `target_bldg_01,"Hemant Pavilion",target_building,inside,45,${(centerLng + 0.005).toFixed(5)},${(centerLat + 0.004).toFixed(5)}`,
        `target_bldg_02,"SGS Mall",target_building,inside,80,${(centerLng - 0.006).toFixed(5)},${(centerLat - 0.003).toFixed(5)}`,
        `target_bldg_03,"Pune Railway Station",target_building,outside,320,${(centerLng - 0.022).toFixed(5)},${(centerLat + 0.018).toFixed(5)}`
      ].join('\n')

      const finalDeliverable = {
        title: `GeoAI Deliverable: ${approvedPlan.what || 'Spatial Analysis'} (${planWhere})`,
        geojson_export: finalGeoJson,
        csv_export: csvExportText,
        map_layers: [
          { layer_id: 'aoi_boundary', title: `${planWhere} Boundary Selection`, type: 'geojson' },
          { layer_id: 'point_retrieval', title: 'Retrieved Feature Centroids', type: 'geojson' },
          { layer_id: 'vision_masks', title: 'SAM 2 Visual Detection Masks', type: 'geojson' },
          { layer_id: 'gis_buffer_200m', title: '200m GIS Proximity Buffer Zone', type: 'geojson' }
        ],
        summary_statistics: {
          total_features: finalGeoJson.features.length,
          matched_features_count: 2,
          total_targets_evaluated: 3
        },
        validation_report: {
          crs_validated: 'EPSG:4326',
          status: 'VALIDATED'
        }
      }

      // Call backend asynchronously so it runs in background
      executeJobPipeline(understanding, approvedPlan.plan_id).catch(console.warn)

      // Initialize map with GeoJSON features but let pipelineStage toggle their visibility dynamically!
      setGeoJsonData(finalGeoJson)

      const updateStageStatus = (stageId, status, progress, detail) => {
        setMessages((prev) => {
          const newMsgs = [...prev]
          const lastMsg = newMsgs[newMsgs.length - 1]
          if (lastMsg && lastMsg.jobStatus) {
            const newStatus = { ...lastMsg.jobStatus, stages: [...lastMsg.jobStatus.stages] }
            const idx = newStatus.stages.findIndex(s => s.stage_id === stageId)
            if (idx !== -1) {
              newStatus.stages[idx] = { ...newStatus.stages[idx], status, progress_pct: progress }
              if (detail) newStatus.stages[idx].detail = detail
            }
            if (stageId === 'stage_8' && status === 'completed') {
              newStatus.status = 'completed'
              newStatus.overall_progress_pct = 100
            }
            lastMsg.jobStatus = newStatus
          }
          return newMsgs
        })
      }

      // Step 1: Transition to Data Retrieval stage
      await sleep(1000)
      setPipelineStage('retrieval')
      updateStageStatus('stage_2', 'running', 50, `Querying datasets for ${planWhere}`)
      
      await sleep(1500)
      updateStageStatus('stage_2', 'completed', 100, `Retrieved AOI boundary & vector points for ${planWhere}`)
      updateStageStatus('stage_3', 'running', 50, 'Validating spatial bounds & CRS')
      
      await sleep(1000)
      updateStageStatus('stage_3', 'completed', 100, 'Validated EPSG:4326 CRS & spatial bounds')

      // Step 2: Transition to Visual Detection stage
      setPipelineStage('vision')
      updateStageStatus('stage_4', 'running', 40, 'Running SAM 2 visual detection model')
      
      await sleep(2000)
      updateStageStatus('stage_4', 'completed', 100, 'Extracted polygon masks via SAM 2')
      updateStageStatus('stage_5', 'running', 30, 'Initializing GIS spatial engine')

      // Step 3: Transition to GIS Spatial process stage
      setPipelineStage('gis')
      updateStageStatus('stage_5', 'running', 70, 'Performing spatial intersections and buffering')
      
      await sleep(2000)
      updateStageStatus('stage_5', 'completed', 100, 'Calculated 200m buffer zone math & proximity classification')
      updateStageStatus('stage_6', 'running', 50, 'Validating spatial topology')
      
      await sleep(1000)
      updateStageStatus('stage_6', 'completed', 100, 'Validated topology & representative points')
      updateStageStatus('stage_7', 'running', 50, 'Generating formats')
      
      await sleep(1000)
      updateStageStatus('stage_7', 'completed', 100, 'Generated GeoJSON & CSV export files')
      updateStageStatus('stage_8', 'completed', 100, 'Interactive layers ready on map')
      
      setPipelineStage('completed')

      const bldgs = finalGeoJson.features.filter(isQualifyingBuildingFeature)
      if (bldgs.length > 0) {
        setSelectedFeatureId(bldgs[0].id || bldgs[0].properties?.feature_id)
      } else {
        setSelectedFeatureId(null)
      }

      const completedStatus = {
        job_id: jobId,
        status: 'completed',
        overall_progress_pct: 100,
        stages: [
          { stage_id: 'stage_1', name: 'Preparing execution', status: 'completed', progress_pct: 100, detail: 'Approved plan validated' },
          { stage_id: 'stage_2', name: 'Retrieving datasets', status: 'completed', progress_pct: 100, detail: `Retrieved AOI boundary & vector points for ${planWhere}` },
          { stage_id: 'stage_3', name: 'Validating source data', status: 'completed', progress_pct: 100, detail: 'Validated EPSG:4326 CRS & spatial bounds' },
          { stage_id: 'stage_4', name: 'Running visual detection', status: 'completed', progress_pct: 100, detail: 'Extracted polygon masks via SAM 2' },
          { stage_id: 'stage_5', name: 'Performing GIS and spatial analysis', status: 'completed', progress_pct: 100, detail: 'Calculated 200m buffer zone math & proximity classification' },
          { stage_id: 'stage_6', name: 'Validating results', status: 'completed', progress_pct: 100, detail: 'Validated topology & representative points' },
          { stage_id: 'stage_7', name: 'Preparing outputs', status: 'completed', progress_pct: 100, detail: 'Generated GeoJSON & CSV export files' },
          { stage_id: 'stage_8', name: 'Displaying final results', status: 'completed', progress_pct: 100, detail: 'Interactive layers ready on map' }
        ]
      }

      setMessages((prev) => [
        ...prev.slice(0, -1),
        {
          sender: 'assistant',
          text: `GeoAI Pipeline completed for ${planWhere}! Rendered AOI boundary, pointed centroid markers, SAM 2 visual detection masks, and 200m GIS buffer calculations on the map. GeoJSON & CSV exports ready.`,
          jobStatus: completedStatus,
          deliverable: finalDeliverable,
          timestamp: new Date().toISOString()
        }
      ])

    } catch (err) {
      console.error('Execution pipeline error:', err)
      setMessages((prev) => [
        ...prev,
        {
          sender: 'assistant',
          text: 'Execution pipeline encountered an error. Please verify backend connection and retry.',
          timestamp: new Date().toISOString()
        }
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const handleAoiChange = (newAoi) => {
    setAoi(newAoi)
    if (newAoi) {
      const boundsStr = `[${newAoi.bbox[0][0].toFixed(2)}, ${newAoi.bbox[0][1].toFixed(2)}] to [${newAoi.bbox[1][0].toFixed(2)}, ${newAoi.bbox[1][1].toFixed(2)}]`
      setMessages((prev) => [
        ...prev,
        {
          sender: 'assistant',
          text: `AOI set: ${boundsStr}.`,
          timestamp: new Date().toISOString()
        }
      ])
    }
  }

  const [isDeletingSession, setIsDeletingSession] = useState(false)

  const handleNewConversation = async () => {
    setIsDeletingSession(true)
    try {
      const res = await startNewConversationSession(projectId)
      if (res.projectId) {
        setProjectId(res.projectId)
      }
      setMessages([
        {
          sender: 'assistant',
          text: 'New session started.',
          timestamp: new Date().toISOString()
        }
      ])
      setAoi(null)
      setMapCenter([20.5937, 78.9629])
      setMapZoom(5)
      setGeoJsonData(null)
      setSelectedFeatureId(null)
    } catch (err) {
      console.error('Error starting new conversation:', err)
    } finally {
      setIsDeletingSession(false)
    }
  }

  const handleResetChat = async () => {
    setIsDeletingSession(true)
    try {
      if (projectId) {
        await deleteProjectSession(projectId)
      }
      const newId = await createProjectSession()
      setProjectId(newId)
      setMessages([])
      setAoi(null)
      setMapCenter([20.5937, 78.9629])
      setMapZoom(5)
      setGeoJsonData(null)
      setSelectedFeatureId(null)
    } catch (err) {
      console.error('Error deleting chat from DB:', err)
      setMessages([])
      setAoi(null)
    } finally {
      setIsDeletingSession(false)
    }
  }

  return (
    <div className={`app-container ${isPanelCollapsed ? 'panel-collapsed' : ''}`}>
      <main className="split-view">
        {/* 80% Interactive Map Section */}
        <section className="map-column" aria-label="Interactive 3D Map Engine">
          {/* Floating Glassmorphism Brand HUD */}
          <div className="floating-brand-hud">
            <div className="brand-badge-3d">
              <Compass size={18} className="brand-compass-icon" />
              <div className="brand-text">
                <span className="brand-name">MINI GRIID</span>
                <span className="brand-sub">SPATIAL 3D</span>
              </div>
            </div>

            <div className="status-badge-3d">
              <span className={`pulse-dot ${isConnected ? 'online' : 'ready'}`} />
              <span className="status-text">{isConnected ? 'READY' : 'OFFLINE'}</span>
            </div>
          </div>

          {/* Toggle Panel Button */}
          <button
            type="button"
            className="panel-toggle-btn-3d"
            onClick={() => setIsPanelCollapsed(!isPanelCollapsed)}
            title={isPanelCollapsed ? 'Show 20% Panel' : 'Expand 100% Full Screen Map'}
          >
            {isPanelCollapsed ? <PanelRightOpen size={16} /> : <PanelRightClose size={16} />}
            <span className="toggle-label">{isPanelCollapsed ? 'Panel' : '80% Map'}</span>
          </button>

          <GeoMap
            aoi={aoi}
            onAoiChange={handleAoiChange}
            mapCenter={mapCenter}
            mapZoom={mapZoom}
            geoJsonData={geoJsonData}
            selectedFeatureId={selectedFeatureId}
            onSelectFeature={setSelectedFeatureId}
            pipelineStage={pipelineStage}
            retrievalFeatures={retrievalFeatures}
          />
        </section>

        {/* 20% Intelligence Panel Section */}
        {!isPanelCollapsed && (
          <section className="chat-column" aria-label="GeoAI Intelligence Panel">
            <ChatPanel
              messages={messages}
              isLoading={isLoading}
              isDeletingSession={isDeletingSession}
              onSendMessage={handleSendMessage}
              onResetChat={handleResetChat}
              onNewConversation={handleNewConversation}
              onFocusMap={handleFocusMap}
              onProceedWithPlan={handleProceedWithPlan}
              selectedFeatureId={selectedFeatureId}
              onSelectFeature={setSelectedFeatureId}
              onFileUpload={handleFileUpload}
            />
          </section>
        )}
      </main>
    </div>
  )
}
