import React from 'react'
import {
  Loader2,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Cpu,
  Layers,
  Search,
  Sliders,
  ShieldCheck,
  Package,
  Globe
} from 'lucide-react'

const STAGE_ICONS = {
  stage_1: Cpu,
  stage_2: Layers,
  stage_3: ShieldCheck,
  stage_4: Search,
  stage_5: Sliders,
  stage_6: CheckCircle2,
  stage_7: Package,
  stage_8: Globe
}

export default function ExecutionProgressCard({ jobStatus }) {
  if (!jobStatus) return null

  const {
    job_id,
    status = 'running',
    overall_progress_pct = 0,
    stages = [],
    error_message
  } = jobStatus

  return (
    <div className="execution-progress-card-3d">
      <div className="progress-header">
        <div className="progress-title-group">
          <Loader2 size={16} className={`progress-spinner ${status === 'running' ? 'active' : ''}`} />
          <span className="progress-title">Live GeoAI Execution ({job_id})</span>
        </div>
        <span className={`progress-status-badge ${status}`}>
          {status.toUpperCase()} ({overall_progress_pct}%)
        </span>
      </div>

      {/* Main Progress Bar */}
      <div className="progress-bar-track">
        <div
          className="progress-bar-fill"
          style={{ width: `${overall_progress_pct}%` }}
        />
      </div>

      {/* 8 Stages List */}
      <div className="stages-list">
        {stages.map((stage, idx) => {
          const IconComp = STAGE_ICONS[stage.stage_id] || Clock
          const isCurrent = stage.status === 'running'
          const isDone = stage.status === 'completed'
          const isFailed = stage.status === 'failed'

          return (
            <div
              key={stage.stage_id || idx}
              className={`stage-row ${stage.status} ${isCurrent ? 'active-stage' : ''}`}
            >
              <div className="stage-icon-wrap">
                {isCurrent ? (
                  <Loader2 size={13} className="spinner-icon" />
                ) : isDone ? (
                  <CheckCircle2 size={13} className="done-icon" />
                ) : isFailed ? (
                  <AlertTriangle size={13} className="fail-icon" />
                ) : (
                  <IconComp size={13} className="pending-icon" />
                )}
              </div>

              <div className="stage-info">
                <div className="stage-name-row">
                  <span className="stage-number">{idx + 1}.</span>
                  <span className="stage-name">{stage.name}</span>
                </div>
                {stage.detail && <span className="stage-detail">{stage.detail}</span>}
              </div>

              <div className="stage-badge">
                {stage.status === 'completed' && <span className="tag-done">100%</span>}
                {stage.status === 'running' && <span className="tag-running">{stage.progress_pct}%</span>}
                {stage.status === 'pending' && <span className="tag-pending">Pending</span>}
                {stage.status === 'failed' && <span className="tag-failed">Failed</span>}
              </div>
            </div>
          )
        })}
      </div>

      {error_message && (
        <div className="execution-error-box">
          <AlertTriangle size={14} />
          <span>Execution Warning: {error_message}</span>
        </div>
      )}
    </div>
  )
}
