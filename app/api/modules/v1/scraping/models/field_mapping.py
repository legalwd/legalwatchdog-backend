"""Field mapping model for tracking semantic field name equivalences.

This model stores mappings between original field names (as extracted by different
LLMs) and their canonical field names for consistent diff analysis.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class FieldMapping(SQLModel, table=True):
    """Stores field name mappings for semantic normalization.

    Each mapping represents an equivalence between an original field name
    (from LLM extraction) and a canonical field name (for consistent comparison).

    Examples:
        - original: "price_visa", canonical: "visa_price"
        - original: "audit_submission_deadline", canonical: "audit_deadline"
    """

    __tablename__ = "field_mappings"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    source_id: UUID = Field(foreign_key="sources.id", index=True)
    original_field_name: str = Field(index=True)
    canonical_field_name: str = Field(index=True)
    similarity_score: float = Field(
        default=1.0, description="Confidence score for this mapping (0.0-1.0)"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    approved: bool = Field(
        default=False, description="Whether this mapping has been reviewed/approved by a user"
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "source_id": "123e4567-e89b-12d3-a456-426614174000",
                "original_field_name": "price_visa",
                "canonical_field_name": "visa_price",
                "similarity_score": 0.95,
                "approved": False,
            }
        }
