import React from 'react'
import { MapPin, Sliders, Target, FileOutput, Activity, Navigation } from 'lucide-react'

export default function DimensionsCard({ understanding, onFocusMap }) {
  if (!understanding) return null

  const { what, where, target, measurement, output_format } = understanding

  return (
    <div className="dimensions-card">
      <div className="dimensions-header">
        <span className="dimensions-title">Extracted Query Dimensions</span>
        <span className="dimensions-badge">5-Field GeoAI</span>
      </div>

      <div className="dimensions-grid">
        {/* WHAT */}
        <div className="dimension-item">
          <div className="dim-label">
            <Activity size={13} className="dim-icon" />
            <span>WHAT (Analytical Task)</span>
          </div>
          <div className="dim-value">
            {what?.value || <span className="dim-empty">Not specified</span>}
          </div>
        </div>

        {/* WHERE */}
        <div className="dimension-item">
          <div className="dim-label">
            <MapPin size={13} className="dim-icon" />
            <span>WHERE (AOI)</span>
          </div>
          <div className="dim-value-row">
            <span className="dim-value">
              {where?.value || <span className="dim-empty">Not specified</span>}
            </span>
            {where?.value && onFocusMap && (
              <button
                type="button"
                className="btn-locate"
                onClick={() => onFocusMap(where.value)}
                title="Locate AOI on Map"
              >
                <Navigation size={12} />
                <span>Locate</span>
              </button>
            )}
          </div>
        </div>

        {/* TARGET */}
        <div className="dimension-item">
          <div className="dim-label">
            <Target size={13} className="dim-icon" />
            <span>TARGET (Objects & Features)</span>
          </div>
          <div className="dim-value">
            {target?.values && target.values.length > 0 ? (
              <div className="dim-tags">
                {target.values.map((val, idx) => (
                  <span key={idx} className="dim-tag">{val}</span>
                ))}
              </div>
            ) : (
              <span className="dim-empty">Not specified</span>
            )}
          </div>
        </div>

        {/* MEASUREMENT */}
        <div className="dimension-item">
          <div className="dim-label">
            <Sliders size={13} className="dim-icon" />
            <span>MEASUREMENT (Constraints & Operations)</span>
          </div>
          <div className="dim-value">
            {measurement?.value ? (
              <span>{measurement.value}</span>
            ) : (
              <span className="dim-empty">Not specified</span>
            )}
          </div>
        </div>

        {/* OUTPUT FORMAT */}
        <div className="dimension-item full-width">
          <div className="dim-label">
            <FileOutput size={13} className="dim-icon" />
            <span>OUTPUT (Deliverables)</span>
          </div>
          <div className="dim-value">
            {output_format?.values && output_format.values.length > 0 ? (
              <div className="dim-tags">
                {output_format.values.map((fmt, idx) => (
                  <span key={idx} className="dim-tag format-tag">{fmt}</span>
                ))}
              </div>
            ) : (
              <span className="dim-empty">Not specified</span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
