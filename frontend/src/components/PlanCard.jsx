import React from 'react'
import {
  Layers,
  Search,
  Sliders,
  Workflow,
  Download,
  CheckCircle2,
  AlertTriangle,
  Cpu
} from 'lucide-react'

export default function PlanCard({ plan, onProceedWithPlan }) {
  if (!plan) return null

  const {
    plan_id,
    what,
    where,
    target,
    measurement,
    output_format,
    data_retrieval = [],
    visual_search = [],
    spatial_analysis = [],
    output_specification = {},
    execution_graph = [],
    is_valid,
    validation_warnings = []
  } = plan

  return (
    <div className="plan-card">
      <div className="plan-header">
        <div className="plan-header-title">
          <Workflow size={16} className="plan-header-icon" />
          <span>AI Execution Plan ({plan_id})</span>
        </div>
        <div className="plan-header-badges">
          <span className={`plan-status-badge ${is_valid ? 'valid' : 'warning'}`}>
            {is_valid ? (
              <>
                <CheckCircle2 size={12} />
                <span>Validated & Ready</span>
              </>
            ) : (
              <>
                <AlertTriangle size={12} />
                <span>Validation Warning</span>
              </>
            )}
          </span>
        </div>
      </div>

      {/* Query Overview */}
      <div className="plan-summary-bar">
        <div className="plan-summary-item">
          <span className="summary-label">Task</span>
          <span className="summary-val">{what}</span>
        </div>
        <div className="plan-summary-item">
          <span className="summary-label">AOI</span>
          <span className="summary-val">{where}</span>
        </div>
        <div className="plan-summary-item">
          <span className="summary-label">Targets</span>
          <span className="summary-val">{Array.isArray(target) ? target.join(', ') : target}</span>
        </div>
      </div>

      {/* 5 Plan Sections */}
      <div className="plan-sections-grid">
        {/* Stage 1: Data Retrieval */}
        <div className="plan-section-block full-width">
          <div className="section-title">
            <Layers size={13} className="section-icon" />
            <span>1. Data Retrieval</span>
          </div>
          <div className="section-list">
            {data_retrieval && data_retrieval.length > 0 ? (
              data_retrieval.map((item, idx) => (
                <div key={idx} className="plan-step-pill" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '4px', padding: '8px 12px' }}>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                    <span className="step-tag category-tag" style={{ background: 'var(--accent-soft)', color: 'var(--accent)', border: '1px solid var(--accent-border)', padding: '2px 8px', borderRadius: 'var(--r-full)', fontSize: '0.75rem', fontWeight: 600 }}>
                      {item.category || 'Vector GIS Data'}
                    </span>
                    <span className={`step-tag level-tag ${item.requirement_level === 'required' ? 'req-tag' : 'opt-tag'}`} style={{ background: item.requirement_level === 'required' ? 'var(--green-soft)' : 'var(--amber-soft)', color: item.requirement_level === 'required' ? 'var(--green)' : 'var(--amber)', border: `1px solid ${item.requirement_level === 'required' ? 'var(--green-border)' : 'var(--amber-border)'}`, padding: '2px 8px', borderRadius: 'var(--r-full)', fontSize: '0.7rem', fontWeight: 700 }}>
                      {(item.requirement_level || 'required').toUpperCase()}
                    </span>
                    {item.registered_source_api && (
                      <span className="step-tag api-tag" style={{ background: 'var(--violet-soft)', color: 'var(--violet)', border: '1px solid var(--violet-border)', padding: '2px 8px', borderRadius: 'var(--r-full)', fontSize: '0.7rem' }}>
                        API: {item.registered_source_api}
                      </span>
                    )}
                  </div>
                  <div className="step-desc" style={{ fontSize: '0.85rem' }}>
                    <strong>{item.dataset_name || item.dataset_id}</strong> — {item.purpose}
                  </div>
                  <div style={{ fontSize: '0.75rem', opacity: 0.8, display: 'flex', gap: '12px', color: 'var(--text-secondary)' }}>
                    {item.spatial_coverage && <span>Coverage: {item.spatial_coverage}</span>}
                    {item.expected_format && <span>Format: {item.expected_format}</span>}
                  </div>
                </div>
              ))
            ) : (
              <div className="plan-step-pill" style={{ fontSize: '0.8rem', opacity: 0.7 }}>
                Retrieve vector data and boundaries for AOI.
              </div>
            )}
          </div>
        </div>

        {/* Stage 2: Visual Detector */}
        <div className="plan-section-block">
          <div className="section-title">
            <Search size={13} className="section-icon" />
            <span>2. Visual Detector</span>
          </div>
          <div className="section-list">
            {visual_search && visual_search.length > 0 ? (
              visual_search.map((item, idx) => (
                <div key={idx} className="plan-step-pill">
                  <span className="step-tag model-tag">{item.model}</span>
                  <span className="step-desc">Detect: <strong>{item.target_entity}</strong> ({item.text_prompt})</span>
                </div>
              ))
            ) : (
              <div className="plan-step-pill" style={{ fontSize: '0.8rem', opacity: 0.7 }}>
                Detect target entities: <strong>{Array.isArray(target) ? target.join(', ') : target || 'specified targets'}</strong>
              </div>
            )}
          </div>
        </div>

        {/* Stage 3: GIS Engine */}
        <div className="plan-section-block">
          <div className="section-title">
            <Sliders size={13} className="section-icon" />
            <span>3. GIS Engine</span>
          </div>
          <div className="section-list">
            {spatial_analysis && spatial_analysis.length > 0 ? (
              spatial_analysis.map((item, idx) => (
                <div key={idx} className="plan-step-pill">
                  <span className="step-tag op-tag">{item.operation}</span>
                  <span className="step-desc">Calculate <strong>{item.output_layer}</strong> from retrieved data & visual detection</span>
                </div>
              ))
            ) : (
              <div className="plan-step-pill" style={{ fontSize: '0.8rem', opacity: 0.7 }}>
                Calculate spatial containment and distance buffer relationships.
              </div>
            )}
          </div>
        </div>

        {/* Stage 4: Validation */}
        <div className="plan-section-block full-width">
          <div className="section-title">
            <CheckCircle2 size={13} className="section-icon" />
            <span>4. Validation</span>
          </div>
          <div className="section-list" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <div className="plan-step-pill" style={{ fontSize: '0.8rem', gap: '6px' }}>
              <span className="step-tag" style={{ background: 'var(--green-soft)', color: 'var(--green)', border: '1px solid var(--green-border)', padding: '2px 8px', borderRadius: 'var(--r-full)' }}>CRS Validation</span>
              <span>{plan.validation_and_fallback?.crs_validation || 'EPSG:4326 (WGS84)'}</span>
            </div>
            <div className="plan-step-pill" style={{ fontSize: '0.8rem', gap: '6px' }}>
              <span className="step-tag" style={{ background: 'var(--accent-soft)', color: 'var(--accent)', border: '1px solid var(--accent-border)', padding: '2px 8px', borderRadius: 'var(--r-full)' }}>Data Checks</span>
              <span>{plan.validation_and_fallback?.data_availability_checks?.join(', ') || 'Coverage & attribute completeness verified'}</span>
            </div>
          </div>
        </div>

        {/* Stage 5: Output */}
        <div className="plan-section-block full-width">
          <div className="section-title">
            <Download size={13} className="section-icon" />
            <span>5. Output</span>
          </div>
          <div className="output-formats-list">
            {(output_specification?.export_formats || (Array.isArray(output_format) ? output_format : [output_format]) || ['GeoJSON', 'interactive map']).filter(Boolean).map((fmt, idx) => (
              <span key={idx} className="format-badge">{fmt}</span>
            ))}
          </div>
        </div>
      </div>

      {plan.missing_data_flags && plan.missing_data_flags.length > 0 && (
        <div className="plan-missing-box" style={{ marginTop: '10px', padding: '8px 12px', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid #ef4444', borderRadius: '6px', color: '#f87171', fontSize: '0.8rem' }}>
          <span className="warning-title" style={{ fontWeight: 600, display: 'block', marginBottom: '4px' }}>🚨 Flagged Missing Data:</span>
          <ul style={{ margin: 0, paddingLeft: '16px' }}>
            {plan.missing_data_flags.map((m, idx) => (
              <li key={idx}>{m}</li>
            ))}
          </ul>
        </div>
      )}

      {validation_warnings.length > 0 && (
        <div className="plan-warnings-box">
          <span className="warning-title">Validation Warnings:</span>
          <ul>
            {validation_warnings.map((w, idx) => (
              <li key={idx}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Action Button: Proceed with this Plan */}
      {onProceedWithPlan && (
        <div className="plan-proceed-action">
          <button
            type="button"
            className="btn-proceed-plan-3d"
            onClick={() => onProceedWithPlan(plan)}
          >
            <Workflow size={15} />
            <span>Proceed with this Plan</span>
          </button>
        </div>
      )}
    </div>
  )
}
