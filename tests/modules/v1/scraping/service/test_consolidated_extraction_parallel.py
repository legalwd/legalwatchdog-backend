"""Unit tests for consolidated extraction service parallel helpers and notification batching."""

from unittest.mock import MagicMock, patch

from app.api.modules.v1.scraping.service.consolidated_extraction_service import (
    ConsolidatedExtractionService,
)


def test_gather_content_parallel_fetches_all_sources():
    """_gather_content should fetch all MinIO sources and preserve order."""
    mock_db = MagicMock()
    mock_job = MagicMock()
    mock_job.id = "test-job-id"

    mock_sj1 = MagicMock()
    mock_sj1.source_id = "src-1"
    mock_sj1.result = {"minio_key": "key1"}

    mock_sj2 = MagicMock()
    mock_sj2.source_id = "src-2"
    mock_sj2.result = {"minio_key": "key2"}

    mock_db.exec.return_value.all.return_value = [mock_sj1, mock_sj2]

    mock_source1 = MagicMock()
    mock_source1.id = "src-1"
    mock_source1.name = "Source One"
    mock_source1.url = "https://source1.gov"

    mock_source2 = MagicMock()
    mock_source2.id = "src-2"
    mock_source2.name = "Source Two"
    mock_source2.url = "https://source2.com"

    mock_db.exec.return_value.all.side_effect = [
        [mock_sj1, mock_sj2],
        [mock_source1, mock_source2],
    ]

    service = ConsolidatedExtractionService(mock_db)

    with patch.object(
        service,
        "llm_service",
    ):
        with patch(
            "app.api.modules.v1.scraping.service.consolidated_extraction_service.minio_storage"
        ) as mock_minio:
            mock_minio.get_content_from_minio.side_effect = [
                b"content one",
                b"content two",
            ]
            results = service._gather_content(mock_job)

    assert len(results) == 2
    assert results[0]["source_name"] == "Source One"
    assert results[0]["content"] == "content one"
    assert results[1]["source_name"] == "Source Two"
    assert results[1]["content"] == "content two"


def test_gather_content_handles_minio_failures_gracefully():
    """_gather_content should skip failed sources and return successful ones."""
    mock_db = MagicMock()
    mock_job = MagicMock()
    mock_job.id = "test-job-id"

    mock_sj1 = MagicMock()
    mock_sj1.source_id = "src-1"
    mock_sj1.result = {"minio_key": "key1"}

    mock_sj2 = MagicMock()
    mock_sj2.source_id = "src-2"
    mock_sj2.result = {"minio_key": "key2"}

    mock_source1 = MagicMock()
    mock_source1.id = "src-1"
    mock_source1.name = "Source One"
    mock_source1.url = "https://source1.gov"

    mock_db.exec.return_value.all.side_effect = [
        [mock_sj1, mock_sj2],
        [mock_source1],
    ]

    service = ConsolidatedExtractionService(mock_db)

    with patch.object(service, "llm_service"):
        with patch(
            "app.api.modules.v1.scraping.service.consolidated_extraction_service.minio_storage"
        ) as mock_minio:
            mock_minio.get_content_from_minio.side_effect = [
                b"content one",
                Exception("MinIO connection refused"),
            ]
            results = service._gather_content(mock_job)

    assert len(results) == 1
    assert results[0]["source_name"] == "Source One"


def test_filter_content_parallel_filters_all_items():
    """_filter_content should filter items using parallel LLM calls."""
    mock_db = MagicMock()
    service = ConsolidatedExtractionService(mock_db)

    mock_llm = MagicMock()
    mock_llm.check_source_relevance.side_effect = [True, False, True]
    service.llm_service = mock_llm

    items = [
        {"source_url": "https://a.gov", "content": "relevant content"},
        {"source_url": "https://b.com", "content": "irrelevant content"},
        {"source_url": "https://c.org", "content": "also relevant"},
    ]

    results = service._filter_content(items, "test prompt")

    assert len(results) == 2
    assert results[0]["source_url"] == "https://a.gov"
    assert results[1]["source_url"] == "https://c.org"
    assert mock_llm.check_source_relevance.call_count == 3


def test_filter_content_handles_llm_failures_gracefully():
    """_filter_content should treat failed LLM checks as non-relevant."""
    mock_db = MagicMock()
    service = ConsolidatedExtractionService(mock_db)

    mock_llm = MagicMock()
    mock_llm.check_source_relevance.side_effect = [
        True,
        Exception("LLM rate limit exceeded"),
        True,
    ]
    service.llm_service = mock_llm

    items = [
        {"source_url": "https://a.gov", "content": "relevant"},
        {"source_url": "https://b.com", "content": "will fail"},
        {"source_url": "https://c.org", "content": "relevant"},
    ]

    results = service._filter_content(items, "test prompt")

    assert len(results) == 2
    assert results[0]["source_url"] == "https://a.gov"
    assert results[1]["source_url"] == "https://c.org"


def test_send_notifications_batch_creates_all_rows():
    """_send_jurisdiction_notifications should create all notification rows in one commit."""
    mock_db = MagicMock()
    mock_job = MagicMock()
    mock_job.id = "test-job-id"
    mock_job.extracted_data = {"change_detection": {"change_summary": "test", "risk_level": "LOW"}}

    mock_jurisdiction = MagicMock()
    mock_jurisdiction.id = "jur-1"
    mock_jurisdiction.name = "Test Jurisdiction"
    mock_jurisdiction.project_id = "proj-1"

    mock_project = MagicMock()
    mock_project.id = "proj-1"
    mock_project.org_id = "org-1"

    mock_user1 = MagicMock()
    mock_user1.id = "user-1"
    mock_user1.email = "user1@example.com"
    mock_user1.name = "User One"

    mock_user2 = MagicMock()
    mock_user2.id = "user-2"
    mock_user2.email = "user2@example.com"
    mock_user2.name = "User Two"

    mock_pu1 = MagicMock()
    mock_pu1.user_id = "user-1"
    mock_pu2 = MagicMock()
    mock_pu2.user_id = "user-2"

    mock_db.get.side_effect = lambda model, id_val: {
        "proj-1": mock_project,
        "user-1": mock_user1,
        "user-2": mock_user2,
    }.get(id_val)

    mock_db.exec.return_value.all.side_effect = [
        [mock_pu1, mock_pu2],
        [mock_user1, mock_user2],
    ]

    service = ConsolidatedExtractionService(mock_db)

    with patch.object(service, "llm_service"):
        with patch(
            "app.api.modules.v1.scraping.service.consolidated_extraction_service.syncify"
        ) as mock_syncify:
            mock_syncify.return_value.return_value = True
            service._send_jurisdiction_notifications(mock_job, mock_jurisdiction)

    assert mock_db.commit.call_count == 2
    assert mock_db.add.call_count >= 2
