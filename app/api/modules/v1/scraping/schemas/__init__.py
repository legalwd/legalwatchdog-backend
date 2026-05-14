"""Schema exports for scraping module."""

from app.api.modules.v1.scraping.schemas.source_service import (
    SourceCreate,
    SourceRead,
    SourceUpdate,
)

__all__ = ["SourceCreate", "SourceUpdate", "SourceRead"]
