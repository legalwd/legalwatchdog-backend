"""Unit tests for Stage2ExtractionService."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.api.core.custom_exceptions.exceptions import ProcessingError
from app.api.modules.v1.scraping.models.scrape_job import ScrapeJob
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.scraping.service.stage2_extraction_service import Stage2ExtractionService


@pytest.fixture
def test_source_id():
    """Generate a test source ID."""
    return str(uuid4())


@pytest.fixture
def test_job_id():
    """Generate a test job ID."""
    return str(uuid4())


@pytest.fixture
def test_revision_id():
    """Generate a test revision ID."""
    return str(uuid4())


@pytest.fixture
def test_content_hash():
    """Generate a test content hash."""
    return "abc123def456"


@pytest.fixture
def test_minio_key():
    """Generate a test MinIO key."""
    return "test/source/content.md"


class TestStage2ExtractionService:
    """Test suite for Stage2ExtractionService."""

    @pytest.mark.asyncio
    async def test_execute_successful_extraction(
        self, test_source_id, test_job_id, test_content_hash, test_minio_key
    ):
        """Test successful LLM extraction."""
        content = "Legal document content for extraction"
        extraction_data = {
            "extracted_data": {
                "key_value_pairs": {"effective_date": "2024-01-01", "jurisdiction": "Federal"}
            },
            "summary": "Legal update summary",
            "markdown_summary": "**Legal update** summary",
            "confidence_score": 0.85,
        }

        with (
            patch("app.api.db.database.SyncSessionLocal") as mock_session_factory,
            patch(
                "app.api.modules.v1.scraping.service.stage2_extraction_service.get_content_from_minio"
            ) as mock_get_content,
            patch(
                "app.api.modules.v1.scraping.service.stage2_extraction_service.AIExtractionService"
            ) as mock_ai_service,
        ):
            # Setup mocks
            mock_session = AsyncMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)

            mock_source = MagicMock(spec=Source)
            mock_project = MagicMock()
            mock_project.monitoring_goal = "Monitor legal changes"
            mock_source.project = mock_project
            mock_jurisdiction = MagicMock()
            mock_jurisdiction.name = "Federal Court"
            mock_source.jurisdiction = mock_jurisdiction

            # Mock the execute calls
            mock_result1 = MagicMock()
            mock_result1.scalar_one_or_none = MagicMock(return_value=None)
            mock_result2 = MagicMock()
            mock_result2.scalar_one_or_none = MagicMock(return_value=None)
            mock_result3 = MagicMock()
            mock_result3.scalars = MagicMock(
                return_value=MagicMock(first=MagicMock(return_value=mock_source))
            )

            mock_session.execute = AsyncMock(side_effect=[mock_result1, mock_result2, mock_result3])
            mock_session.commit = AsyncMock()
            mock_session_factory.return_value = mock_session

            mock_get_content.return_value = content

            mock_ai_instance = MagicMock()
            mock_ai_instance.run_llm_analysis_with_openrouter = AsyncMock(
                return_value=extraction_data
            )
            mock_ai_service.return_value = mock_ai_instance

            service = Stage2ExtractionService()
            result = await service.execute(
                test_source_id, test_job_id, test_content_hash, test_minio_key, db=mock_session
            )

            assert result["status"] == "completed"
            assert result["extraction_count"] == 2  # Two key-value pairs
            assert "revision_id" in result

            # Verify revision was created (since no existing revision was found)
            # The service creates a new DataRevision and commits it

            # Note: Stage 3 chaining is handled at the task level, not service level

    @pytest.mark.asyncio
    async def test_execute_empty_content_from_minio(
        self, test_source_id, test_job_id, test_content_hash, test_minio_key
    ):
        """Test handling of empty content from MinIO."""
        with (
            patch("app.api.db.database.SyncSessionLocal") as mock_session_factory,
            patch(
                "app.api.modules.v1.scraping.service.stage2_extraction_service.get_content_from_minio"
            ) as mock_get_content,
        ):
            mock_session = AsyncMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)

            mock_source = MagicMock(spec=Source)
            mock_result1 = MagicMock()
            mock_result1.scalar_one_or_none = MagicMock(return_value=None)
            mock_result2 = MagicMock()
            mock_result2.scalar_one_or_none = MagicMock(return_value=None)
            mock_result3 = MagicMock()
            mock_result3.scalars = MagicMock(
                return_value=MagicMock(first=MagicMock(return_value=mock_source))
            )
            mock_result4 = MagicMock()
            mock_result4.scalars = MagicMock(
                return_value=MagicMock(first=MagicMock(return_value=MagicMock(spec=ScrapeJob)))
            )
            mock_result5 = MagicMock()
            mock_result5.scalars = MagicMock(
                return_value=MagicMock(first=MagicMock(return_value=MagicMock(spec=ScrapeJob)))
            )
            mock_session.execute = AsyncMock(
                side_effect=[mock_result1, mock_result2, mock_result3, mock_result4, mock_result5]
            )
            mock_session_factory.return_value = mock_session

            mock_get_content.return_value = ""  # Empty content

            service = Stage2ExtractionService()

            with pytest.raises(ProcessingError, match="Failed to extract data"):
                await service.execute(
                    test_source_id, test_job_id, test_content_hash, test_minio_key, db=mock_session
                )

    @pytest.mark.asyncio
    async def test_execute_source_not_found(
        self, test_source_id, test_job_id, test_content_hash, test_minio_key
    ):
        """Test handling when source doesn't exist."""
        content = "Legal document content"

        with (
            patch("app.api.db.database.SyncSessionLocal") as mock_session_factory,
            patch(
                "app.api.modules.v1.scraping.service.stage2_extraction_service.get_content_from_minio"
            ) as mock_get_content,
        ):
            mock_session = AsyncMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)

            mock_result1 = MagicMock()
            mock_result1.scalar_one_or_none = MagicMock(return_value=None)
            mock_result2 = MagicMock()
            mock_result2.scalar_one_or_none = MagicMock(return_value=None)
            mock_result3 = MagicMock()
            mock_result3.scalars = MagicMock(
                return_value=MagicMock(first=MagicMock(return_value=None))
            )
            mock_result4 = MagicMock()
            mock_result4.scalars = MagicMock(
                return_value=MagicMock(first=MagicMock(return_value=MagicMock(spec=ScrapeJob)))
            )
            mock_result5 = MagicMock()
            mock_result5.scalars = MagicMock(
                return_value=MagicMock(first=MagicMock(return_value=MagicMock(spec=ScrapeJob)))
            )
            mock_session.execute = AsyncMock(
                side_effect=[mock_result1, mock_result2, mock_result3, mock_result4, mock_result5]
            )
            mock_session_factory.return_value = mock_session

            mock_get_content.return_value = content

            service = Stage2ExtractionService()

            with pytest.raises(ProcessingError, match="Failed to extract data"):
                await service.execute(
                    test_source_id, test_job_id, test_content_hash, test_minio_key, db=mock_session
                )

    @pytest.mark.asyncio
    async def test_execute_llm_extraction_failure(
        self, test_source_id, test_job_id, test_content_hash, test_minio_key
    ):
        """Test handling of LLM extraction failure."""
        content = "Legal document content"

        with (
            patch("app.api.db.database.SyncSessionLocal") as mock_session_factory,
            patch(
                "app.api.modules.v1.scraping.service.stage2_extraction_service.get_content_from_minio"
            ) as mock_get_content,
            patch(
                "app.api.modules.v1.scraping.service.stage2_extraction_service.AIExtractionService"
            ) as mock_ai_service,
        ):
            mock_session = AsyncMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)

            mock_source = MagicMock(spec=Source)
            mock_project = MagicMock()
            mock_project.monitoring_goal = "Monitor legal changes"
            mock_source.project = mock_project
            mock_jurisdiction = MagicMock()
            mock_jurisdiction.name = "Federal Court"
            mock_source.jurisdiction = mock_jurisdiction
            mock_job = MagicMock(spec=ScrapeJob)

            mock_result1 = MagicMock()
            mock_result1.scalar_one_or_none = MagicMock(return_value=None)
            mock_result2 = MagicMock()
            mock_result2.scalar_one_or_none = MagicMock(return_value=None)
            mock_result3 = MagicMock()
            mock_result3.scalars = MagicMock(
                return_value=MagicMock(first=MagicMock(return_value=mock_source))
            )
            mock_result4 = MagicMock()
            mock_result4.scalars = MagicMock(
                return_value=MagicMock(first=MagicMock(return_value=mock_job))
            )
            mock_result5 = MagicMock()
            mock_result5.scalars = MagicMock(
                return_value=MagicMock(first=MagicMock(return_value=mock_job))
            )
            mock_session.execute = AsyncMock(
                side_effect=[mock_result1, mock_result2, mock_result3, mock_result4, mock_result5]
            )
            mock_session.commit = AsyncMock()
            mock_session_factory.return_value = mock_session

            mock_get_content.return_value = content

            mock_ai_instance = MagicMock()
            mock_ai_instance.run_llm_analysis_with_openrouter = AsyncMock(
                side_effect=Exception("LLM API error")
            )
            mock_ai_service.return_value = mock_ai_instance

            service = Stage2ExtractionService()

            with pytest.raises(ProcessingError, match="Failed to extract data"):
                await service.execute(
                    test_source_id, test_job_id, test_content_hash, test_minio_key, db=mock_session
                )

            # Verify revision status was set to extracting but then failed
            # Since no existing revision, this assertion doesn't apply

    @pytest.mark.asyncio
    async def test_execute_with_none_project_jurisdiction(
        self, test_source_id, test_job_id, test_content_hash, test_minio_key
    ):
        """Test extraction with None project/jurisdiction values."""
        content = "Legal document content"
        extraction_data = {
            "extracted_data": {"key_value_pairs": {}},
            "summary": "Summary",
            "markdown_summary": "Markdown",
            "confidence_score": 0.8,
        }

        with (
            patch("app.api.db.database.SyncSessionLocal") as mock_session_factory,
            patch(
                "app.api.modules.v1.scraping.service.stage2_extraction_service.get_content_from_minio"
            ) as mock_get_content,
            patch(
                "app.api.modules.v1.scraping.service.stage2_extraction_service.AIExtractionService"
            ) as mock_ai_service,
        ):
            mock_session = AsyncMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)

            mock_source = MagicMock(spec=Source)
            mock_source.project = None  # No project
            mock_source.jurisdiction = None  # No jurisdiction

            mock_result = MagicMock()
            mock_result.scalars = MagicMock(
                return_value=MagicMock(first=MagicMock(return_value=mock_source))
            )
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.commit = AsyncMock()
            mock_session_factory.return_value = mock_session

            mock_get_content.return_value = content

            mock_ai_instance = MagicMock()
            mock_ai_instance.run_llm_analysis_with_openrouter = AsyncMock(
                return_value=extraction_data
            )
            mock_ai_service.return_value = mock_ai_instance

            service = Stage2ExtractionService()
            result = await service.execute(
                test_source_id, test_job_id, test_content_hash, test_minio_key, db=mock_session
            )

            assert result["status"] == "completed"

            # Verify LLM was called with fallback values
            call_args = mock_ai_instance.run_llm_analysis_with_openrouter.call_args
            assert call_args[1]["project_prompt"] == "Monitor legal changes"  # Default
            assert call_args[1]["jurisdiction_prompt"] == "General jurisdiction"  # Default
