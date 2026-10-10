import React, { useState, useRef, useEffect } from 'react'
import {
  Send,
  AlertCircle,
  CheckCircle2,
  Globe,
  Loader2,
  Plus,
  Trash2,
  Upload
} from 'lucide-react'
import DimensionsCard from './DimensionsCard'
import PlanCard from './PlanCard'
import DeliverableCard from './DeliverableCard'
import ExecutionProgressCard from './ExecutionProgressCard'

export default function ChatPanel({
  messages,
  isLoading,
  isDeletingSession,
  onSendMessage,
  onResetChat,
  onNewConversation,
  onFocusMap,
  onProceedWithPlan,
  selectedFeatureId,
  onSelectFeature,
  onFileUpload
}) {
  const [inputText, setInputText] = useState('')
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const fileInputRef = useRef(null)

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (evt) => {
      try {
        const parsed = JSON.parse(evt.target.result)
        if (onFileUpload) {
          onFileUpload(parsed, file.name)
        }
      } catch (err) {
        alert('Invalid GeoJSON file format. Please upload a valid .geojson or .json file.')
      }
    }
    reader.readAsText(file)
    e.target.value = ''
  }

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const handleSubmit = (e) => {
    e?.preventDefault()
    if (!inputText.trim() || isLoading || isDeletingSession) return
    onSendMessage(inputText.trim())
    setInputText('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="chat-panel-container">
      {/* Chat Header */}
      <div className="chat-header">
        <div className="chat-header-title-group">
          <div className="google-header-dots" title="Google AI Identity System">
            <span className="g-dot blue" />
            <span className="g-dot red" />
            <span className="g-dot yellow" />
            <span className="g-dot green" />
          </div>
          <div>
            <h2 className="chat-title">MINI GRIID Intelligence</h2>
            <p className="chat-subtitle">Query Understanding & Spatial Analytics</p>
          </div>
        </div>

        <div className="chat-header-actions">
          <button
            type="button"
            className="btn-new-chat"
            onClick={onNewConversation}
            disabled={isLoading || isDeletingSession}
            title="Start new conversation and delete old records from database"
          >
            {isDeletingSession ? (
              <Loader2 size={13} className="spinner" />
            ) : (
              <Plus size={14} />
            )}
            <span>New Chat</span>
          </button>

          <button
            type="button"
            className="btn-icon danger-icon"
            onClick={onResetChat}
            disabled={isLoading || isDeletingSession}
            title="Delete current conversation from database"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div className="chat-messages-container">
        {messages.length === 0 ? (
          <div className="chat-empty-state">
            <div className="empty-icon-wrap">
              <Globe size={28} className="empty-icon" />
            </div>
            <h3 className="empty-title">MINI GRIID Spatial Assistant</h3>
            <p className="empty-description">
              Describe your geospatial query specifying what to find, area of interest, target entities, spatial measurements, or required output formats.
            </p>
          </div>
        ) : (
          <div className="chat-stream">
            {messages.map((msg, index) => (
              <div
                key={index}
                className={`message-row ${msg.sender === 'user' ? 'user' : 'assistant'}`}
              >
                {msg.sender === 'user' ? (
                  <div className="user-bubble">
                    <p className="message-text">{msg.text}</p>
                  </div>
                ) : (
                  <div className="assistant-bubble">
                    {/* Natural language response */}
                    <div className="message-markdown" style={{ whiteSpace: 'pre-wrap' }}>
                      {msg.text}
                    </div>

                    {/* Sufficiency Missing Information Alert (Only when insufficient) */}
                    {msg.sufficiency && !msg.is_conversational && !msg.sufficiency.is_sufficient && (
                      <div className="sufficiency-alert insufficient">
                        <AlertCircle size={15} className="alert-icon warning" />
                        <span>
                          {msg.sufficiency.missing_information && msg.sufficiency.missing_information.length > 0
                            ? `Missing: ${msg.sufficiency.missing_information.map(f => f.toUpperCase()).join(', ')}`
                            : msg.sufficiency.missing_fields && msg.sufficiency.missing_fields.length > 0
                            ? `Missing: ${msg.sufficiency.missing_fields.map(f => f.toUpperCase()).join(', ')}`
                            : msg.sufficiency.reason || msg.sufficiency.questions_for_user?.[0] || 'Additional information required to proceed.'}
                        </span>
                      </div>
                    )}

                    {/* Visual AI Execution Plan Card */}
                    {msg.plan && (
                      <PlanCard plan={msg.plan} onProceedWithPlan={onProceedWithPlan} />
                    )}

                    {/* Live Execution 8-Stage Progress Card */}
                    {msg.jobStatus && (
                      <ExecutionProgressCard jobStatus={msg.jobStatus} />
                    )}

                    {/* Part 3 Spatial Output Deliverable Card */}
                    {msg.deliverable && (
                      <DeliverableCard
                        deliverable={msg.deliverable}
                        selectedFeatureId={selectedFeatureId}
                        onSelectFeature={onSelectFeature}
                      />
                    )}

                    {/* 5-Field Dimensions Extraction */}
                    {msg.understanding && !msg.is_conversational && (
                      <DimensionsCard
                        understanding={msg.understanding}
                        onFocusMap={onFocusMap}
                      />
                    )}
                  </div>
                )}
              </div>
            ))}

            {/* Loading Indicator */}
            {isLoading && (
              <div className="message-row assistant">
                <div className="assistant-bubble loading-bubble">
                  <div className="loading-dots">
                    <span /><span /><span />
                  </div>
                  <span>Analyzing geospatial query…</span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Chat Input Container */}
      <div className="chat-input-wrapper">
        <form className="chat-input-form" onSubmit={handleSubmit}>
          <textarea
            ref={inputRef}
            className="chat-textarea"
            placeholder="Type your geospatial problem or location query..."
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={2}
            disabled={isLoading}
          />
          <div className="chat-input-actions">
            <input
              type="file"
              ref={fileInputRef}
              accept=".geojson,.json"
              style={{ display: 'none' }}
              onChange={handleFileChange}
            />
            <button
              type="button"
              className="btn-upload-geojson"
              onClick={() => fileInputRef.current?.click()}
              disabled={isLoading}
              title="Upload GeoJSON / JSON file to display buildings on Mapbox"
            >
              <Upload size={13} />
              <span>GeoJSON</span>
            </button>
            <span className="input-hint">Shift + Enter for line</span>
            <button
              type="submit"
              className="btn-send"
              disabled={!inputText.trim() || isLoading}
              title="Send Message"
            >
              <Send size={15} />
              <span>Send</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
