"""Service for LLM monitoring and analytics operations."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.custom_exceptions.exceptions import (
    InvalidDateRangeError,
    LLMProviderError,
    LLMQueryError,
    LLMUsageError,
)
from app.api.core.llm.llm_manager import LLMManager
from app.api.core.llm.usage_tracker import LLMUsageTracker

logger = logging.getLogger(__name__)


class LLMMonitoringService:
    """
    Service class for LLM monitoring business logic.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the LLM monitoring service.

        Args:
            db (AsyncSession): Database session for querying LLM usage data
        """
        self.db = db
        self.tracker = LLMUsageTracker()

    async def get_usage_stats(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        user_id: Optional[UUID] = None,
        organization_id: Optional[UUID] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> dict:
        """
        Get comprehensive LLM usage statistics.

        Args:
            start_date: Start date in ISO format (YYYY-MM-DD)
            end_date: End date in ISO format (YYYY-MM-DD)
            user_id: Filter statistics by specific user
            organization_id: Filter statistics by organization
            provider: Filter by LLM provider
            model: Filter by specific model

        Returns:
            dict: Comprehensive usage statistics

        Raises:
            InvalidDateRangeError: If date format is invalid or range exceeds limits
            LLMUsageError: If unable to retrieve usage statistics
        """
        try:
            start_dt = self._parse_start_date(start_date)
            end_dt = self._parse_end_date(end_date)

            self._validate_date_range(start_dt, end_dt)

            stats = await self.tracker.get_usage_stats(
                db=self.db,
                start_date=start_dt,
                end_date=end_dt,
                user_id=user_id,
                organization_id=organization_id,
                provider=provider,
                model=model,
            )

            return stats

        except InvalidDateRangeError:
            logger.error(f"Invalid date range: start_date={start_date}, end_date={end_date}")
            raise
        except Exception as e:
            logger.exception(f"Failed to get LLM usage stats: {str(e)}")
            raise LLMUsageError("Failed to retrieve LLM usage statistics")

    async def get_usage_by_provider(
        self,
        days: int = 30,
        organization_id: Optional[UUID] = None,
    ) -> list:
        """
        Get LLM usage breakdown by provider.

        Args:
            days: Number of days to analyze (1-365)
            organization_id: Filter data by specific organization

        Returns:
            list: Provider usage breakdown

        Raises:
            InvalidDateRangeError: If date range exceeds limits
            LLMQueryError: If unable to retrieve provider usage data
        """
        try:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            return await self.tracker.get_usage_by_provider(
                db=self.db,
                start_date=start_date,
                organization_id=organization_id,
            )
        except InvalidDateRangeError:
            logger.error(f"Invalid date range: days={days}")
            raise
        except Exception as e:
            logger.exception(f"Failed to get usage by provider: {str(e)}")
            raise LLMQueryError("Failed to retrieve usage by provider")

    async def get_usage_by_model(
        self,
        days: int = 30,
        provider: Optional[str] = None,
        organization_id: Optional[UUID] = None,
    ) -> list:
        """
        Get LLM usage breakdown by model.

        Args:
            days: Number of days to analyze (1-365)
            provider: Filter by specific provider
            organization_id: Filter data by specific organization

        Returns:
            list: Model usage breakdown

        Raises:
            InvalidDateRangeError: If date range exceeds limits
            LLMQueryError: If unable to retrieve model usage data
        """
        try:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            return await self.tracker.get_usage_by_model(
                db=self.db,
                start_date=start_date,
                provider=provider,
                organization_id=organization_id,
            )
        except InvalidDateRangeError:
            logger.error(f"Invalid date range: days={days}")
            raise
        except Exception as e:
            logger.exception(f"Failed to get usage by model: {str(e)}")
            raise LLMQueryError("Failed to retrieve usage by model")

    async def get_usage_by_endpoint(
        self,
        days: int = 30,
        organization_id: Optional[UUID] = None,
    ) -> list:
        """
        Get LLM usage breakdown by API endpoint.

        Args:
            days: Number of days to analyze (1-365)
            organization_id: Filter data by specific organization

        Returns:
            list: Endpoint usage breakdown

        Raises:
            InvalidDateRangeError: If date range exceeds limits
            LLMQueryError: If unable to retrieve endpoint usage data
        """
        try:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            return await self.tracker.get_usage_by_endpoint(
                db=self.db,
                start_date=start_date,
                organization_id=organization_id,
            )
        except InvalidDateRangeError:
            logger.error(f"Invalid date range: days={days}")
            raise
        except Exception as e:
            logger.exception(f"Failed to get usage by endpoint: {str(e)}")
            raise LLMQueryError("Failed to retrieve usage by endpoint")

    async def get_usage_trends(
        self,
        days: int = 30,
        granularity: str = "day",
        organization_id: Optional[UUID] = None,
    ) -> list:
        """
        Get LLM usage trends over time.

        Args:
            days: Number of days to analyze (1-365)
            granularity: Time aggregation level: 'hour', 'day', 'week', or 'month'
            organization_id: Filter data by specific organization

        Returns:
            list: Time-series trends

        Raises:
            InvalidDateRangeError: If granularity is invalid or date range exceeds limits
            LLMQueryError: If unable to retrieve usage trends
        """
        try:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            if granularity not in ["hour", "day", "week", "month"]:
                raise InvalidDateRangeError("Granularity must be one of: hour, day, week, month")

            return await self.tracker.get_usage_trends(
                db=self.db,
                start_date=start_date,
                granularity=granularity,
                organization_id=organization_id,
            )
        except InvalidDateRangeError:
            logger.error(f"Invalid granularity: granularity={granularity}, days={days}")
            raise
        except Exception as e:
            logger.exception(f"Failed to get usage trends: {str(e)}")
            raise LLMQueryError("Failed to retrieve usage trends")

    async def get_provider_health(self) -> list:
        """
        Get health status of all LLM providers.

        Returns:
            list: Provider health status

        Raises:
            LLMProviderError: If unable to retrieve provider health status
        """
        try:
            return await self.tracker.get_provider_health(self.db)
        except Exception as e:
            logger.exception(f"Failed to get provider health: {str(e)}")
            raise LLMProviderError("Failed to retrieve provider health status")

    async def get_cost_breakdown(
        self,
        days: int = 30,
        organization_id: Optional[UUID] = None,
        group_by: str = "provider",
    ) -> list:
        """
        Get detailed cost breakdown of LLM usage.

        Args:
            days: Number of days to analyze (1-365)
            organization_id: Filter data by specific organization
            group_by: Dimension to group costs by

        Returns:
            list: Cost breakdown

        Raises:
            InvalidDateRangeError: If group_by value is invalid or date range exceeds limits
            LLMQueryError: If unable to retrieve cost breakdown
        """
        try:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            if group_by not in ["provider", "model", "endpoint", "user", "organization"]:
                raise InvalidDateRangeError(
                    "Group by must be one of: provider, model, endpoint, user, organization"
                )

            return await self.tracker.get_cost_breakdown(
                db=self.db,
                start_date=start_date,
                group_by=group_by,
                organization_id=organization_id,
            )
        except InvalidDateRangeError:
            logger.error(f"Invalid group_by parameter: group_by={group_by}")
            raise
        except Exception as e:
            logger.exception(f"Failed to get cost breakdown: {str(e)}")
            raise LLMQueryError("Failed to retrieve cost breakdown")

    async def get_usage_by_organization(self, days: int = 30) -> list:
        """
        Get LLM usage breakdown by organization.

        Args:
            days: Number of days to analyze (1-365)

        Returns:
            list: Organization usage

        Raises:
            InvalidDateRangeError: If date range exceeds limits
            LLMQueryError: If unable to retrieve organization usage data
        """
        try:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            return await self.tracker.get_usage_by_organization_detailed(
                db=self.db,
                start_date=start_date,
            )
        except InvalidDateRangeError:
            logger.error(f"Invalid date range: days={days}")
            raise
        except Exception as e:
            logger.exception(f"Failed to get organization usage: {str(e)}")
            raise LLMQueryError("Failed to retrieve organization usage data")

    async def get_usage_by_user(
        self,
        days: int = 30,
        organization_id: Optional[UUID] = None,
    ) -> list:
        """
        Get LLM usage breakdown by user.

        Args:
            days: Number of days to analyze (1-365)
            organization_id: Filter users by specific organization

        Returns:
            list: User usage

        Raises:
            InvalidDateRangeError: If date range exceeds limits
            LLMQueryError: If unable to retrieve user usage data
        """
        try:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            return await self.tracker.get_usage_by_user_detailed(
                db=self.db,
                organization_id=organization_id,
                start_date=start_date,
            )
        except InvalidDateRangeError:
            logger.error(f"Invalid date range: days={days}")
            raise
        except Exception as e:
            logger.exception(f"Failed to get user usage: {str(e)}")
            raise LLMQueryError("Failed to retrieve user usage data")

    async def get_usage_by_project(
        self,
        days: int = 30,
        organization_id: Optional[UUID] = None,
    ) -> list:
        """
        Get LLM usage breakdown by project.

        Args:
            days: Number of days to analyze (1-365)
            organization_id: Filter projects by specific organization

        Returns:
            list: Project usage

        Raises:
            InvalidDateRangeError: If date range exceeds limits
            LLMQueryError: If unable to retrieve project usage data
        """
        try:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            return await self.tracker.get_usage_by_project(
                db=self.db,
                organization_id=organization_id,
                start_date=start_date,
            )
        except InvalidDateRangeError:
            logger.error(f"Invalid date range: days={days}")
            raise
        except Exception as e:
            logger.exception(f"Failed to get project usage: {str(e)}")
            raise LLMQueryError("Failed to retrieve project usage data")

    async def get_detailed_logs(
        self,
        user_id: Optional[UUID] = None,
        organization_id: Optional[UUID] = None,
        project_id: Optional[UUID] = None,
        days: int = 7,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """
        Get detailed LLM request logs with full attribution.

        Args:
            user_id: Filter logs by specific user
            organization_id: Filter logs by organization
            project_id: Filter logs by project
            days: Number of days to look back (1-90)
            limit: Maximum number of logs to return (1-1000)
            offset: Pagination offset

        Returns:
            dict: Paginated log results

        Raises:
            InvalidDateRangeError: If date range or limit exceeds allowed values
            LLMQueryError: If unable to retrieve detailed logs
        """
        try:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            if days > 90:
                raise InvalidDateRangeError("Date range cannot exceed 90 days for detailed logs")

            if limit > 1000:
                raise InvalidDateRangeError("Limit cannot exceed 1000 records")

            return await self.tracker.get_detailed_logs(
                db=self.db,
                user_id=user_id,
                organization_id=organization_id,
                project_id=project_id,
                start_date=start_date,
                limit=limit,
                offset=offset,
            )
        except InvalidDateRangeError:
            logger.error(f"Invalid parameters: days={days}, limit={limit}")
            raise
        except Exception as e:
            logger.exception(f"Failed to get detailed logs: {str(e)}")
            raise LLMQueryError("Failed to retrieve detailed logs")

    async def test_connection(
        self,
        provider: str = "openrouter",
        model: Optional[str] = None,
        user_id: UUID = None,
    ) -> dict:
        """
        Test LLM provider connection and functionality.

        Args:
            provider: LLM provider to test
            model: Specific model to test
            user_id: User ID to associate with the test request

        Returns:
            dict: Connection test results

        Raises:
            LLMProviderError: If connection test fails or provider is unavailable
        """
        try:
            manager = LLMManager(
                db=self.db,
                provider_type=provider,
                enable_tracking=False,
            )

            test_prompt = "Respond with a single word: 'OK'"

            response = await manager.generate_with_tracking(
                prompt=test_prompt,
                model=model,
                temperature=0.0,
                max_tokens=10,
                user_id=str(user_id),
            )

            return {
                "provider": response.provider,
                "model": response.model,
                "latency_ms": response.usage_metrics.latency_ms,
                "status": "connected",
                "response_preview": response.content[:50],
            }

        except Exception as e:
            logger.exception(f"Connection test failed for {provider}: {str(e)}")
            raise LLMProviderError(f"Connection test failed for {provider}: {str(e)}")

    def _parse_start_date(self, start_date: Optional[str]) -> datetime:
        """
        Parse start date string to datetime object.

        Args:
            start_date: ISO format date string (YYYY-MM-DD) or None

        Returns:
            datetime: Parsed datetime, defaults to 30 days ago if None

        Raises:
            InvalidDateRangeError: If date format is invalid
        """
        if start_date:
            try:
                return datetime.fromisoformat(start_date)
            except ValueError:
                raise InvalidDateRangeError("Invalid start date format. Use YYYY-MM-DD format.")
        return datetime.now(timezone.utc) - timedelta(days=30)

    def _parse_end_date(self, end_date: Optional[str]) -> datetime:
        """
        Parse end date string to datetime object.

        Args:
            end_date: ISO format date string (YYYY-MM-DD) or None

        Returns:
            datetime: Parsed datetime, defaults to current time if None

        Raises:
            InvalidDateRangeError: If date format is invalid
        """
        if end_date:
            try:
                return datetime.fromisoformat(end_date)
            except ValueError:
                raise InvalidDateRangeError("Invalid end date format. Use YYYY-MM-DD format.")
        return datetime.now(timezone.utc)

    def _validate_date_range(self, start_dt: datetime, end_dt: datetime) -> None:
        """
        Validate that start date is before end date and within allowed range.

        Args:
            start_dt: Start datetime
            end_dt: End datetime

        Raises:
            InvalidDateRangeError: If start date is after end date or range exceeds 365 days
        """
        if start_dt >= end_dt:
            raise InvalidDateRangeError("Start date must be before end date")

        max_days = 365
        if (end_dt - start_dt).days > max_days:
            raise InvalidDateRangeError(f"Date range cannot exceed {max_days} days")
