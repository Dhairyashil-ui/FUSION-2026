from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class ProjectBase(BaseModel):
    name: str


class ProjectCreate(ProjectBase):
    pass


class ProjectRead(ProjectBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationRead(BaseModel):
    id: UUID
    project_id: UUID
    conversation_number: int
    user_query: str
    assistant_response: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str


class DatabaseHealthResponse(BaseModel):
    status: str
    database: str
    postgis: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None
