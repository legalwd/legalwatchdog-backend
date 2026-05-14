from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExtractionResult(BaseModel):
    """
    Schema for the Extraction phase (Text -> JSON).
    The AI populates 'extracted_data' with keys derived from the prompt logic.
    """

    summary: str = Field(..., description="A concise summary.")

    markdown_summary: str = Field(
        default="",
        description="Markdown-formatted summary with extracted data "
        "presented as formatted table or list. Generated after extraction.",
    )

    confidence_score: float = Field(..., description="0.0 to 1.0 confidence score.", ge=0.0, le=1.0)

    extracted_data: Dict[str, Any] = Field(..., description="Key-value facts.")


class FieldChange(BaseModel):
    """Represents a single field change in diff analysis.

    Attributes:
        field_name: Canonical name of the changed field
        old_value: Previous value (None if field was added)
        new_value: New value (None if field was removed)
        change_type: Type of change - "added", "removed", or "modified"
        change_description: Human-readable sentence describing the change

    Examples:
        >>> FieldChange(
        ...     field_name="fee_schedule_fee_1",
        ...     old_value="$32,500.00",
        ...     new_value="$33,500.00",
        ...     change_type="modified",
        ...     change_description="Standard License Fee increased from $32,500.00 to $33,500.00"
        ... )
    """

    field_name: str = Field(..., description="Canonical name of the field that changed")
    old_value: Optional[str] = Field(None, description="Previous value, None if added")
    new_value: Optional[str] = Field(None, description="New value, None if removed")
    change_type: str = Field(
        default="modified", description="Type of change: 'added', 'removed', or 'modified'"
    )
    change_description: Optional[str] = Field(
        None,
        description="Human-readable sentence describing this specific change "
        "(e.g., 'Standard License Fee increased from $32,500.00 to $33,500.00')",
    )

    @field_validator("old_value", "new_value", mode="before")
    @classmethod
    def convert_to_string(cls, v):
        """Convert dict/list values to JSON strings for LLM compliance."""
        if v is None:
            return None
        if isinstance(v, (dict, list)):
            import json

            return json.dumps(v, default=str)
        return str(v)


class ChangeDetectionResult(BaseModel):
    """
    Strict schema for the Semantic Diff phase (JSON A vs JSON B).

    Now includes detailed field-level changes for precise tracking.
    """

    has_changed: bool = Field(
        ...,
        description="True if FACTUAL information changed. False if only phrasing changed.",
    )

    change_summary: str = Field(
        ...,
        description="One sentence explaining exactly what changed"
        " (e.g. 'Visa price increased from 60 to 80').",
    )

    risk_level: str = Field(
        ..., description="LOW, MEDIUM, or HIGH based on the severity of the change."
    )

    field_changes: List[FieldChange] = Field(
        default_factory=list,
        description="Detailed list of individual field changes with old/new values",
    )

    model_config = ConfigDict(extra="forbid")
