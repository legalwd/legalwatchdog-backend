"""Parallel AI usage tracking service for monitoring and analytics.

This module provides a centralized service for tracking Parallel AI Extract API usage,
including cost analysis, performance metrics, and detailed request logging with full
attribution (user, organization, project).
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import Integer, cast, func, not_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.db.models.parallel_usage import ParallelUsageLog
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.users.models.users_model import User

logger = logging.getLogger(__name__)


class ParallelUsageTracker:
    """Service for tracking and analyzing Parallel AI Extract API usage.

    Provides methods for logging usage, retrieving statistics, and generating
    detailed reports with full attribution across users, organizations, and projects.
    """

    @staticmethod
    async def log_usage(
        db: AsyncSession,
        user_id: Optional[UUID] = None,
        organization_id: Optional[UUID] = None,
        project_id: Optional[UUID] = None,
        url_extracted: str = "",
        endpoint_name: str = "unknown",
        success: bool = False,
        cost: Decimal = Decimal("0"),
        latency_ms: int = 0,
        content_size_bytes: int = 0,
        error_message: Optional[str] = None,
    ) -> ParallelUsageLog:
        """Log a Parallel AI extraction request.

        Args:
            db: Database session.
            user_id: User who initiated the request.
            organization_id: Organization context.
            project_id: Project context for cost attribution.
            url_extracted: Target URL.
            endpoint_name: API endpoint name.
            success: Whether extraction succeeded.
            cost: API cost in USD.
            latency_ms: Request latency in milliseconds.
            content_size_bytes: Size of extracted content.
            error_message: Error details if failed.

        Returns:
            ParallelUsageLog: Created log entry.

        Examples:
            >>> log = await tracker.log_usage(
            ...     db=db,
            ...     user_id=user.id,
            ...     project_id=project.id,
            ...     url_extracted="https://example.com",
            ...     endpoint_name="scrape_source",
            ...     success=True,
            ...     cost=Decimal("0.001"),
            ...     latency_ms=1250
            ... )
        """
        try:
            log_entry = ParallelUsageLog(
                user_id=user_id,
                organization_id=organization_id,
                project_id=project_id,
                url_extracted=url_extracted,
                endpoint_name=endpoint_name,
                success=success,
                cost=cost,
                latency_ms=latency_ms,
                content_size_bytes=content_size_bytes,
                error_message=error_message,
            )

            db.add(log_entry)
            await db.commit()
            await db.refresh(log_entry)

            logger.info(
                f"Logged Parallel AI usage: endpoint={endpoint_name}, "
                f"success={success}, cost=${cost}, latency={latency_ms}ms"
            )

            return log_entry

        except Exception as e:
            logger.error(f"Failed to log Parallel AI usage: {e}", exc_info=True)
            await db.rollback()
            raise

    @staticmethod
    async def get_usage_stats(
        db: AsyncSession,
        user_id: Optional[UUID] = None,
        organization_id: Optional[UUID] = None,
        organization_ids: Optional[list[UUID]] = None,
        project_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> dict:
        """Get aggregated usage statistics.

        Args:
            db: Database session.
            user_id: Filter by user.
            organization_id: Filter by organization.
            organization_ids: Filter by multiple organizations.
            project_id: Filter by project.
            start_date: Start of date range.
            end_date: End of date range.

        Returns:
            dict: Statistics including total requests, cost, success rate, etc.
        """
        try:
            query = select(
                func.count(ParallelUsageLog.id).label("total_requests"),
                func.sum(cast(ParallelUsageLog.success, Integer)).label("successful_requests"),
                func.sum(ParallelUsageLog.cost).label("total_cost"),
                func.avg(ParallelUsageLog.latency_ms).label("avg_latency_ms"),
                func.sum(ParallelUsageLog.content_size_bytes).label("total_content_bytes"),
            )

            conditions = []
            if user_id:
                conditions.append(ParallelUsageLog.user_id == user_id)
            if organization_id:
                conditions.append(ParallelUsageLog.organization_id == organization_id)
            if organization_ids:
                conditions.append(ParallelUsageLog.organization_id.in_(organization_ids))
            if project_id:
                conditions.append(ParallelUsageLog.project_id == project_id)

            if conditions:
                query = query.where(or_(*conditions))

            if start_date:
                query = query.where(ParallelUsageLog.created_at >= start_date)
            if end_date:
                query = query.where(ParallelUsageLog.created_at <= end_date)

            result = await db.execute(query)
            row = result.one()

            total_requests = row.total_requests or 0
            successful_requests = row.successful_requests or 0
            failed_requests = total_requests - successful_requests
            success_rate = (
                round((successful_requests / total_requests) * 100, 2)
                if total_requests > 0
                else 0.0
            )

            return {
                "total_requests": total_requests,
                "successful_requests": successful_requests,
                "failed_requests": failed_requests,
                "success_rate": success_rate,
                "total_cost_usd": float(row.total_cost or Decimal("0")),
                "avg_latency_ms": int(row.avg_latency_ms) if row.avg_latency_ms else 0,
                "total_content_mb": round((row.total_content_bytes or 0) / (1024 * 1024), 2),
            }

        except Exception as e:
            logger.error(f"Failed to get usage stats: {e}", exc_info=True)
            return {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "success_rate": 0.0,
                "total_cost_usd": 0.0,
                "avg_latency_ms": 0,
                "total_content_mb": 0.0,
            }

    @staticmethod
    async def get_usage_by_project(
        db: AsyncSession,
        organization_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[dict]:
        """Get usage breakdown by project.

        Args:
            db: Database session.
            organization_id: Filter by organization.
            start_date: Start of date range.
            end_date: End of date range.

        Returns:
            list[dict]: Project usage statistics.
        """
        try:
            query = (
                select(
                    ParallelUsageLog.project_id,
                    Project.name.label("project_name"),
                    Project.organization_id.label("org_id"),
                    func.count(ParallelUsageLog.id).label("request_count"),
                    func.sum(cast(ParallelUsageLog.success, Integer)).label("successful_requests"),
                    func.sum(ParallelUsageLog.cost).label("total_cost"),
                    func.sum(ParallelUsageLog.content_size_bytes).label("total_content_bytes"),
                )
                .join(Project, ParallelUsageLog.project_id == Project.id, isouter=True)
                .where(ParallelUsageLog.project_id.isnot(None))
            )

            if organization_id:
                query = query.where(Project.organization_id == organization_id)
            if start_date:
                query = query.where(ParallelUsageLog.created_at >= start_date)
            if end_date:
                query = query.where(ParallelUsageLog.created_at <= end_date)

            query = query.group_by(
                ParallelUsageLog.project_id, Project.name, Project.organization_id
            ).order_by(func.count(ParallelUsageLog.id).desc())

            result = await db.execute(query)
            rows = result.all()

            return [
                {
                    "project_id": str(row.project_id),
                    "project_name": row.project_name or "Unknown Project",
                    "organization_id": str(row.org_id) if row.org_id else None,
                    "request_count": row.request_count,
                    "successful_requests": row.successful_requests or 0,
                    "failed_requests": row.request_count - (row.successful_requests or 0),
                    "total_cost_usd": float(row.total_cost or Decimal("0")),
                    "total_content_mb": round((row.total_content_bytes or 0) / (1024 * 1024), 2),
                }
                for row in rows
            ]

        except Exception as e:
            logger.error(f"Failed to get usage by project: {e}", exc_info=True)
            return []

    @staticmethod
    async def get_usage_by_user_detailed(
        db: AsyncSession,
        organization_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 20,
    ) -> list[dict]:
        """Get detailed usage breakdown by user.

        Args:
            db: Database session.
            organization_id: Filter by organization.
            start_date: Start of date range.
            end_date: End of date range.
            limit: Maximum number of users to return.

        Returns:
            list[dict]: User usage statistics with organization details.
        """
        try:
            query = (
                select(
                    ParallelUsageLog.user_id,
                    User.first_name.label("user_first_name"),
                    User.last_name.label("user_last_name"),
                    User.email.label("user_email"),
                    ParallelUsageLog.organization_id,
                    Organization.name.label("organization_name"),
                    func.count(ParallelUsageLog.id).label("request_count"),
                    func.sum(cast(ParallelUsageLog.success, Integer)).label("successful_requests"),
                    func.sum(ParallelUsageLog.cost).label("total_cost"),
                    func.avg(ParallelUsageLog.latency_ms).label("avg_latency_ms"),
                    func.sum(ParallelUsageLog.content_size_bytes).label("total_content_bytes"),
                    func.max(ParallelUsageLog.created_at).label("last_request_at"),
                )
                .join(User, ParallelUsageLog.user_id == User.id, isouter=True)
                .join(
                    Organization, ParallelUsageLog.organization_id == Organization.id, isouter=True
                )
                .where(ParallelUsageLog.user_id.isnot(None))
            )

            if organization_id:
                query = query.where(ParallelUsageLog.organization_id == organization_id)
            if start_date:
                query = query.where(ParallelUsageLog.created_at >= start_date)
            if end_date:
                query = query.where(ParallelUsageLog.created_at <= end_date)

            query = (
                query.group_by(
                    ParallelUsageLog.user_id,
                    User.first_name,
                    User.last_name,
                    User.email,
                    ParallelUsageLog.organization_id,
                    Organization.name,
                )
                .order_by(func.count(ParallelUsageLog.id).desc())
                .limit(limit)
            )

            result = await db.execute(query)
            rows = result.all()

            return [
                {
                    "user_id": str(row.user_id),
                    "user_name": f"{row.user_first_name or ''} {row.user_last_name or ''}".strip()
                    or "Unknown User",
                    "user_email": row.user_email or "unknown@example.com",
                    "organization_id": str(row.organization_id) if row.organization_id else None,
                    "organization_name": row.organization_name or "No Organization",
                    "request_count": row.request_count,
                    "successful_requests": row.successful_requests or 0,
                    "failed_requests": row.request_count - (row.successful_requests or 0),
                    "total_cost_usd": float(row.total_cost or Decimal("0")),
                    "avg_latency_ms": int(row.avg_latency_ms) if row.avg_latency_ms else 0,
                    "total_content_mb": round((row.total_content_bytes or 0) / (1024 * 1024), 2),
                    "last_request_at": row.last_request_at.isoformat()
                    if row.last_request_at
                    else None,
                }
                for row in rows
            ]

        except Exception as e:
            logger.error(f"Failed to get usage by user: {e}", exc_info=True)
            return []

    @staticmethod
    async def get_usage_by_organization_detailed(
        db: AsyncSession,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[dict]:
        """Get detailed usage breakdown by organization.

        Args:
            db: Database session.
            start_date: Start of date range.
            end_date: End of date range.

        Returns:
            list[dict]: Organization usage statistics with user counts.
        """
        try:
            query = (
                select(
                    ParallelUsageLog.organization_id,
                    Organization.name.label("organization_name"),
                    Organization.plan,
                    func.count(func.distinct(ParallelUsageLog.user_id)).label("unique_users"),
                    func.count(ParallelUsageLog.id).label("request_count"),
                    func.sum(cast(ParallelUsageLog.success, Integer)).label("successful_requests"),
                    func.sum(ParallelUsageLog.cost).label("total_cost"),
                    func.sum(ParallelUsageLog.content_size_bytes).label("total_content_bytes"),
                    func.max(ParallelUsageLog.created_at).label("last_request_at"),
                )
                .join(
                    Organization, ParallelUsageLog.organization_id == Organization.id, isouter=True
                )
                .where(ParallelUsageLog.organization_id.isnot(None))
            )

            if start_date:
                query = query.where(ParallelUsageLog.created_at >= start_date)
            if end_date:
                query = query.where(ParallelUsageLog.created_at <= end_date)

            query = query.group_by(
                ParallelUsageLog.organization_id,
                Organization.name,
                Organization.plan,
            ).order_by(func.count(ParallelUsageLog.id).desc())

            result = await db.execute(query)
            rows = result.all()

            return [
                {
                    "organization_id": str(row.organization_id),
                    "organization_name": row.organization_name or "Unknown Organization",
                    "plan": row.plan or "trialing",
                    "unique_users": row.unique_users,
                    "request_count": row.request_count,
                    "successful_requests": row.successful_requests or 0,
                    "failed_requests": row.request_count - (row.successful_requests or 0),
                    "total_cost_usd": float(row.total_cost or Decimal("0")),
                    "total_content_mb": round((row.total_content_bytes or 0) / (1024 * 1024), 2),
                    "last_request_at": row.last_request_at.isoformat()
                    if row.last_request_at
                    else None,
                }
                for row in rows
            ]

        except Exception as e:
            logger.error(f"Failed to get usage by organization: {e}", exc_info=True)
            return []

    @staticmethod
    async def get_detailed_logs(
        db: AsyncSession,
        user_id: Optional[UUID] = None,
        organization_id: Optional[UUID] = None,
        project_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """Get detailed request logs with full attribution.

        Args:
            db: Database session.
            user_id: Filter by user.
            organization_id: Filter by organization.
            project_id: Filter by project.
            start_date: Start of date range.
            end_date: End of date range.
            limit: Maximum logs to return.
            offset: Pagination offset.

        Returns:
            dict: Paginated logs with total count.
        """
        try:
            # Build query for logs
            query = (
                select(
                    ParallelUsageLog,
                    User.first_name.label("user_first_name"),
                    User.last_name.label("user_last_name"),
                    User.email.label("user_email"),
                    Organization.name.label("organization_name"),
                    Project.name.label("project_name"),
                )
                .join(User, ParallelUsageLog.user_id == User.id, isouter=True)
                .join(
                    Organization, ParallelUsageLog.organization_id == Organization.id, isouter=True
                )
                .join(Project, ParallelUsageLog.project_id == Project.id, isouter=True)
            )

            # Apply filters
            if user_id:
                query = query.where(ParallelUsageLog.user_id == user_id)
            if organization_id:
                query = query.where(ParallelUsageLog.organization_id == organization_id)
            if project_id:
                query = query.where(ParallelUsageLog.project_id == project_id)
            if start_date:
                query = query.where(ParallelUsageLog.created_at >= start_date)
            if end_date:
                query = query.where(ParallelUsageLog.created_at <= end_date)

            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await db.execute(count_query)
            total_count = total_result.scalar() or 0

            # Get paginated results
            query = query.order_by(ParallelUsageLog.created_at.desc()).limit(limit).offset(offset)
            result = await db.execute(query)
            rows = result.all()

            logs = [
                {
                    "id": str(row.ParallelUsageLog.id),
                    "url_extracted": row.ParallelUsageLog.url_extracted,
                    "endpoint_name": row.ParallelUsageLog.endpoint_name,
                    "user": {
                        "id": str(row.ParallelUsageLog.user_id)
                        if row.ParallelUsageLog.user_id
                        else None,
                        "name": f"{row.user_first_name or ''} {row.user_last_name or ''}".strip()
                        or "Unknown",
                        "email": row.user_email or "unknown@example.com",
                    },
                    "organization": {
                        "id": str(row.ParallelUsageLog.organization_id)
                        if row.ParallelUsageLog.organization_id
                        else None,
                        "name": row.organization_name or "No Organization",
                    },
                    "project": {
                        "id": str(row.ParallelUsageLog.project_id)
                        if row.ParallelUsageLog.project_id
                        else None,
                        "name": row.project_name or "No Project",
                    },
                    "success": row.ParallelUsageLog.success,
                    "cost_usd": float(row.ParallelUsageLog.cost),
                    "latency_ms": row.ParallelUsageLog.latency_ms,
                    "content_size_bytes": row.ParallelUsageLog.content_size_bytes,
                    "error_message": row.ParallelUsageLog.error_message,
                    "created_at": row.ParallelUsageLog.created_at.isoformat(),
                }
                for row in rows
            ]

            return {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "logs": logs,
            }

        except Exception as e:
            logger.error(f"Failed to get detailed logs: {e}", exc_info=True)
            return {
                "total": 0,
                "limit": limit,
                "offset": offset,
                "logs": [],
            }

    @staticmethod
    async def get_usage_by_endpoint(
        db: AsyncSession,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[dict]:
        """Get usage breakdown by endpoint.

        Args:
            db: Database session.
            start_date: Start of date range.
            end_date: End of date range.

        Returns:
            list[dict]: Endpoint usage statistics.
        """
        try:
            query = select(
                ParallelUsageLog.endpoint_name,
                func.count(ParallelUsageLog.id).label("request_count"),
                func.sum(cast(ParallelUsageLog.success, Integer)).label("successful_requests"),
                func.sum(ParallelUsageLog.cost).label("total_cost"),
                func.avg(ParallelUsageLog.latency_ms).label("avg_latency_ms"),
            )

            if start_date:
                query = query.where(ParallelUsageLog.created_at >= start_date)
            if end_date:
                query = query.where(ParallelUsageLog.created_at <= end_date)

            query = query.group_by(ParallelUsageLog.endpoint_name).order_by(
                func.count(ParallelUsageLog.id).desc()
            )

            result = await db.execute(query)
            rows = result.all()

            return [
                {
                    "endpoint_name": row.endpoint_name,
                    "request_count": row.request_count,
                    "successful_requests": row.successful_requests or 0,
                    "failed_requests": row.request_count - (row.successful_requests or 0),
                    "total_cost_usd": float(row.total_cost or Decimal("0")),
                    "avg_latency_ms": int(row.avg_latency_ms) if row.avg_latency_ms else 0,
                }
                for row in rows
            ]

        except Exception as e:
            logger.error(f"Failed to get usage by endpoint: {e}", exc_info=True)
            return []

    @staticmethod
    async def get_daily_cost_breakdown(
        db: AsyncSession,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[dict]:
        """Get daily cost breakdown for trend analysis.

        Args:
            db: Database session.
            start_date: Start of date range.
            end_date: End of date range.

        Returns:
            list[dict]: Daily cost statistics.
        """
        try:
            query = select(
                func.date(ParallelUsageLog.created_at).label("date"),
                func.count(ParallelUsageLog.id).label("request_count"),
                func.sum(cast(ParallelUsageLog.success, Integer)).label("successful_requests"),
                func.sum(ParallelUsageLog.cost).label("total_cost"),
            )

            if start_date:
                query = query.where(ParallelUsageLog.created_at >= start_date)
            if end_date:
                query = query.where(ParallelUsageLog.created_at <= end_date)

            query = query.group_by(func.date(ParallelUsageLog.created_at)).order_by(
                func.date(ParallelUsageLog.created_at).desc()
            )

            result = await db.execute(query)
            rows = result.all()

            return [
                {
                    "date": str(row.date),
                    "request_count": row.request_count,
                    "successful_requests": row.successful_requests or 0,
                    "failed_requests": row.request_count - (row.successful_requests or 0),
                    "total_cost_usd": float(row.total_cost or Decimal("0")),
                }
                for row in rows
            ]

        except Exception as e:
            logger.error(f"Failed to get daily cost breakdown: {e}", exc_info=True)
            return []

    @staticmethod
    async def get_recent_errors(
        db: AsyncSession,
        limit: int = 50,
    ) -> list[dict]:
        """Get recent extraction errors for troubleshooting.

        Args:
            db: Database session.
            limit: Number of errors to return.

        Returns:
            list[dict]: Recent error logs.
        """
        try:
            query = (
                select(ParallelUsageLog)
                .where(not_(ParallelUsageLog.success))
                .order_by(ParallelUsageLog.created_at.desc())
                .limit(limit)
            )

            result = await db.execute(query)
            error_logs = result.scalars().all()

            return [
                {
                    "id": str(log.id),
                    "user_id": str(log.user_id) if log.user_id else None,
                    "url_extracted": log.url_extracted,
                    "endpoint_name": log.endpoint_name,
                    "error_message": log.error_message,
                    "latency_ms": log.latency_ms,
                    "created_at": log.created_at.isoformat(),
                }
                for log in error_logs
            ]

        except Exception as e:
            logger.error(f"Failed to get recent errors: {e}", exc_info=True)
            return []
