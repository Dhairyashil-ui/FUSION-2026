import uuid
from sqlalchemy import Column, Text, Integer, DateTime, ForeignKey, UniqueConstraint, Index, func, text
from sqlalchemy.types import Uuid
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Conversation(Base):
    """Stores every user and assistant conversational exchange."""
    __tablename__ = "conversations"

    id = Column(
        Uuid().with_variant(PG_UUID(as_uuid=True), "postgresql"),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    project_id = Column(
        Uuid().with_variant(PG_UUID(as_uuid=True), "postgresql"),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    conversation_number = Column(Integer, nullable=False)
    user_query = Column(Text, nullable=False)
    assistant_response = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("project_id", "conversation_number", name="uq_project_conversation_number"),
        Index("idx_conversations_project_id", "project_id"),
        Index("idx_conversations_project_number", "project_id", "conversation_number"),
    )

    # Relationships
    project = relationship("Project", back_populates="conversations")
    extracted_requirements = relationship(
        "ExtractedRequirement",
        back_populates="conversation",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Conversation id={self.id} project_id={self.project_id} num={self.conversation_number}>"
