import uuid
from sqlalchemy import Column, Text, Integer, DateTime, ForeignKey, UniqueConstraint, Index, func, text
from sqlalchemy.types import Uuid, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB as PG_JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class ConversationSummary(Base):
    """Stores accumulated summaries generated after every 10 conversation turns."""
    __tablename__ = "conversation_summaries"

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
    summary_start_conversation = Column(Integer, nullable=False)
    summary_end_conversation = Column(Integer, nullable=False)
    summary_text = Column(Text, nullable=False)
    structured_state = Column(JSON().with_variant(PG_JSONB, "postgresql"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "summary_start_conversation",
            "summary_end_conversation",
            name="uq_project_summary_range"
        ),
        Index("idx_conversation_summaries_project_id", "project_id"),
    )

    # Relationships
    project = relationship("Project", back_populates="summaries")

    def __repr__(self) -> str:
        return f"<ConversationSummary id={self.id} project_id={self.project_id} range={self.summary_start_conversation}-{self.summary_end_conversation}>"
