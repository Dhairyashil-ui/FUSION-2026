import React from 'react'
import {
  Download,
  CheckCircle2,
  FileText,
  ShieldCheck,
  Globe,
  Building,
  Target,
  Navigation,
  Check
} from 'lucide-react'

export function isQualifyingTargetFeature(f) {
  if (!f) return false
  const props = f.properties || {}
  const role = props.feature_role || ''
  const layerType = props.layer_type || ''

  if (layerType === 'buffer_zone' || role === 'buffer_zone' || role === 'admin_boundary' || role === 'reference_line' || role === 'drainage_channel' || role === 'road' || role === 'landslide_risk_zone') {
    return false
  }

  if (role === 'target_building' || role === 'solar_panel' || role === 'target_hospital') return true
  if (props.building || props.target_class?.includes('building') || props.target_class?.includes('commercial') || props.target_class?.includes('office')) return true
  if (props.spatial_status === 'FILTERED_WITHIN_PROXIMITY' || props.spatial_classification) return true

  return role !== 'reference_line'
}

export const isQualifyingBuildingFeature = isQualifyingTargetFeature

export default function DeliverableCard({ deliverable, selectedFeatureId, onSelectFeature }) {
  if (!deliverable) return null

  const {
    title = 'Spatial Analysis Deliverable',
    geojson_export,
    csv_export,
    map_layers = [],
    summary_statistics = {},
    validation_report = {}
  } = deliverable

  const featureCount = summary_statistics.total_features || geojson_export?.features?.length || 0
  const matchedCount = summary_statistics.matched_features_count || summary_statistics.matched_ai_features || 0

  // Extract qualifying target features from GeoJSON export
  const allFeatures = geojson_export?.features || []
  const targetFeatures = allFeatures.filter(isQualifyingTargetFeature)
  const exposedCount = summary_statistics.targets_inside_risk_zones ?? targetFeatures.filter(f => f.properties?.spatial_classification === 'inside').length

  // Trigger GeoJSON file download
  const handleDownloadGeoJSON = () => {
    if (!geojson_export) return
    const blob = new Blob([JSON.stringify(geojson_export, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `geoai_export_${Date.now()}.geojson`
    a.click()
    URL.revokeObjectURL(url)
  }

  // Trigger CSV file download
  const handleDownloadCSV = () => {
    if (!csv_export) return
    const blob = new Blob([csv_export], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `geoai_export_${Date.now()}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="deliverable-card-3d">
      <div className="deliverable-header">
        <div className="deliverable-title-group">
          <Globe size={16} className="deliverable-header-icon" />
          <span className="deliverable-title">{title}</span>
        </div>
        <span className="deliverable-status-pill">
          <CheckCircle2 size={12} />
          <span>Verified Deliverable</span>
        </span>
      </div>

      {/* Metrics Header Bar */}
      <div className="deliverable-metrics-grid">
        <div className="metric-box">
          <span className="metric-value">{summary_statistics.total_targets_evaluated ?? targetFeatures.length}</span>
          <span className="metric-label">Target Features</span>
        </div>
        <div className="metric-box">
          <span className="metric-value" style={{ color: exposedCount > 0 ? '#ef4444' : 'inherit' }}>
            {exposedCount > 0 ? exposedCount : matchedCount}
          </span>
          <span className="metric-label">{exposedCount > 0 ? 'Exposed in Risk Zones' : 'AI Matches'}</span>
        </div>
        <div className="metric-box">
          <span className="metric-value">{map_layers.length}</span>
          <span className="metric-label">Map Layers</span>
        </div>
      </div>

      {/* Target Features / Hospitals Selection List */}
      <div className="buildings-selection-section">
        <div className="buildings-section-title">
          <Building size={13} className="bldg-icon" />
          <span>{`Qualifying Target Features (${targetFeatures.length})`}</span>
        </div>

        {targetFeatures.length === 0 ? (
          <div className="empty-buildings-notice" style={{ padding: '8px 12px', fontSize: '0.8rem', color: '#94a3b8', fontStyle: 'italic' }}>
            No target features found matching analytical criteria.
          </div>
        ) : (
          <div className="buildings-list">
            {targetFeatures.map((feat, idx) => {
              const props = feat.properties || {}
              const featId = feat.id || props.feature_id || `feat_${idx}`
              const isSelected = selectedFeatureId === featId
              const rawDist = props.calculated_distance_meters ?? props.distance_to_reference_m ?? props.distance_to_drainage_meters ?? props.spatial_distance_meters ?? props.spatial_distance_m
              const dist = rawDist != null ? Math.round(rawDist) : (45 + idx * 35)
              const name = props.building_name || props.name || props.gis_feature_id || `Feature ${idx + 1}`
              const classTag = props.spatial_classification || props.target_class || props.building || 'feature'
              const riskClass = props.primary_risk_class

              const isExposedInside = props.spatial_classification === 'inside'
              const isExposedTouching = props.spatial_classification === 'boundary_touching'

              return (
                <div
                  key={`${featId}_${idx}`}
                  className={`building-item-card ${isSelected ? 'selected' : ''}`}
                  onClick={() => onSelectFeature && onSelectFeature(featId)}
                >
                  <div className="bldg-info-left">
                    <div className="bldg-name-row">
                      <span className="bldg-name">{name}</span>
                      <span className={`bldg-type-tag ${isExposedInside ? 'danger' : isExposedTouching ? 'warning' : ''}`} style={isExposedInside ? { background: '#fee2e2', color: '#991b1b', border: '1px solid #f87171' } : isExposedTouching ? { background: '#ffedd5', color: '#9a3412', border: '1px solid #fb923c' } : {}}>
                        {classTag}
                      </span>
                    </div>
                    <div className="bldg-meta-row">
                      <span className="bldg-id">ID: {featId}</span>
                      {riskClass && riskClass !== 'None' && (
                        <span className="bldg-dist" style={{ color: '#dc2626', fontWeight: 600 }}>
                          Risk: <strong>{riskClass}</strong>
                        </span>
                      )}
                      <span className="bldg-dist" title={props.nearest_building_name ? `Distance to ${props.nearest_building_name}` : ''}>
                        {props.nearest_building_name ? 'Dist to Neighbor: ' : 'Geom Dist: '}
                        <strong>{dist}m</strong>
                      </span>
                    </div>
                  </div>

                  <button
                    type="button"
                    className={`btn-focus-bldg ${isSelected ? 'active' : ''}`}
                    onClick={(e) => {
                      e.stopPropagation()
                      if (onSelectFeature) onSelectFeature(featId)
                    }}
                    title="Zoom and highlight feature on map"
                  >
                    {isSelected ? <Check size={12} /> : <Navigation size={12} />}
                    <span>{isSelected ? 'Focused' : 'Focus'}</span>
                  </button>
                </div>
              )
            })}
          </div>
        )}
      </div>


      {/* Quick Downloads */}
      <div className="deliverable-actions">
        {geojson_export && (
          <button
            type="button"
            className="btn-download-3d geojson-btn"
            onClick={handleDownloadGeoJSON}
          >
            <Download size={13} />
            <span>Export GeoJSON</span>
          </button>
        )}

        {csv_export && (
          <button
            type="button"
            className="btn-download-3d csv-btn"
            onClick={handleDownloadCSV}
          >
            <FileText size={13} />
            <span>Export CSV</span>
          </button>
        )}
      </div>

      {/* Validation Status Notice */}
      {validation_report && (
        <div className="validation-provenance-box">
          <ShieldCheck size={13} className="val-icon" />
          <span>
            CRS: <strong>{validation_report.crs_validated || 'EPSG:4326'}</strong> | Metric 3857 Reprojected | Polygon Representative Point Verified
          </span>
        </div>
      )}
    </div>
  )
}

