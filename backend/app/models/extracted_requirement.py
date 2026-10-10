import uuid
from sqlalchemy import Column, Boolean, DateTime, ForeignKey, Index, func, text
from sqlalchemy.types import Uuid, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB as PG_JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class ExtractedRequirement(Base):
    """Stores the five extracted components and sufficiency state from each conversation."""
    __tablename__ = "extracted_requirements"

    id = Column(
        Uuid().with_variant(PG_UUID(as_uuid=True), "postgresql"),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    conversation_id = Column(
        Uuid().with_variant(PG_UUID(as_uuid=True), "postgresql"),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    what = Column(JSON().with_variant(PG_JSONB, "postgresql"), nullable=True)
    where_data = Column(JSON().with_variant(PG_JSONB, "postgresql"), nullable=True)
    target = Column(JSON().with_variant(PG_JSONB, "postgresql"), nullable=True)
    measurement_data = Column(JSON().with_variant(PG_JSONB, "postgresql"), nullable=True)
    output_format = Column(JSON().with_variant(PG_JSONB, "postgresql"), nullable=True)
    missing_information = Column(JSON().with_variant(PG_JSONB, "postgresql"), nullable=True)
    questions_for_user = Column(JSON().with_variant(PG_JSONB, "postgresql"), nullable=True)
    is_sufficient = Column(Boolean, default=False, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_extracted_requirements_conversation_id", "conversation_id"),
    )

    # Relationships
    conversation = relationship("Conversation", back_populates="extracted_requirements")

    def __repr__(self) -> str:
        return f"<ExtractedRequirement id={self.id} conversation_id={self.conversation_id} sufficient={self.is_sufficient}>"
