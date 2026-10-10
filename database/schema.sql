-- ==============================================================================
-- FUSION 2026 - Database Schema
-- Target: PostgreSQL / Supabase with PostGIS
-- ==============================================================================

-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- ------------------------------------------------------------------------------
-- 1. Projects Table
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ------------------------------------------------------------------------------
-- 2. Conversations Table
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    conversation_number INTEGER NOT NULL,
    user_query TEXT NOT NULL,
    assistant_response TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_project_conversation_number UNIQUE (project_id, conversation_number)
);

-- ------------------------------------------------------------------------------
-- 3. Extracted Requirements Table
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS extracted_requirements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    what JSONB,
    where_data JSONB,
    target JSONB,
    measurement_data JSONB,
    output_format JSONB,
    missing_information JSONB,
    questions_for_user JSONB,
    is_sufficient BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ------------------------------------------------------------------------------
-- 4. Conversation Summaries Table
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS conversation_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    summary_start_conversation INTEGER NOT NULL,
    summary_end_conversation INTEGER NOT NULL,
    summary_text TEXT NOT NULL,
    structured_state JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_project_summary_range UNIQUE (project_id, summary_start_conversation, summary_end_conversation)
);

-- ------------------------------------------------------------------------------
-- Indexes
-- ------------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_conversations_project_id 
    ON conversations (project_id);

CREATE INDEX IF NOT EXISTS idx_conversations_project_number 
    ON conversations (project_id, conversation_number);

CREATE INDEX IF NOT EXISTS idx_extracted_requirements_conversation_id 
    ON extracted_requirements (conversation_id);

CREATE INDEX IF NOT EXISTS idx_conversation_summaries_project_id 
    ON conversation_summaries (project_id);
