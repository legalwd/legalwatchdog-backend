"""
Service layer for Parallel.ai monitoring operations.
Handles all business logic and database interactions.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.custom_exceptions.exceptions import (
    InvalidDateRangeError,
    ParallelProviderConnectionError,
    ParallelQueryError,
    ParallelUsageError,
)
from app.api.core.parallel.usage_tracker import ParallelUsageTracker

logger = logging.getLogger(__name__)


class ParallelMonitoringService:
    """
    Service class for Parallel.ai monitoring business logic.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the Parallel.ai monitoring service.

        Args:
            db (AsyncSession): Database session for querying Parallel.ai usage data
        """
        self.db = db
        self.tracker = ParallelUsageTracker()

    async def get_usage_stats(
        self,
        days: int = 30,
    ) -> Dict:
        """
        Get comprehensive Parallel.ai usage statistics.

        Args:
            days: Number of days to analyze (1-365).

        Returns:
            dict: Comprehensive usage statistics

        Raises:
            InvalidDateRangeError: If date range exceeds limits
            ParallelUsageError: If unable to retrieve usage statistics
            ParallelProviderError: If Parallel.ai service is unavailable
        """
        try:
            self._validate_days(days)
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            stats = await self.tracker.get_usage_stats(
                db=self.db,
                start_date=start_date,
            )

            total_content_mb = stats["total_content_mb"]
            total_requests = stats["total_requests"]
            avg_content_kb = (
                round((total_content_mb * 1024) / total_requests, 2) if total_requests > 0 else 0.0
            )

            return {
                "total_requests": stats["total_requests"],
                "successful_requests": stats["successful_requests"],
                "failed_requests": stats["failed_requests"],
                "success_rate": stats["success_rate"],
                "total_cost": str(stats["total_cost_usd"]),
                "avg_latency_ms": stats["avg_latency_ms"],
                "total_content_mb": total_content_mb,
                "avg_content_kb": avg_content_kb,
            }

        except InvalidDateRangeError:
            logger.error(f"Invalid days parameter: days={days}")
            raise
        except ConnectionError as e:
            logger.exception(f"Parallel.ai service unavailable: {str(e)}")

            raise ParallelProviderConnectionError("Parallel.ai service is currently unavailable")
        except Exception as e:
            logger.exception(f"Failed to get Parallel.ai usage stats: {str(e)}")
            raise ParallelUsageError("Failed to retrieve Parallel.ai usage statistics")

    async def get_usage_by_endpoint(
        self,
        days: int = 30,
    ) -> List[Dict]:
        """
        Get Parallel.ai usage breakdown by API endpoint.

        Args:
            days: Number of days to analyze (1-365).

        Returns:
            list: Endpoint usage breakdown

        Raises:
            InvalidDateRangeError: If date range exceeds limits
            ParallelQueryError: If unable to retrieve endpoint usage data
            ParallelProviderError: If Parallel.ai service is unavailable
        """
        try:
            self._validate_days(days)
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            endpoint_usage = await self.tracker.get_usage_by_endpoint(
                db=self.db,
                start_date=start_date,
            )

            for item in endpoint_usage:
                item["total_cost"] = str(item["total_cost_usd"])
                del item["total_cost_usd"]

            return endpoint_usage

        except InvalidDateRangeError:
            logger.error(f"Invalid days parameter: days={days}")
            raise
        except ConnectionError as e:
            logger.exception(f"Parallel.ai service unavailable: {str(e)}")

            raise ParallelProviderConnectionError("Parallel.ai service is currently unavailable")
        except Exception as e:
            logger.exception(f"Failed to get usage by endpoint: {str(e)}")
            raise ParallelQueryError("Failed to retrieve Parallel.ai usage by endpoint")

    async def get_usage_by_user(
        self,
        days: int = 30,
        limit: int = 20,
    ) -> List[Dict]:
        """
        Get Parallel.ai usage breakdown by user.

        Args:
            days: Number of days to analyze (1-365).
            limit: Number of top users to return (1-100).

        Returns:
            list: User usage breakdown

        Raises:
            InvalidDateRangeError: If parameters exceed allowed values
            ParallelQueryError: If unable to retrieve user usage data
            ParallelProviderError: If Parallel.ai service is unavailable
        """
        try:
            self._validate_days(days)
            self._validate_limit(limit, max_limit=100)

            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            user_usage_detailed = await self.tracker.get_usage_by_user_detailed(
                db=self.db,
                start_date=start_date,
                limit=limit,
            )

            user_usage = [
                {
                    "user_id": item["user_id"],
                    "email": item["user_email"],
                    "request_count": item["request_count"],
                    "successful_requests": item["successful_requests"],
                    "failed_requests": item["failed_requests"],
                    "total_cost": str(item["total_cost_usd"]),
                    "avg_latency_ms": item["avg_latency_ms"],
                }
                for item in user_usage_detailed
            ]

            return user_usage

        except InvalidDateRangeError:
            logger.error(f"Invalid parameters: days={days}, limit={limit}")
            raise
        except ConnectionError as e:
            logger.exception(f"Parallel.ai service unavailable: {str(e)}")

            raise ParallelProviderConnectionError("Parallel.ai service is currently unavailable")
        except Exception as e:
            logger.exception(f"Failed to get usage by user: {str(e)}")
            raise ParallelQueryError("Failed to retrieve Parallel.ai usage by user")

    async def get_cost_breakdown(
        self,
        days: int = 30,
    ) -> List[Dict]:
        """
        Get daily Parallel.ai cost breakdown for trend analysis.

        Args:
            days: Number of days to analyze (1-365).

        Returns:
            list: Daily cost breakdown

        Raises:
            InvalidDateRangeError: If date range exceeds limits
            ParallelQueryError: If unable to retrieve cost breakdown
            ParallelProviderError: If Parallel.ai service is unavailable
        """
        try:
            self._validate_days(days)
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            daily_costs_data = await self.tracker.get_daily_cost_breakdown(
                db=self.db,
                start_date=start_date,
            )

            daily_costs = [
                {
                    "date": item["date"],
                    "request_count": item["request_count"],
                    "successful_requests": item["successful_requests"],
                    "failed_requests": item["failed_requests"],
                    "total_cost": str(item["total_cost_usd"]),
                }
                for item in daily_costs_data
            ]

            return daily_costs

        except InvalidDateRangeError:
            logger.error(f"Invalid days parameter: days={days}")
            raise
        except ConnectionError as e:
            logger.exception(f"Parallel.ai service unavailable: {str(e)}")

            raise ParallelProviderConnectionError("Parallel.ai service is currently unavailable")
        except Exception as e:
            logger.exception(f"Failed to get cost breakdown: {str(e)}")
            raise ParallelQueryError("Failed to retrieve Parallel.ai cost breakdown")

    async def get_recent_errors(
        self,
        limit: int = 50,
    ) -> List[Dict]:
        """
        Get recent Parallel.ai extraction errors for troubleshooting.

        Args:
            limit: Number of recent errors to return (1-200).

        Returns:
            list: Recent error details

        Raises:
            InvalidDateRangeError: If limit exceeds allowed value
            ParallelQueryError: If unable to retrieve recent errors
            ParallelProviderError: If Parallel.ai service is unavailable
        """
        try:
            self._validate_limit(limit, max_limit=200)

            recent_errors = await self.tracker.get_recent_errors(
                db=self.db,
                limit=limit,
            )

            return recent_errors

        except InvalidDateRangeError:
            logger.error(f"Invalid limit parameter: limit={limit}")
            raise
        except ConnectionError as e:
            logger.exception(f"Parallel.ai service unavailable: {str(e)}")

            raise ParallelProviderConnectionError("Parallel.ai service is currently unavailable")
        except Exception as e:
            logger.exception(f"Failed to get recent errors: {str(e)}")
            raise ParallelQueryError("Failed to retrieve recent Parallel.ai errors")

    async def get_usage_by_organization(
        self,
        days: int = 30,
    ) -> List[Dict]:
        """
        Get detailed Parallel.ai usage breakdown by organization.

        Args:
            days: Number of days to analyze (1-365).

        Returns:
            list: Organization usage breakdown

        Raises:
            InvalidDateRangeError: If date range exceeds limits
            ParallelQueryError: If unable to retrieve organization usage data
            ParallelProviderError: If Parallel.ai service is unavailable
        """
        try:
            self._validate_days(days)
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            organization_usage = await self.tracker.get_usage_by_organization_detailed(
                db=self.db,
                start_date=start_date,
            )

            return organization_usage

        except InvalidDateRangeError:
            logger.error(f"Invalid days parameter: days={days}")
            raise
        except ConnectionError as e:
            logger.exception(f"Parallel.ai service unavailable: {str(e)}")
            raise ParallelProviderConnectionError("Parallel.ai service is currently unavailable")
        except Exception as e:
            logger.exception(f"Failed to get organization usage: {str(e)}")
            raise ParallelQueryError("Failed to retrieve Parallel.ai usage by organization")

    async def get_usage_by_project(
        self,
        organization_id: Optional[UUID] = None,
        days: int = 30,
    ) -> List[Dict]:
        """
        Get Parallel.ai usage breakdown by project.

        Args:
            organization_id: Optional organization filter.
            days: Number of days to analyze (1-365).

        Returns:
            list: Project usage breakdown

        Raises:
            InvalidDateRangeError: If date range exceeds limits
            ParallelQueryError: If unable to retrieve project usage data
            ParallelProviderError: If Parallel.ai service is unavailable
        """
        try:
            self._validate_days(days)
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            project_usage = await self.tracker.get_usage_by_project(
                db=self.db,
                organization_id=organization_id,
                start_date=start_date,
            )

            return project_usage

        except InvalidDateRangeError:
            logger.error(f"Invalid days parameter: days={days}")
            raise
        except ConnectionError as e:
            logger.exception(f"Parallel.ai service unavailable: {str(e)}")

            raise ParallelProviderConnectionError("Parallel.ai service is currently unavailable")
        except Exception as e:
            logger.exception(f"Failed to get project usage: {str(e)}")
            raise ParallelQueryError("Failed to retrieve Parallel.ai usage by project")

    async def get_detailed_logs(
        self,
        user_id: Optional[UUID] = None,
        organization_id: Optional[UUID] = None,
        project_id: Optional[UUID] = None,
        days: int = 7,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict:
        """
        Get detailed Parallel.ai request logs with full attribution.

        Args:
            user_id: Optional user filter.
            organization_id: Optional organization filter.
            project_id: Optional project filter.
            days: Number of days to analyze (1-90).
            limit: Number of logs to return (1-500).
            offset: Pagination offset.

        Returns:
            dict: Paginated log results

        Raises:
            InvalidDateRangeError: If parameters exceed allowed values
            ParallelQueryError: If unable to retrieve detailed logs
            ParallelProviderError: If Parallel.ai service is unavailable
        """
        try:
            self._validate_days(days, max_days=90)
            self._validate_limit(limit, max_limit=500)

            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            logs_data = await self.tracker.get_detailed_logs(
                db=self.db,
                user_id=user_id,
                organization_id=organization_id,
                project_id=project_id,
                start_date=start_date,
                limit=limit,
                offset=offset,
            )

            return logs_data

        except InvalidDateRangeError:
            logger.error(f"Invalid parameters: days={days}, limit={limit}")
            raise
        except ConnectionError as e:
            logger.exception(f"Parallel.ai service unavailable: {str(e)}")

            raise ParallelProviderConnectionError("Parallel.ai service is currently unavailable")
        except Exception as e:
            logger.exception(f"Failed to get detailed logs: {str(e)}")
            raise ParallelQueryError("Failed to retrieve detailed Parallel.ai logs")

    def _validate_days(self, days: int, max_days: int = 365) -> None:
        """
        Validate that days parameter is within allowed range.

        Args:
            days: Number of days to validate
            max_days: Maximum allowed days (default: 365)

        Raises:
            InvalidDateRangeError: If days is outside allowed range
        """
        if days < 1 or days > max_days:
            raise InvalidDateRangeError(f"Days must be between 1 and {max_days}")

    def _validate_limit(self, limit: int, max_limit: int) -> None:
        """
        Validate that limit parameter is within allowed range.

        Args:
            limit: Limit to validate
            max_limit: Maximum allowed limit

        Raises:
            InvalidDateRangeError: If limit is outside allowed range
        """
        if limit < 1 or limit > max_limit:
            raise InvalidDateRangeError(f"Limit must be between 1 and {max_limit}")
