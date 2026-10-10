import React from 'react'
import { Sparkles, Compass } from 'lucide-react'

export default function Header({ isConnected }) {
  return (
    <header className="app-header">
      <div className="header-left">
        <div className="brand-logo">
          <Compass size={18} className="brand-icon" />
          <span className="brand-title">FUSION 2026</span>
          <span className="brand-tag">GeoAI</span>
        </div>
      </div>

      <div className="header-center">
        <span className="phase-pill">
          Geospatial Intelligence Platform
        </span>
      </div>

      <div className="header-right">
        <div className="system-status">
          <span className={`status-indicator ${isConnected ? 'online' : 'ready'}`} />
          <span className="status-label">
            {isConnected ? 'Backend Connected' : 'Engine Ready'}
          </span>
        </div>
      </div>
    </header>
  )
}
