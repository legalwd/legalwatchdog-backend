import logging

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.db.database import get_db
from app.api.modules.v1.scraping.routes.docs.output_routes_docs import (
    download_latest_markdown_custom_errors,
    download_latest_markdown_custom_success,
    download_latest_markdown_responses,
    download_revision_markdown_custom_errors,
    download_revision_markdown_custom_success,
    download_revision_markdown_responses,
    view_latest_revision_custom_errors,
    view_latest_revision_custom_success,
    view_latest_revision_responses,
    view_revision_custom_errors,
    view_revision_custom_success,
    view_revision_responses,
)
from app.api.modules.v1.scraping.service.output_service import OutputService
from app.api.utils.response_payloads import success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/output", tags=["Scrape Output"])


@router.get(
    "/revision/{revision_id}/download",
    status_code=status.HTTP_200_OK,
    responses=download_revision_markdown_responses,
)
async def download_revision_markdown(
    revision_id: str,
    include_metadata: bool = Query(
        True, description="Include metadata header with source info and scrape details"
    ),
    db: AsyncSession = Depends(get_db),
):
    """
        Download markdown content for a specific data revision.

        **Use Cases:**
        - Download a specific historical version
        - Export content for offline analysis
        - Archive specific scrape results

        **Response:**
        - Downloads as `.md` file with suggested filename
        - Includes optional YAML frontmatter with metadata
        - Content-Type: text/markdown

        **Example:**
    ```
        GET /api/v1/download/revision/abc-123/markdown?include_metadata=true
    ```
    """
    service = OutputService(db)
    payload = await service.get_revision_markdown_payload(revision_id, include_metadata)

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Revision markdown retrieved",
        data=payload,
    )


download_revision_markdown._custom_errors = download_revision_markdown_custom_errors
download_revision_markdown._custom_success = download_revision_markdown_custom_success


@router.get(
    "/source/{source_id}/latest",
    status_code=status.HTTP_200_OK,
    responses=download_latest_markdown_responses,
)
async def download_latest_markdown(
    source_id: str,
    include_metadata: bool = Query(
        True, description="Include metadata header with source info and scrape details"
    ),
    db: AsyncSession = Depends(get_db),
):
    """
        Download markdown content for the latest revision of a source.

        **Use Cases:**
        - Quick access to current content
        - Export most recent scrape
        - Get latest without knowing revision ID

        **Response:**
        - Downloads most recent revision as `.md` file
        - Automatically finds latest by scrape timestamp

        **Example:**
    ```
        GET /api/v1/download/source/xyz-789/latest/markdown
    ```
    """
    service = OutputService(db)
    payload = await service.get_latest_revision_markdown_payload(source_id, include_metadata)

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Latest revision markdown retrieved",
        data=payload,
    )


download_latest_markdown._custom_errors = download_latest_markdown_custom_errors
download_latest_markdown._custom_success = download_latest_markdown_custom_success


@router.get(
    "/revision/{revision_id}/view",
    status_code=status.HTTP_200_OK,
    responses=view_revision_responses,
)
async def view_revision(
    revision_id: str,
    include_metadata: bool = Query(True, description="Include metadata in response"),
    db: AsyncSession = Depends(get_db),
):
    """
    View revision content for frontend display.

    Returns content in a format suitable for rendering in the UI.
    Use this for displaying content to users instead of downloading.

    **Formats:**
    - json (default): Structured data with markdown content
    - markdown: Raw markdown text
    - html: Pre-rendered HTML

    """
    service = OutputService(db)
    payload = await service.get_revision_for_display(revision_id, include_metadata)

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Revision retrieved for display",
        data=payload,
    )


view_revision._custom_errors = view_revision_custom_errors
view_revision._custom_success = view_revision_custom_success


@router.get(
    "/source/{source_id}/latest/view",
    status_code=status.HTTP_200_OK,
    responses=view_latest_revision_responses,
)
async def view_latest_revision(
    source_id: str, include_metadata: bool = Query(True), db: AsyncSession = Depends(get_db)
):
    """
    View the latest revision of a source for frontend display.
    """
    service = OutputService(db)
    payload = await service.get_latest_revision_for_display(source_id, include_metadata)

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Latest revision retrieved for display",
        data=payload,
    )


view_latest_revision._custom_errors = view_latest_revision_custom_errors
view_latest_revision._custom_success = view_latest_revision_custom_success
