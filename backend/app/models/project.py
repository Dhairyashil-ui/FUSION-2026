import uuid
from sqlalchemy import Column, Text, DateTime, func, text
from sqlalchemy.types import Uuid
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Project(Base):
    """Stores a user's FUSION project / session."""
    __tablename__ = "projects"

    id = Column(
        Uuid().with_variant(PG_UUID(as_uuid=True), "postgresql"),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    name = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Relationships
    conversations = relationship("Conversation", back_populates="project", cascade="all, delete-orphan")
    summaries = relationship("ConversationSummary", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Project id={self.id} name='{self.name}'>"
