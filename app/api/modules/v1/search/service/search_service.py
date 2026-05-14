import json
import logging
import re
from typing import Any

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from sqlmodel import select

from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.search.schemas.search_schema import (
    DataRevisionSearchResult,
    SearchOperator,
    SearchRequest,
    SearchResponse,
)

logger = logging.getLogger(__name__)


class SearchService:
    """Service for performing full-text search on DataRevision entities."""

    def __init__(self, db: AsyncSession):
        """
        Initialize the search service.

        Args:
            db: Async database session
        """
        self.db = db

    async def search(self, search_request: SearchRequest) -> SearchResponse:
        """
        Perform full-text search on data revisions.

        Args:
            search_request: Search parameters including query, filters, and pagination

        Returns:
            SearchResponse: Paginated search results with relevance scores

        Raises:
            BadRequestError: For invalid search parameters
            ProcessingError: For unexpected processing errors
        """
        from app.api.core.custom_exceptions.exceptions import (
            BadRequestError,
            ProcessingError,
        )

        try:
            if not search_request.query or not search_request.query.strip():
                raise BadRequestError("Search query cannot be empty")

            tsquery = self._build_tsquery(search_request.query, search_request.operator)

            if not tsquery:
                raise BadRequestError("Search query resulted in no valid search terms")

            relevance_score_col = func.ts_rank(
                DataRevision.search_vector, func.to_tsquery("english", tsquery)
            ).label("relevance_score")

            base_filters: list[Any] = [
                DataRevision.search_vector.op("@@")(func.to_tsquery("english", tsquery)),
            ]

            statement = select(DataRevision, relevance_score_col).filter(*base_filters)
            statement = self._apply_filters(statement, search_request)

            count_statement = select(func.count()).select_from(DataRevision).filter(*base_filters)
            count_statement = self._apply_filters(count_statement, search_request)

            count_result = await self.db.execute(count_statement)
            total_count = count_result.scalar() or 0

            if total_count == 0:
                logger.info(f"No results found for query: '{search_request.query}'")
                return SearchResponse(
                    results=[],
                    total=0,
                    page=search_request.page,
                    limit=search_request.limit,
                    total_pages=0,
                    query=search_request.query,
                    operator=search_request.operator,
                )

            offset = (search_request.page - 1) * search_request.limit
            total_pages = (total_count + search_request.limit - 1) // search_request.limit

            statement = (
                statement.order_by(relevance_score_col.desc())
                .filter(relevance_score_col >= search_request.min_rank)
                .offset(offset)
                .limit(search_request.limit)
            )

            results_result = await self.db.execute(statement)
            results = results_result.all()

            search_results = [
                DataRevisionSearchResult(
                    id=result.DataRevision.id,
                    title=result.DataRevision.minio_object_key,
                    summary=result.DataRevision.ai_summary,
                    content=None,
                    key_fields=result.DataRevision.extracted_data or {},
                    revision_date=result.DataRevision.scraped_at,
                    relevance_score=result.relevance_score,
                )
                for result in results
            ]

            logger.info(
                f"Search completed: {len(search_results)} results returned "
                f"({total_count} total matches)"
            )

            return SearchResponse(
                results=search_results,
                total=total_count,
                page=search_request.page,
                limit=search_request.limit,
                total_pages=total_pages,
                query=search_request.query,
                operator=search_request.operator,
            )
        except BadRequestError:
            raise
        except Exception as e:
            logger.error(
                f"Search failed for query='{search_request.query}': {str(e)}", exc_info=True
            )
            raise ProcessingError("Failed to search data revisions. Please try again.") from e

    def _build_tsquery(self, query: str, operator: SearchOperator) -> str:
        """
        Build a PostgreSQL tsquery string from the search query.
        Sanitizes input to prevent tsquery syntax errors.

        Args:
            query: Raw search query string
            operator: Search operator (AND, OR, NOT, PHRASE)

        Returns:
            str: Formatted tsquery string for PostgreSQL
        """
        query = query.strip()

        def sanitize_term(term: str) -> str:
            return re.sub(r"[&|!()<>*:]", "", term).strip()

        if operator == SearchOperator.AND:
            terms = [sanitize_term(t) for t in query.split() if sanitize_term(t)]
            tsquery = " & ".join(terms) if terms else ""
        elif operator == SearchOperator.OR:
            terms = [sanitize_term(t) for t in query.split() if sanitize_term(t)]
            tsquery = " | ".join(terms) if terms else ""
        elif operator == SearchOperator.NOT:
            terms = [sanitize_term(t) for t in query.split() if sanitize_term(t)]
            if not terms:
                tsquery = ""
            elif len(terms) == 1:
                tsquery = f"!{terms[0]}"
            else:
                tsquery = f"{terms[0]} & !({' | '.join(terms[1:])})"
        else:
            sanitized = sanitize_term(query)
            tsquery = " <-> ".join(sanitized.split()) if sanitized else ""

        return tsquery

    def _apply_filters(self, query: Select, search_request: SearchRequest) -> Select:
        """
        Apply filters to the search query.

        Args:
            query: SQLAlchemy select statement
            search_request: Search request containing filter parameters

        Returns:
            Modified select statement with applied filters

        Raises:
            BadRequestError: If filter keys contain invalid characters
        """
        from app.api.core.custom_exceptions.exceptions import BadRequestError

        for key, value in search_request.extracted_data_filters.items():
            if not re.match(r"^[a-zA-Z0-9_]+$", key):
                raise BadRequestError(
                    f"Invalid filter key: '{key}'. Only alphanumeric characters "
                    "and underscores are allowed."
                )

            if isinstance(value, (dict, list)):
                value_str = json.dumps(value, separators=(",", ":"))
            else:
                value_str = str(value)

            query = query.filter(DataRevision.extracted_data.op("->>")(key) == value_str)

        return query
