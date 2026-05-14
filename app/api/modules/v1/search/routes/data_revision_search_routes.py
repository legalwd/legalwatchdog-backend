import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.search.schemas.search_schema import SearchRequest
from app.api.modules.v1.search.service.search_service import SearchService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import success_response

from .docs.data_revision_search_routes_docs import (
    search_data_revisions_custom_errors,
    search_data_revisions_custom_success,
    search_data_revisions_responses,
)

router = APIRouter(
    prefix="/data-revisions",
    tags=["Data Revision Search"],
)

logger = logging.getLogger("app")


@router.post(
    "/",
    status_code=status.HTTP_200_OK,
    responses=search_data_revisions_responses,
)
async def search_data_revisions(
    payload: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Perform full-text search on data revisions across all sources.

    This endpoint searches through data revisions using PostgreSQL's full-text
    search capabilities. Results include all data revisions the user has access to.

    Args:
        payload (SearchRequest): Search parameters including:
            - query (str): Search query text (required, min 1 char, max 500 chars)
            - operator (SearchOperator): Search operator - AND, OR, NOT, or PHRASE
              (default: AND)
            - page (int): Page number for pagination (default: 1, min: 1)
            - limit (int): Results per page (default: 20, min: 1, max: 100)
            - min_rank (float): Minimum relevance score (default: 0.0, range: 0.0-1.0)
            - extracted_data_filters (dict): Key-value filters for JSON fields
              (keys must be alphanumeric with underscores only)
        current_user (User): The authenticated user performing the search.
        db (AsyncSession): Database session for query execution.

    Returns:
        JSONResponse: Success response containing:
            - status (str): "success"
            - message (str): "Data revision search successful"
            - data (SearchResponse): Search results with:
                - results (List[DataRevisionSearchResult]): Matching data revisions
                - total (int): Total number of matches across all pages
                - page (int): Current page number
                - limit (int): Results per page
                - total_pages (int): Total number of pages available
                - query (str): The search query used
                - operator (SearchOperator): The operator used

    Raises:
        HTTPException:
            - 400 Bad Request if:
                - Search query is empty or invalid
                - Filter keys contain invalid characters
                - Query contains no valid search terms after sanitization
            - 401 Unauthorized if authentication fails
            - 403 Forbidden if user lacks permission to search data revisions
            - 500 Internal Server Error if search processing fails
    """
    logger.info(
        f"Searching data revisions: user_id={current_user.id}, "
        f"query='{payload.query}', operator={payload.operator}"
    )

    search_service = SearchService(db)
    search_response = await search_service.search(payload)

    logger.info(
        f"Data revision search successful: user_id={current_user.id}, "
        f"total_results={search_response.total}, "
        f"returned={len(search_response.results)}"
    )

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Data revision search successful",
        data=search_response.model_dump(),
    )


search_data_revisions._custom_errors = search_data_revisions_custom_errors
search_data_revisions._custom_success = search_data_revisions_custom_success
