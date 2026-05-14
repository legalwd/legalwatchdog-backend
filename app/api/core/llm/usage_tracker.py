"""LLM usage tracking service for admin dashboard monitoring."""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Integer, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.api.core.llm.base_provider import LLMUsageMetrics
from app.api.db.models.llm_usage import LLMProviderStatus, LLMUsageLog

logger = logging.getLogger(__name__)


class LLMUsageTracker:
    """Tracks and persists LLM usage metrics for admin dashboard.

    Provides comprehensive usage tracking, cost monitoring, and provider
    health status updates for billing, analytics, and operational monitoring.

    Examples:
        >>> tracker = LLMUsageTracker()
        >>> await tracker.log_usage(db, usage_metrics, endpoint="/api/v1/scrape")
    """

    @staticmethod
    async def log_usage(
        db: AsyncSession,
        metrics: LLMUsageMetrics,
        endpoint: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> LLMUsageLog:
        """Log LLM usage metrics to database.

        Args:
            db (AsyncSession): Database session.
            metrics (LLMUsageMetrics): Usage metrics to log.
            endpoint (Optional[str]): API endpoint that triggered request.
            ip_address (Optional[str]): Client IP address.

        Returns:
            LLMUsageLog: Persisted usage log entry.

        Examples:
            >>> log = await tracker.log_usage(
            ...     db=db,
            ...     metrics=usage_metrics,
            ...     endpoint="/api/v1/sources/extract"
            ... )
            >>> print(f"Logged ${log.cost_usd:.4f} usage")
        """
        try:
            log_entry = LLMUsageLog(
                request_id=metrics.request_id or "unknown",
                model=metrics.model,
                provider=metrics.provider,
                user_id=UUID(metrics.user_id) if metrics.user_id else None,
                organization_id=UUID(metrics.organization_id) if metrics.organization_id else None,
                project_id=UUID(metrics.project_id) if metrics.project_id else None,
                jurisdiction_id=UUID(metrics.jurisdiction_id) if metrics.jurisdiction_id else None,
                input_tokens=metrics.input_tokens,
                output_tokens=metrics.output_tokens,
                total_tokens=metrics.total_tokens,
                cost_usd=metrics.cost_usd,
                latency_ms=metrics.latency_ms,
                success=metrics.success,
                error_message=metrics.error_message,
                retry_count=metrics.retry_count,
                endpoint=endpoint,
                ip_address=ip_address,
            )

            db.add(log_entry)
            await db.commit()
            await db.refresh(log_entry)

            logger.info(
                f"Logged LLM usage: model={metrics.model}, "
                f"tokens={metrics.total_tokens}, cost=${metrics.cost_usd:.6f}, "
                f"success={metrics.success}"
            )

            return log_entry
        except Exception as e:
            logger.error(f"Failed to log LLM usage: {e}", exc_info=True)
            await db.rollback()
            raise

    @staticmethod
    def log_usage_sync(
        db: Session,
        metrics: LLMUsageMetrics,
        endpoint: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> LLMUsageLog:
        """Log LLM usage metrics to database (sync version for Celery).

        Args:
            db (Session): Sync database session.
            metrics (LLMUsageMetrics): Usage metrics to log.
            endpoint (Optional[str]): API endpoint that triggered request.
            ip_address (Optional[str]): Client IP address.

        Returns:
            LLMUsageLog: Persisted usage log entry.

        Examples:
            >>> log = tracker.log_usage_sync(
            ...     db=sync_db,
            ...     metrics=usage_metrics,
            ...     endpoint="/celery/scraping/stage4"
            ... )
            >>> print(f"Logged ${log.cost_usd:.4f} usage")
        """
        try:
            log_entry = LLMUsageLog(
                request_id=metrics.request_id or "unknown",
                model=metrics.model,
                provider=metrics.provider,
                user_id=UUID(metrics.user_id) if metrics.user_id else None,
                organization_id=UUID(metrics.organization_id) if metrics.organization_id else None,
                project_id=UUID(metrics.project_id) if metrics.project_id else None,
                jurisdiction_id=UUID(metrics.jurisdiction_id) if metrics.jurisdiction_id else None,
                input_tokens=metrics.input_tokens,
                output_tokens=metrics.output_tokens,
                total_tokens=metrics.total_tokens,
                cost_usd=metrics.cost_usd,
                latency_ms=metrics.latency_ms,
                success=metrics.success,
                error_message=metrics.error_message,
                retry_count=metrics.retry_count,
                endpoint=endpoint,
                ip_address=ip_address,
            )

            db.add(log_entry)
            db.commit()
            db.refresh(log_entry)

            logger.info(
                f"Logged LLM usage (sync): model={metrics.model}, "
                f"tokens={metrics.total_tokens}, cost=${metrics.cost_usd:.6f}, "
                f"success={metrics.success}"
            )

            return log_entry
        except Exception as e:
            logger.error(f"Failed to log LLM usage (sync): {e}", exc_info=True)
            db.rollback()
            raise

    @staticmethod
    async def update_provider_status(
        db: AsyncSession,
        provider: str,
        model: Optional[str],
        success: bool,
        latency_ms: float,
        error_message: Optional[str] = None,
    ) -> LLMProviderStatus:
        """Update provider health status based on request outcome.

        Args:
            db (AsyncSession): Database session.
            provider (str): Provider identifier.
            model (Optional[str]): Model identifier.
            success (bool): Whether request succeeded.
            latency_ms (float): Request latency in milliseconds.
            error_message (Optional[str]): Error message if failed.

        Returns:
            LLMProviderStatus: Updated provider status.

        Examples:
            >>> status = await tracker.update_provider_status(
            ...     db=db,
            ...     provider="openrouter",
            ...     model="anthropic/claude-3.5-sonnet",
            ...     success=True,
            ...     latency_ms=1234.5
            ... )
        """
        try:
            stmt = select(LLMProviderStatus).where(
                LLMProviderStatus.provider == provider,
                LLMProviderStatus.model == model,
            )
            result = await db.execute(stmt)
            status = result.scalar_one_or_none()

            if not status:
                status = LLMProviderStatus(
                    provider=provider,
                    model=model,
                    is_available=True,
                    error_rate=0.0,
                    avg_latency_ms=0.0,
                    requests_last_hour=0,
                )
                db.add(status)

            alpha = 0.2
            status.avg_latency_ms = alpha * latency_ms + (1 - alpha) * status.avg_latency_ms

            if success:
                status.error_rate = (1 - alpha) * status.error_rate
                status.last_success_at = datetime.utcnow()
                status.is_available = True
            else:
                status.error_rate = alpha + (1 - alpha) * status.error_rate
                status.last_error = error_message
                status.last_error_at = datetime.utcnow()
                if status.error_rate > 0.5:
                    status.is_available = False

            status.requests_last_hour += 1

            await db.commit()
            await db.refresh(status)

            return status
        except Exception as e:
            logger.error(f"Failed to update provider status: {e}", exc_info=True)
            await db.rollback()
            raise

    @staticmethod
    async def get_usage_stats(
        db: AsyncSession,
        user_id: Optional[UUID] = None,
        organization_id: Optional[UUID] = None,
        organization_ids: Optional[list[UUID]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> dict:
        """Get aggregated usage statistics for admin dashboard.

        Args:
            db (AsyncSession): Database session.
            user_id (Optional[UUID]): Filter by user ID.
            organization_id (Optional[UUID]): Filter by organization ID.
            organization_ids (Optional[list[UUID]]): Filter by multiple organization IDs.
            start_date (Optional[datetime]): Start date filter.
            end_date (Optional[datetime]): End date filter.

        Returns:
            dict: Aggregated usage statistics.

        Examples:
            >>> stats = await tracker.get_usage_stats(
            ...     db=db,
            ...     organization_id=org_id,
            ...     start_date=datetime.now() - timedelta(days=30)
            ... )
            >>> print(f"Total cost: ${stats['total_cost_usd']:.2f}")
        """
        try:
            query = select(
                func.count(LLMUsageLog.id).label("total_requests"),
                func.sum(LLMUsageLog.total_tokens).label("total_tokens"),
                func.sum(LLMUsageLog.input_tokens).label("total_input_tokens"),
                func.sum(LLMUsageLog.output_tokens).label("total_output_tokens"),
                func.sum(LLMUsageLog.cost_usd).label("total_cost_usd"),
                func.avg(LLMUsageLog.latency_ms).label("avg_latency_ms"),
                func.sum(cast(~LLMUsageLog.success, Integer)).label("failed_requests"),
            )

            conditions = []
            if user_id:
                conditions.append(LLMUsageLog.user_id == user_id)
            if organization_id:
                conditions.append(LLMUsageLog.organization_id == organization_id)
            if organization_ids:
                conditions.append(LLMUsageLog.organization_id.in_(organization_ids))

            if conditions:
                query = query.where(or_(*conditions))

            if start_date:
                query = query.where(LLMUsageLog.created_at >= start_date)
            if end_date:
                query = query.where(LLMUsageLog.created_at <= end_date)

            result = await db.execute(query)
            row = result.one()

            return {
                "total_requests": row.total_requests or 0,
                "total_tokens": row.total_tokens or 0,
                "total_input_tokens": row.total_input_tokens or 0,
                "total_output_tokens": row.total_output_tokens or 0,
                "total_cost_usd": float(row.total_cost_usd or 0.0),
                "avg_latency_ms": float(row.avg_latency_ms or 0.0),
                "failed_requests": row.failed_requests or 0,
                "success_rate": (
                    1.0 - (row.failed_requests or 0) / max(row.total_requests or 1, 1)
                ),
            }
        except Exception as e:
            logger.error(f"Failed to get usage stats: {e}", exc_info=True)
            return {
                "total_requests": 0,
                "total_tokens": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cost_usd": 0.0,
                "avg_latency_ms": 0,
                "failed_requests": 0,
                "success_rate": 0.0,
            }

    @staticmethod
    async def get_usage_by_model(
        db: AsyncSession,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[dict]:
        """Get usage breakdown by model for cost analysis.

        Args:
            db (AsyncSession): Database session.
            start_date (Optional[datetime]): Start date filter.
            end_date (Optional[datetime]): End date filter.

        Returns:
            list[dict]: List of model usage statistics.

        Examples:
            >>> models = await tracker.get_usage_by_model(
            ...     db=db,
            ...     start_date=datetime.now() - timedelta(days=7)
            ... )
            >>> for model in models:
            ...     print(f"{model['model']}: ${model['total_cost_usd']:.2f}")
        """
        try:
            query = (
                select(
                    LLMUsageLog.model,
                    LLMUsageLog.provider,
                    func.count(LLMUsageLog.id).label("request_count"),
                    func.sum(LLMUsageLog.total_tokens).label("total_tokens"),
                    func.sum(LLMUsageLog.cost_usd).label("total_cost_usd"),
                    func.avg(LLMUsageLog.latency_ms).label("avg_latency_ms"),
                )
                .group_by(LLMUsageLog.model, LLMUsageLog.provider)
                .order_by(func.sum(LLMUsageLog.cost_usd).desc())
            )

            if start_date:
                query = query.where(LLMUsageLog.created_at >= start_date)
            if end_date:
                query = query.where(LLMUsageLog.created_at <= end_date)

            result = await db.execute(query)
            rows = result.all()

            return [
                {
                    "model": row.model,
                    "provider": row.provider,
                    "request_count": row.request_count,
                    "total_tokens": row.total_tokens,
                    "total_cost_usd": float(row.total_cost_usd),
                    "avg_latency_ms": float(row.avg_latency_ms),
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to get usage by model: {e}", exc_info=True)
            return []

    @staticmethod
    async def get_usage_by_provider(
        db: AsyncSession,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        organization_id: Optional[UUID] = None,
    ) -> list[dict]:
        """Get usage breakdown by provider for cost analysis.

        Args:
            db (AsyncSession): Database session.
            start_date (Optional[datetime]): Start date filter.
            end_date (Optional[datetime]): End date filter.
            organization_id (Optional[UUID]): Filter by organization ID.

        Returns:
            list[dict]: List of provider usage statistics.

        Examples:
            >>> providers = await tracker.get_usage_by_provider(
            ...     db=db,
            ...     start_date=datetime.now() - timedelta(days=7)
            ... )
            >>> for provider in providers:
            ...     print(f"{provider['provider']}: ${provider['total_cost_usd']:.2f}")
        """
        try:
            query = (
                select(
                    LLMUsageLog.provider,
                    func.count(LLMUsageLog.id).label("request_count"),
                    func.sum(LLMUsageLog.total_tokens).label("total_tokens"),
                    func.sum(LLMUsageLog.input_tokens).label("total_input_tokens"),
                    func.sum(LLMUsageLog.output_tokens).label("total_output_tokens"),
                    func.sum(LLMUsageLog.cost_usd).label("total_cost_usd"),
                    func.avg(LLMUsageLog.latency_ms).label("avg_latency_ms"),
                    func.sum(cast(~LLMUsageLog.success, Integer)).label("failed_requests"),
                )
                .group_by(LLMUsageLog.provider)
                .order_by(func.sum(LLMUsageLog.cost_usd).desc())
            )

            if organization_id:
                query = query.where(LLMUsageLog.organization_id == organization_id)
            if start_date:
                query = query.where(LLMUsageLog.created_at >= start_date)
            if end_date:
                query = query.where(LLMUsageLog.created_at <= end_date)

            result = await db.execute(query)
            rows = result.all()

            return [
                {
                    "provider": row.provider,
                    "request_count": row.request_count or 0,
                    "total_tokens": row.total_tokens or 0,
                    "total_input_tokens": row.total_input_tokens or 0,
                    "total_output_tokens": row.total_output_tokens or 0,
                    "total_cost_usd": float(row.total_cost_usd or 0.0),
                    "avg_latency_ms": float(row.avg_latency_ms or 0.0),
                    "failed_requests": row.failed_requests or 0,
                    "success_rate": (
                        1.0 - (row.failed_requests or 0) / max(row.request_count or 1, 1)
                    ),
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to get usage by provider: {e}", exc_info=True)
            return []

    @staticmethod
    async def get_provider_health(db: AsyncSession) -> list[dict]:
        """Get current health status of all providers.

        Args:
            db (AsyncSession): Database session.

        Returns:
            list[dict]: List of provider health statuses.

        Examples:
            >>> health = await tracker.get_provider_health(db)
            >>> for provider in health:
            ...     print(f"{provider['provider']}: {provider['is_available']}")
        """
        try:
            stmt = select(LLMProviderStatus).order_by(LLMProviderStatus.provider)
            result = await db.execute(stmt)
            statuses = result.scalars().all()

            return [
                {
                    "provider": status.provider,
                    "model": status.model,
                    "is_available": status.is_available,
                    "error_rate": status.error_rate,
                    "avg_latency_ms": status.avg_latency_ms,
                    "requests_last_hour": status.requests_last_hour,
                    "last_success_at": status.last_success_at.isoformat()
                    if status.last_success_at
                    else None,
                    "last_error_at": status.last_error_at.isoformat()
                    if status.last_error_at
                    else None,
                    "last_error": status.last_error,
                }
                for status in statuses
            ]
        except Exception as e:
            logger.error(f"Failed to get provider health: {e}", exc_info=True)
            return []

    @staticmethod
    async def get_usage_by_endpoint(
        db: AsyncSession,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        organization_id: Optional[UUID] = None,
    ) -> list[dict]:
        """Get usage breakdown by API endpoint.

        Args:
            db (AsyncSession): Database session.
            start_date (Optional[datetime]): Start date filter.
            end_date (Optional[datetime]): End date filter.
            organization_id (Optional[UUID]): Filter by organization ID.

        Returns:
            list[dict]: List of endpoint usage statistics.

        Examples:
            >>> endpoints = await tracker.get_usage_by_endpoint(
            ...     db=db,
            ...     start_date=datetime.now() - timedelta(days=7)
            ... )
            >>> for endpoint in endpoints:
            ...     print(f"{endpoint['endpoint']}: {endpoint['request_count']} requests")
        """
        try:
            query = (
                select(
                    LLMUsageLog.endpoint,
                    func.count(LLMUsageLog.id).label("request_count"),
                    func.sum(LLMUsageLog.total_tokens).label("total_tokens"),
                    func.sum(LLMUsageLog.cost_usd).label("total_cost_usd"),
                    func.avg(LLMUsageLog.latency_ms).label("avg_latency_ms"),
                    func.sum(cast(~LLMUsageLog.success, Integer)).label("failed_requests"),
                )
                .where(LLMUsageLog.endpoint.isnot(None))
                .group_by(LLMUsageLog.endpoint)
                .order_by(func.sum(LLMUsageLog.cost_usd).desc())
            )

            if organization_id:
                query = query.where(LLMUsageLog.organization_id == organization_id)
            if start_date:
                query = query.where(LLMUsageLog.created_at >= start_date)
            if end_date:
                query = query.where(LLMUsageLog.created_at <= end_date)

            result = await db.execute(query)
            rows = result.all()

            return [
                {
                    "endpoint": row.endpoint,
                    "request_count": row.request_count or 0,
                    "total_tokens": row.total_tokens or 0,
                    "total_cost_usd": float(row.total_cost_usd or 0.0),
                    "avg_latency_ms": float(row.avg_latency_ms or 0.0),
                    "failed_requests": row.failed_requests or 0,
                    "success_rate": (
                        1.0 - (row.failed_requests or 0) / max(row.request_count or 1, 1)
                    ),
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to get usage by endpoint: {e}", exc_info=True)
            return []

    @staticmethod
    async def get_usage_trends(
        db: AsyncSession,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        granularity: str = "day",
    ) -> list[dict]:
        """Get usage trends over time with configurable granularity.

        Args:
            db (AsyncSession): Database session.
            start_date (Optional[datetime]): Start date filter.
            end_date (Optional[datetime]): End date filter.
            granularity (str): Aggregation granularity (hour, day, week, month).

        Returns:
            list[dict]: List of time-series usage data.

        Examples:
            >>> trends = await tracker.get_usage_trends(
            ...     db=db,
            ...     start_date=datetime.now() - timedelta(days=7),
            ...     granularity="day"
            ... )
        """
        try:
            if granularity == "hour":
                trunc_func = func.date_trunc("hour", LLMUsageLog.created_at)
            elif granularity == "week":
                trunc_func = func.date_trunc("week", LLMUsageLog.created_at)
            elif granularity == "month":
                trunc_func = func.date_trunc("month", LLMUsageLog.created_at)
            else:
                trunc_func = func.date_trunc("day", LLMUsageLog.created_at)

            query = (
                select(
                    trunc_func.label("time_bucket"),
                    func.count(LLMUsageLog.id).label("request_count"),
                    func.sum(LLMUsageLog.total_tokens).label("total_tokens"),
                    func.sum(LLMUsageLog.cost_usd).label("total_cost_usd"),
                    func.avg(LLMUsageLog.latency_ms).label("avg_latency_ms"),
                    func.sum(cast(~LLMUsageLog.success, Integer)).label("failed_requests"),
                )
                .group_by(trunc_func)
                .order_by(trunc_func)
            )

            if start_date:
                query = query.where(LLMUsageLog.created_at >= start_date)
            if end_date:
                query = query.where(LLMUsageLog.created_at <= end_date)

            result = await db.execute(query)
            rows = result.all()

            return [
                {
                    "time": row.time_bucket.isoformat() if row.time_bucket else None,
                    "request_count": row.request_count or 0,
                    "total_tokens": row.total_tokens or 0,
                    "total_cost_usd": float(row.total_cost_usd or 0.0),
                    "avg_latency_ms": float(row.avg_latency_ms or 0.0),
                    "failed_requests": row.failed_requests or 0,
                    "success_rate": (
                        1.0 - (row.failed_requests or 0) / max(row.request_count or 1, 1)
                    ),
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to get usage trends: {e}", exc_info=True)
            return []

    @staticmethod
    async def get_cost_breakdown(
        db: AsyncSession,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        group_by: str = "provider",
        organization_id: Optional[UUID] = None,
    ) -> dict:
        """Get detailed cost breakdown grouped by dimension.

        Args:
            db (AsyncSession): Database session.
            start_date (Optional[datetime]): Start date filter.
            end_date (Optional[datetime]): End date filter.
            group_by (str): Grouping dimension (provider, model, endpoint, user, organization).
            organization_id (Optional[UUID]): Filter by organization ID.

        Returns:
            dict: Cost breakdown data.

        Examples:
            >>> breakdown = await tracker.get_cost_breakdown(
            ...     db=db,
            ...     group_by="model",
            ...     start_date=datetime.now() - timedelta(days=30)
            ... )
        """
        try:
            if group_by == "model":
                group_col = LLMUsageLog.model
            elif group_by == "endpoint":
                group_col = LLMUsageLog.endpoint
            elif group_by == "user":
                group_col = LLMUsageLog.user_id
            elif group_by == "organization":
                group_col = LLMUsageLog.organization_id
            else:
                group_col = LLMUsageLog.provider

            query = (
                select(
                    group_col.label("dimension"),
                    func.count(LLMUsageLog.id).label("request_count"),
                    func.sum(LLMUsageLog.input_tokens).label("input_tokens"),
                    func.sum(LLMUsageLog.output_tokens).label("output_tokens"),
                    func.sum(LLMUsageLog.total_tokens).label("total_tokens"),
                    func.sum(LLMUsageLog.cost_usd).label("total_cost_usd"),
                    func.avg(LLMUsageLog.cost_usd).label("avg_cost_per_request"),
                )
                .group_by(group_col)
                .order_by(func.sum(LLMUsageLog.cost_usd).desc())
            )

            if organization_id:
                query = query.where(LLMUsageLog.organization_id == organization_id)
            if start_date:
                query = query.where(LLMUsageLog.created_at >= start_date)
            if end_date:
                query = query.where(LLMUsageLog.created_at <= end_date)

            result = await db.execute(query)
            rows = result.all()

            breakdown_list = [
                {
                    "dimension": str(row.dimension) if row.dimension else "unknown",
                    "request_count": row.request_count or 0,
                    "input_tokens": row.input_tokens or 0,
                    "output_tokens": row.output_tokens or 0,
                    "total_tokens": row.total_tokens or 0,
                    "total_cost_usd": float(row.total_cost_usd or 0.0),
                    "avg_cost_per_request": float(row.avg_cost_per_request or 0.0),
                }
                for row in rows
            ]

            total_cost = sum(item["total_cost_usd"] for item in breakdown_list)

            return {
                "group_by": group_by,
                "total_cost_usd": total_cost,
                "breakdown": breakdown_list,
            }
        except Exception as e:
            logger.error(f"Failed to get cost breakdown: {e}", exc_info=True)
            return {"group_by": group_by, "total_cost_usd": 0.0, "breakdown": []}

    @staticmethod
    async def get_error_analysis(
        db: AsyncSession,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        organization_id: Optional[UUID] = None,
    ) -> dict:
        """Get error analysis and insights.

        Args:
            db (AsyncSession): Database session.
            start_date (Optional[datetime]): Start date filter.
            end_date (Optional[datetime]): End date filter.
            organization_id (Optional[UUID]): Filter by organization ID.

        Returns:
            dict: Error analysis data.

        Examples:
            >>> analysis = await tracker.get_error_analysis(
            ...     db=db,
            ...     start_date=datetime.now() - timedelta(days=7)
            ... )
        """
        try:
            query = select(LLMUsageLog).where(LLMUsageLog.success.is_(False))

            if organization_id:
                query = query.where(LLMUsageLog.organization_id == organization_id)
            if start_date:
                query = query.where(LLMUsageLog.created_at >= start_date)
            if end_date:
                query = query.where(LLMUsageLog.created_at <= end_date)

            result = await db.execute(query)
            error_logs = result.scalars().all()

            error_counts = {}
            for log in error_logs:
                error_msg = log.error_message or "Unknown error"
                error_counts[error_msg] = error_counts.get(error_msg, 0) + 1

            # Get overall stats
            stats_query = select(
                func.count(LLMUsageLog.id).label("total_requests"),
                func.sum(cast(~LLMUsageLog.success, Integer)).label("failed_requests"),
            )

            if organization_id:
                stats_query = stats_query.where(LLMUsageLog.organization_id == organization_id)
            if start_date:
                stats_query = stats_query.where(LLMUsageLog.created_at >= start_date)
            if end_date:
                stats_query = stats_query.where(LLMUsageLog.created_at <= end_date)

            stats_result = await db.execute(stats_query)
            stats_row = stats_result.one()

            total_requests = stats_row.total_requests or 0
            failed_requests = stats_row.failed_requests or 0
            error_rate = (failed_requests / max(total_requests, 1)) if total_requests > 0 else 0.0

            return {
                "total_requests": total_requests,
                "failed_requests": failed_requests,
                "error_rate": error_rate,
                "total_unique_errors": len(error_counts),
                "errors_by_message": [
                    {"message": msg, "count": count}
                    for msg, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True)
                ][:10],
            }
        except Exception as e:
            logger.error(f"Failed to get error analysis: {e}", exc_info=True)
            return {
                "total_requests": 0,
                "failed_requests": 0,
                "error_rate": 0.0,
                "total_unique_errors": 0,
                "errors_by_message": [],
            }

    # NEW METHODS FOR DETAILED TRACKING

    @staticmethod
    async def get_usage_by_project(
        db: AsyncSession,
        organization_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[dict]:
        """Get usage breakdown by project with project details.

        Args:
            db (AsyncSession): Database session.
            organization_id (Optional[UUID]): Filter by organization ID.
            start_date (Optional[datetime]): Start date filter.
            end_date (Optional[datetime]): End date filter.

        Returns:
            list[dict]: Project usage with name, org, total cost, tokens.

        Examples:
            >>> projects = await tracker.get_usage_by_project(db=db)
            >>> for project in projects:
            ...     print(f"{project['project_name']}: ${project['total_cost_usd']:.2f}")
        """
        try:
            from app.api.modules.v1.projects.models.project_model import Project

            query = (
                select(
                    LLMUsageLog.project_id,
                    Project.title.label("project_name"),
                    Project.org_id,
                    func.count(LLMUsageLog.id).label("request_count"),
                    func.sum(LLMUsageLog.total_tokens).label("total_tokens"),
                    func.sum(LLMUsageLog.cost_usd).label("total_cost_usd"),
                )
                .join(Project, LLMUsageLog.project_id == Project.id, isouter=True)
                .where(LLMUsageLog.project_id.isnot(None))
                .group_by(LLMUsageLog.project_id, Project.title, Project.org_id)
                .order_by(func.sum(LLMUsageLog.cost_usd).desc())
            )

            if organization_id:
                query = query.where(LLMUsageLog.organization_id == organization_id)
            if start_date:
                query = query.where(LLMUsageLog.created_at >= start_date)
            if end_date:
                query = query.where(LLMUsageLog.created_at <= end_date)

            result = await db.execute(query)
            rows = result.all()

            return [
                {
                    "project_id": str(row.project_id),
                    "project_name": row.project_name or "Unknown Project",
                    "organization_id": str(row.org_id) if row.org_id else None,
                    "request_count": row.request_count,
                    "total_tokens": row.total_tokens,
                    "total_cost_usd": float(row.total_cost_usd or 0.0),
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
    ) -> list[dict]:
        """Get usage by user with user details (name, email, org).

        Args:
            db (AsyncSession): Database session.
            organization_id (Optional[UUID]): Filter by organization ID.
            start_date (Optional[datetime]): Start date filter.
            end_date (Optional[datetime]): End date filter.

        Returns:
            list[dict]: User usage with name, email, org, cost, tokens.

        Examples:
            >>> users = await tracker.get_usage_by_user_detailed(db=db)
            >>> for user in users:
            ...     print(f"{user['user_name']}: ${user['total_cost_usd']:.2f}")
        """
        try:
            from app.api.modules.v1.organization.models.organization_model import Organization
            from app.api.modules.v1.users.models.users_model import User

            query = (
                select(
                    LLMUsageLog.user_id,
                    User.name.label("user_name"),
                    User.email.label("user_email"),
                    LLMUsageLog.organization_id,
                    Organization.name.label("organization_name"),
                    func.count(LLMUsageLog.id).label("request_count"),
                    func.sum(LLMUsageLog.total_tokens).label("total_tokens"),
                    func.sum(LLMUsageLog.input_tokens).label("input_tokens"),
                    func.sum(LLMUsageLog.output_tokens).label("output_tokens"),
                    func.sum(LLMUsageLog.cost_usd).label("total_cost_usd"),
                    func.max(LLMUsageLog.created_at).label("last_request_at"),
                )
                .join(User, LLMUsageLog.user_id == User.id, isouter=True)
                .join(Organization, LLMUsageLog.organization_id == Organization.id, isouter=True)
                .where(LLMUsageLog.user_id.isnot(None))
                .group_by(
                    LLMUsageLog.user_id,
                    User.name,
                    User.email,
                    LLMUsageLog.organization_id,
                    Organization.name,
                )
                .order_by(func.sum(LLMUsageLog.cost_usd).desc())
            )

            if organization_id:
                query = query.where(LLMUsageLog.organization_id == organization_id)
            if start_date:
                query = query.where(LLMUsageLog.created_at >= start_date)
            if end_date:
                query = query.where(LLMUsageLog.created_at <= end_date)

            result = await db.execute(query)
            rows = result.all()

            return [
                {
                    "user_id": str(row.user_id),
                    "user_name": row.user_name or "Unknown User",
                    "user_email": row.user_email or "unknown@example.com",
                    "organization_id": str(row.organization_id) if row.organization_id else None,
                    "organization_name": row.organization_name or "No Organization",
                    "request_count": row.request_count,
                    "total_tokens": row.total_tokens,
                    "input_tokens": row.input_tokens,
                    "output_tokens": row.output_tokens,
                    "total_cost_usd": float(row.total_cost_usd or 0.0),
                    "last_request_at": row.last_request_at.isoformat()
                    if row.last_request_at
                    else None,
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to get usage by user detailed: {e}", exc_info=True)
            return []

    @staticmethod
    async def get_usage_by_organization_detailed(
        db: AsyncSession,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[dict]:
        """Get usage by organization with org details and user count.

        Args:
            db (AsyncSession): Database session.
            start_date (Optional[datetime]): Start date filter.
            end_date (Optional[datetime]): End date filter.

        Returns:
            list[dict]: Organization usage with name, user count, cost, tokens.

        Examples:
            >>> orgs = await tracker.get_usage_by_organization_detailed(db=db)
            >>> for org in orgs:
            ...     print(f"{org['organization_name']}: ${org['total_cost_usd']:.2f}")
        """
        try:
            from app.api.modules.v1.organization.models.organization_model import Organization

            query = (
                select(
                    LLMUsageLog.organization_id,
                    Organization.name.label("organization_name"),
                    Organization.plan,
                    func.count(func.distinct(LLMUsageLog.user_id)).label("unique_users"),
                    func.count(LLMUsageLog.id).label("request_count"),
                    func.sum(LLMUsageLog.total_tokens).label("total_tokens"),
                    func.sum(LLMUsageLog.cost_usd).label("total_cost_usd"),
                    func.max(LLMUsageLog.created_at).label("last_request_at"),
                )
                .join(Organization, LLMUsageLog.organization_id == Organization.id, isouter=True)
                .where(LLMUsageLog.organization_id.isnot(None))
                .group_by(
                    LLMUsageLog.organization_id,
                    Organization.name,
                    Organization.plan,
                )
                .order_by(func.sum(LLMUsageLog.cost_usd).desc())
            )

            if start_date:
                query = query.where(LLMUsageLog.created_at >= start_date)
            if end_date:
                query = query.where(LLMUsageLog.created_at <= end_date)

            result = await db.execute(query)
            rows = result.all()

            return [
                {
                    "organization_id": str(row.organization_id),
                    "organization_name": row.organization_name or "Unknown Organization",
                    "plan": row.plan or "trialing",
                    "unique_users": row.unique_users,
                    "request_count": row.request_count,
                    "total_tokens": row.total_tokens,
                    "total_cost_usd": float(row.total_cost_usd or 0.0),
                    "last_request_at": row.last_request_at.isoformat()
                    if row.last_request_at
                    else None,
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to get usage by organization detailed: {e}", exc_info=True)
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
            db (AsyncSession): Database session.
            user_id (Optional[UUID]): Filter by user ID.
            organization_id (Optional[UUID]): Filter by organization ID.
            project_id (Optional[UUID]): Filter by project ID.
            start_date (Optional[datetime]): Start date filter.
            end_date (Optional[datetime]): End date filter.
            limit (int): Maximum number of logs to return.
            offset (int): Offset for pagination.

        Returns:
            dict: Paginated logs with user/org/project details.

        Examples:
            >>> logs = await tracker.get_detailed_logs(db=db, limit=50)
            >>> print(f"Found {logs['total']} logs")
        """
        try:
            from app.api.modules.v1.organization.models.organization_model import Organization
            from app.api.modules.v1.projects.models.project_model import Project
            from app.api.modules.v1.users.models.users_model import User

            query = (
                select(
                    LLMUsageLog,
                    User.name.label("user_name"),
                    User.email.label("user_email"),
                    Organization.name.label("organization_name"),
                    Project.title.label("project_name"),
                )
                .join(User, LLMUsageLog.user_id == User.id, isouter=True)
                .join(Organization, LLMUsageLog.organization_id == Organization.id, isouter=True)
                .join(Project, LLMUsageLog.project_id == Project.id, isouter=True)
                .order_by(LLMUsageLog.created_at.desc())
            )

            if user_id:
                query = query.where(LLMUsageLog.user_id == user_id)
            if organization_id:
                query = query.where(LLMUsageLog.organization_id == organization_id)
            if project_id:
                query = query.where(LLMUsageLog.project_id == project_id)
            if start_date:
                query = query.where(LLMUsageLog.created_at >= start_date)
            if end_date:
                query = query.where(LLMUsageLog.created_at <= end_date)

            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await db.execute(count_query)
            total_count = total_result.scalar()

            # Get paginated results
            query = query.limit(limit).offset(offset)
            result = await db.execute(query)
            rows = result.all()

            logs = [
                {
                    "id": str(row.LLMUsageLog.id),
                    "request_id": row.LLMUsageLog.request_id,
                    "model": row.LLMUsageLog.model,
                    "provider": row.LLMUsageLog.provider,
                    "user": {
                        "id": str(row.LLMUsageLog.user_id) if row.LLMUsageLog.user_id else None,
                        "name": row.user_name or "Unknown",
                        "email": row.user_email or "unknown@example.com",
                    },
                    "organization": {
                        "id": str(row.LLMUsageLog.organization_id)
                        if row.LLMUsageLog.organization_id
                        else None,
                        "name": row.organization_name or "No Organization",
                    },
                    "project": {
                        "id": str(row.LLMUsageLog.project_id)
                        if row.LLMUsageLog.project_id
                        else None,
                        "name": row.project_name or "No Project",
                    },
                    "tokens": {
                        "input": row.LLMUsageLog.input_tokens,
                        "output": row.LLMUsageLog.output_tokens,
                        "total": row.LLMUsageLog.total_tokens,
                    },
                    "cost_usd": row.LLMUsageLog.cost_usd,
                    "latency_ms": row.LLMUsageLog.latency_ms,
                    "success": row.LLMUsageLog.success,
                    "error_message": row.LLMUsageLog.error_message,
                    "endpoint": row.LLMUsageLog.endpoint,
                    "ip_address": row.LLMUsageLog.ip_address,
                    "created_at": row.LLMUsageLog.created_at.isoformat(),
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
