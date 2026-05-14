import logging
import re
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import desc, select

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import NotFoundError, ProcessingError
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.scraping.storage.minio_storage import get_content_from_minio

logger = logging.getLogger(__name__)


class OutputService:
    """Service for handling content downloads from MinIO."""

    def __init__(self, db: AsyncSession):
        """
        Initialize download service.

        Args:
            db: Database session
        """
        self.db = db

    async def get_revision_markdown(
        self, revision_id: str, include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Retrieve markdown content for a data revision.

        Args:
            revision_id: UUID of the data revision
            include_metadata: Whether to prepend metadata header

        Returns:
            Dict containing:
                - content (bytes): Markdown content
                - filename (str): Suggested filename
                - content_type (str): MIME type
                - metadata (dict): Revision metadata

        Raises:
            NotFoundException: If revision not found
            S3Error: If content not in MinIO
        """
        query = (
            select(DataRevision)
            .where(DataRevision.id == revision_id)
            .options(selectinload(DataRevision.source).selectinload(Source.jurisdiction))
        )
        result = await self.db.execute(query)
        revision = result.scalars().first()

        if not revision:
            raise NotFoundError(f"Data revision {revision_id} not found")

        object_key = revision.minio_object_key

        if object_key.startswith("raw/"):
            bucket = settings.MINIO_BUCKET
        elif object_key.startswith("clean/"):
            bucket = settings.MINIO_BUCKET
        else:
            bucket = settings.MINIO_BUCKET
            logger.warning(
                f"Object key '{object_key}' doesn't match expected pattern. "
                f"Defaulting to bucket: {bucket}"
            )

        try:
            content_bytes = get_content_from_minio(object_name=object_key, bucket_name=bucket)

            if content_bytes is None:
                logger.info(f"Content retrieval returned None for {bucket}/{object_key}")
                raise NotFoundError("No content retrieved")

        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch content for revision {revision_id}: {e}")
            raise ProcessingError()

        if include_metadata:
            metadata_header = self._generate_metadata_header(revision)
            content_bytes = metadata_header.encode("utf-8") + b"\n\n" + content_bytes

        source_name = revision.source.name.replace(" ", "_").replace("/", "_")
        jurisdiction_name = revision.source.jurisdiction.name.replace(" ", "_").replace("/", "_")
        timestamp = revision.scraped_at.strftime("%Y%m%d_%H%M%S")
        filename = f"{jurisdiction_name}_{source_name}_{timestamp}.md"

        return {
            "content": content_bytes,
            "filename": filename,
            "content_type": "text/markdown; charset=utf-8",
            "metadata": {
                "revision_id": str(revision.id),
                "source_id": str(revision.source_id),
                "source_name": revision.source.name,
                "jurisdiction": revision.source.jurisdiction.name,
                "url": revision.source.url,
                "scraped_at": revision.scraped_at.isoformat(),
                "content_hash": revision.content_hash,
                "was_change_detected": revision.was_change_detected,
                "confidence_score": revision.ai_confidence_score,
            },
        }

    async def get_revision_markdown_payload(
        self, revision_id: str, include_metadata: bool = True
    ) -> Dict[str, Any]:
        """Return a JSON-serializable payload for revision markdown download."""
        result = await self.get_revision_markdown(revision_id, include_metadata)

        content_bytes = result["content"]
        try:
            content_text = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            import base64

            content_text = base64.b64encode(content_bytes).decode("ascii")

        return {
            "content": content_text,
            "filename": result["filename"],
            "content_type": result["content_type"],
            "metadata": result["metadata"],
        }

    async def get_latest_revision_markdown(
        self, source_id: str, include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Get markdown for the latest revision of a source.

        Args:
            source_id: UUID of the source
            include_metadata: Whether to include metadata header

        Returns:
            Same format as get_revision_markdown()

        Raises:
            NotFoundException: If no revisions found for source
        """

        try:
            query = (
                select(DataRevision)
                .where(DataRevision.source_id == source_id)
                .order_by(desc(DataRevision.scraped_at))
                .limit(1)
            )
            result = await self.db.execute(query)
            revision = result.scalars().first()

            if not revision:
                raise NotFoundError(f"No revisions found for source {source_id}")

            return await self.get_revision_markdown(
                str(revision.id), include_metadata=include_metadata
            )

        except NotFoundError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to retrieve latest revision markdown for {source_id}: {str(e)}",
                exc_info=True,
            )
            raise ProcessingError()

    async def get_latest_revision_markdown_payload(
        self, source_id: str, include_metadata: bool = True
    ):
        result = await self.get_latest_revision_markdown(
            source_id, include_metadata=include_metadata
        )
        content_bytes = result["content"]
        try:
            content_text = content_bytes.decode("utf-8")
        except Exception:
            import base64

            content_text = base64.b64encode(content_bytes).decode("ascii")

        return {
            "content": content_text,
            "filename": result["filename"],
            "content_type": result["content_type"],
            "metadata": result["metadata"],
        }

    async def get_revision_for_display(
        self, revision_id: str, include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Get revision content for frontend display/rendering.

        Returns structured JSON suitable for UI display.
        """
        result = await self.get_revision_markdown(revision_id, include_metadata)

        markdown_content = result["content"].decode("utf-8")

        sections = self._split_markdown_sections(markdown_content)

        return {
            "id": revision_id,
            "content": markdown_content,
            "sections": sections,
            "metadata": result["metadata"],
            "filename": result["filename"],
            "preview": self._generate_preview(markdown_content),
            "word_count": len(markdown_content.split()),
            "character_count": len(markdown_content),
            "format": "markdown",
        }

    async def get_latest_revision_for_display(
        self, source_id: str, include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Get latest revision for display.
        """
        query = (
            select(DataRevision)
            .where(DataRevision.source_id == source_id)
            .order_by(desc(DataRevision.scraped_at))
            .limit(1)
        )
        result = await self.db.execute(query)
        revision = result.scalars().first()

        if not revision:
            raise NotFoundError(f"No revisions found for source {source_id}")

        return await self.get_revision_for_display(str(revision.id), include_metadata)

    def _split_markdown_sections(self, markdown: str) -> List[Dict[str, Any]]:
        """
        Split markdown into sections based on headers.
        Useful for creating a table of contents.
        """

        sections = []
        lines = markdown.split("\n")
        current_section = {"title": "Content", "content": "", "level": 1, "id": "content"}

        for line in lines:
            header_match = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
            if header_match:
                if current_section["content"].strip():
                    sections.append(current_section.copy())

                level = len(header_match.group(1))
                title = header_match.group(2)
                section_id = title.lower().replace(" ", "-").replace(".", "")

                current_section = {"title": title, "content": "", "level": level, "id": section_id}
            else:
                current_section["content"] += line + "\n"

        if current_section["content"].strip():
            sections.append(current_section)

        return sections

    def _generate_preview(self, markdown: str, max_length: int = 300) -> str:
        """
        Generate a preview/snippet of the content.
        """
        import re

        text = re.sub(r"^#+\s+", "", markdown, flags=re.MULTILINE)
        text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        text = re.sub(r"`[^`]+`", "", text)
        text = re.sub(r"\*\*|\*|__|_", "", text)

        text = " ".join(text.split())

        if len(text) <= max_length:
            return text
        else:
            return text[:max_length].rsplit(" ", 1)[0] + "..."

    def _generate_metadata_header(self, revision: DataRevision) -> str:
        """Generate markdown metadata header in YAML frontmatter format."""
        return f"""---
        title: {revision.source.name}
        revision_id: {revision.id}
        source_id: {revision.source_id}
        jurisdiction: {revision.source.jurisdiction.name}
        url: {revision.source.url}
        scraped_at: {revision.scraped_at.isoformat()}
        change_detected: {revision.was_change_detected}
        confidence_score: {revision.ai_confidence_score or "N/A"}
        content_hash: {revision.content_hash[:16]}...
        ---"""
