import React from 'react'
import { Sparkles, Compass } from 'lucide-react'

export default function Header({ isConnected }) {
  return (
    <header className="app-header">
      <div className="header-left">
        <div className="brand-logo">
          <Compass size={18} className="brand-icon" />
          <span className="brand-title">MINI GRIID</span>
          <span className="brand-tag">SPATIAL AI</span>
        </div>
      </div>

      <div className="header-center">
        <span className="phase-pill">
          Spatial Intelligence Platform
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
