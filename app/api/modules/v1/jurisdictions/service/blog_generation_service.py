"""Service for generating blog posts from jurisdiction state data.

Supports both sync (Celery task) and async (FastAPI route) contexts.
Generates domain-agnostic blog content by pulling context from:
- Organization.industry
- Project.master_prompt
- Jurisdiction.prompt

Follows the exact pattern used in AIExtractionService for sync/async handling.
"""

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple, Union, cast
from uuid import UUID, uuid4

from fastapi import status as http_status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, selectinload

from app.api.core.custom_exceptions.exceptions import (
    BlogGenerationInProgressError,
    ProcessingError,
    ResourceNotFoundError,
)
from app.api.core.llm.llm_manager import LLMManager
from app.api.modules.v1.jurisdictions.models.blog_generation_job import (
    BlogGenerationJob,
    BlogGenerationJobStatus,
    ProjectBulkBlogJob,
    ProjectBulkBlogJobStatus,
)
from app.api.modules.v1.jurisdictions.models.jurisdiction_blog_post import JurisdictionBlogPost
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.jurisdictions.models.jurisdiction_state import (
    JurisdictionState,
    JurisdictionStateHistory,
)
from app.api.modules.v1.jurisdictions.prompts.blog_prompts import (
    BLOG_CONTENT_PROMPT,
    BLOG_PLACEHOLDER_CONTENT,
    BLOG_SYSTEM_PROMPT,
)
from app.api.modules.v1.jurisdictions.schemas.blog_schema import (
    BlogGenerationJobResponse,
    BlogLLMOutput,
    BlogPostResponse,
)
from app.api.modules.v1.jurisdictions.service.async_jurisdiction_state_service import (
    AsyncJurisdictionStateService,
)
from app.api.modules.v1.jurisdictions.service.blog_artifact_service import (
    build_public_resource_url,
    delete_artifact,
    render_html_body,
    write_artifact,
)
from app.api.modules.v1.jurisdictions.service.blog_search_service import crud as blog_crud
from app.api.modules.v1.jurisdictions.service.jurisdiction_state_service import (
    JurisdictionStateService,
)
from app.api.modules.v1.projects.models.project_model import Project
from app.api.utils.pagination import calculate_pagination

logger = logging.getLogger(__name__)


class BlogGenerationService:
    """Service for generating blog posts from jurisdiction state data.

    Handles both sync (Celery) and async (FastAPI) contexts.
    Generates domain-agnostic content based on Organization, Project,
    and Jurisdiction context fields.

    Attributes:
        db: Database session (Session or AsyncSession).
        is_async: Whether the session is async.

    Examples:
        >>> # Sync context (Celery task)
        >>> service = BlogGenerationService(sync_session)
        >>> result = service.generate_blog_post_sync(jurisdiction_id)

        >>> # Async context (FastAPI route)
        >>> service = BlogGenerationService(async_session)
        >>> result = await service.generate_blog_post_async(jurisdiction_id)
    """

    HISTORY_FIELD_ACRONYMS = {
        "paye": "PAYE",
        "nhf": "NHF",
        "vat": "VAT",
        "cit": "CIT",
        "pit": "PIT",
    }
    RESOURCE_ROOT_SEGMENT = "resources"

    def __init__(self, db: Union[Session, AsyncSession]):
        """Initialize blog generation service.

        Args:
            db: Database session (sync or async).

        Examples:
            >>> service = BlogGenerationService(db)
        """
        self.db = db
        self.is_async = isinstance(db, AsyncSession)

    def generate_blog_post_sync(
        self,
        jurisdiction_id: UUID,
        job_id: Optional[UUID] = None,
        skip_placeholder: bool = False,
    ) -> Dict[str, Any]:
        """Generate blog post synchronously (for Celery tasks).

        Called inline from consolidation task after Day 1 auto-accept.
        Uses LLMManager.generate_with_tracking_sync() to avoid event loop issues.

        Args:
            jurisdiction_id: Jurisdiction to generate blog for.
            job_id: Optional BlogGenerationJob ID for status tracking.
            skip_placeholder: If True, return 'skipped_no_data' instead of writing
                a Coming Soon placeholder when the ledger is empty. Use True for all
                automated/pipeline callers to prevent mass placeholder generation.

        Returns:
            dict: Generation result with status, message, version.
                status: "success" | "skipped" | "skipped_no_data" | "failed" | "placeholder"
                message: Human-readable result description.
                version: Blog post version number (None if failed).

        Raises:
            ProcessingError: If critical error occurs.

        Examples:
            >>> result = service.generate_blog_post_sync(jur_id, job_id)
            >>> print(result["status"])
            success
        """
        try:
            # Mark job as IN_PROGRESS
            self._update_job_status_sync(job_id, BlogGenerationJobStatus.IN_PROGRESS)

            stmt = (
                select(Jurisdiction)
                .options(selectinload(Jurisdiction.project).selectinload(Project.organization))
                .where(Jurisdiction.id == jurisdiction_id)
            )
            result = self.db.execute(stmt)
            jurisdiction = result.scalar_one_or_none()

            if not jurisdiction:
                self._update_job_status_sync(
                    job_id,
                    BlogGenerationJobStatus.FAILED,
                    error_message=f"Jurisdiction {jurisdiction_id} not found",
                )
                raise ProcessingError(message=f"Jurisdiction {jurisdiction_id} not found")

            domain_context = self._resolve_domain_context(jurisdiction)

            state_service = JurisdictionStateService(self.db)
            state_map = state_service.get_jurisdiction_state(jurisdiction_id)

            if not state_map:
                if skip_placeholder:
                    logger.warning(
                        f"generate_blog_post_sync: No ledger data for {jurisdiction_id}. "
                        "skip_placeholder=True — blog NOT generated to prevent Coming Soon spam."
                    )
                    self._update_job_status_sync(job_id, BlogGenerationJobStatus.COMPLETED)
                    return {
                        "status": "skipped_no_data",
                        "jurisdiction_id": str(jurisdiction_id),
                        "message": "No ledger data available. Blog generation skipped.",
                        "version": None,
                    }
                result = self._generate_placeholder_sync(
                    jurisdiction_id, domain_context, jurisdiction
                )
                self._update_job_status_sync(job_id, BlogGenerationJobStatus.COMPLETED)
                return result

            formatted_state, content_hash = self._build_state_context(state_map)

            existing_blog = self._get_existing_blog_sync(jurisdiction_id)
            if existing_blog and existing_blog.content_hash == content_hash:
                logger.info(
                    f"Skipping blog regeneration for {jurisdiction_id}: content hash unchanged"
                )
                self._update_job_status_sync(job_id, BlogGenerationJobStatus.COMPLETED)
                return {
                    "status": "skipped",
                    "jurisdiction_id": str(jurisdiction_id),
                    "message": "Blog content unchanged, skipped regeneration",
                    "version": existing_blog.version,
                }

            history_context = self._load_history_context_sync(jurisdiction_id)

            try:
                llm_output, generation_model = self._call_llm_sync(
                    domain_context, formatted_state, history_context
                )
            except Exception as e:
                logger.error(f"LLM call failed for {jurisdiction_id}: {e}", exc_info=True)
                self._update_job_status_sync(
                    job_id,
                    BlogGenerationJobStatus.FAILED,
                    error_message=f"LLM call failed: {str(e)}",
                )
                return {
                    "status": "failed",
                    "jurisdiction_id": str(jurisdiction_id),
                    "message": "Blog generation encountered an error. Please try again.",
                    "version": existing_blog.version if existing_blog else None,
                }

            slug = self._slugify(domain_context["jurisdiction_name"], domain_context["industry"])
            breadcrumbs = self._build_breadcrumbs_sync(jurisdiction, slug)

            blog_post = self._upsert_blog_post_sync(
                jurisdiction_id=jurisdiction_id,
                title=llm_output.title,
                slug=slug,
                content=llm_output.content,
                meta_description=llm_output.meta_description,
                keywords=llm_output.keywords,
                content_hash=content_hash,
                generation_model=generation_model,
                existing=existing_blog,
                breadcrumbs=breadcrumbs,
            )

            self._update_job_status_sync(job_id, BlogGenerationJobStatus.COMPLETED)

            return {
                "status": "success",
                "jurisdiction_id": str(jurisdiction_id),
                "message": "Blog post generated successfully",
                "version": blog_post.version,
            }

        except ProcessingError:
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error in generate_blog_post_sync for {jurisdiction_id}: {e}",
                exc_info=True,
            )
            self._update_job_status_sync(
                job_id,
                BlogGenerationJobStatus.FAILED,
                error_message=f"Unexpected error: {str(e)}",
            )
            raise ProcessingError(message="Blog generation failed. Please try again.")

    async def generate_blog_post_async(
        self,
        jurisdiction_id: UUID,
        job_id: Optional[UUID] = None,
        skip_placeholder: bool = False,
    ) -> Dict[str, Any]:
        """Generate blog post asynchronously (for FastAPI routes).

        Called from BackgroundTasks in manual trigger endpoint.
        Uses LLMManager.generate_with_tracking() for async context.

        Args:
            jurisdiction_id: Jurisdiction to generate blog for.
            job_id: Optional BlogGenerationJob ID for status tracking.
            skip_placeholder: If True, return 'skipped_no_data' instead of writing
                a Coming Soon placeholder when the ledger is empty. Use True for all
                automated/pipeline callers to prevent mass placeholder generation.

        Returns:
            dict: Generation result (same structure as sync version).

        Raises:
            ProcessingError: If critical error occurs.

        Examples:
            >>> result = await service.generate_blog_post_async(jur_id, job_id)
        """
        try:
            # Mark job as IN_PROGRESS
            await self._update_job_status_async(job_id, BlogGenerationJobStatus.IN_PROGRESS)

            stmt = (
                select(Jurisdiction)
                .options(selectinload(Jurisdiction.project).selectinload(Project.organization))
                .where(Jurisdiction.id == jurisdiction_id)
            )
            result = await self.db.execute(stmt)
            jurisdiction = result.scalar_one_or_none()

            if not jurisdiction:
                await self._update_job_status_async(
                    job_id,
                    BlogGenerationJobStatus.FAILED,
                    error_message=f"Jurisdiction {jurisdiction_id} not found",
                )
                raise ProcessingError(message=f"Jurisdiction {jurisdiction_id} not found")

            domain_context = self._resolve_domain_context(jurisdiction)

            state_service = AsyncJurisdictionStateService(self.db)
            state_map = await state_service.get_jurisdiction_state(jurisdiction_id)

            if not state_map:
                if skip_placeholder:
                    logger.warning(
                        f"generate_blog_post_async: No ledger data for {jurisdiction_id}. "
                        "skip_placeholder=True — blog NOT generated to prevent Coming Soon spam."
                    )
                    await self._update_job_status_async(job_id, BlogGenerationJobStatus.COMPLETED)
                    return {
                        "status": "skipped_no_data",
                        "jurisdiction_id": str(jurisdiction_id),
                        "message": "No ledger data available. Blog generation skipped.",
                        "version": None,
                    }
                result = await self._generate_placeholder_async(
                    jurisdiction_id, domain_context, jurisdiction
                )
                await self._update_job_status_async(job_id, BlogGenerationJobStatus.COMPLETED)
                return result

            formatted_state, content_hash = self._build_state_context(state_map)

            existing_blog = await self._get_existing_blog_async(jurisdiction_id)
            if existing_blog and existing_blog.content_hash == content_hash:
                logger.info(
                    f"Skipping blog regeneration for {jurisdiction_id}: content hash unchanged"
                )
                await self._update_job_status_async(job_id, BlogGenerationJobStatus.COMPLETED)
                return {
                    "status": "skipped",
                    "jurisdiction_id": str(jurisdiction_id),
                    "message": "Blog content unchanged, skipped regeneration",
                    "version": existing_blog.version,
                }

            history_context = await self._load_history_context_async(jurisdiction_id)

            try:
                llm_output, generation_model = await self._call_llm_async(
                    domain_context, formatted_state, history_context
                )
            except Exception as e:
                logger.error(f"LLM call failed for {jurisdiction_id}: {e}", exc_info=True)
                await self._update_job_status_async(
                    job_id,
                    BlogGenerationJobStatus.FAILED,
                    error_message=f"LLM call failed: {str(e)}",
                )
                return {
                    "status": "failed",
                    "jurisdiction_id": str(jurisdiction_id),
                    "message": "Blog generation encountered an error. Please try again.",
                    "version": existing_blog.version if existing_blog else None,
                }

            slug = self._slugify(domain_context["jurisdiction_name"], domain_context["industry"])
            breadcrumbs = await self._build_breadcrumbs_async(jurisdiction, slug)

            blog_post = await self._upsert_blog_post_async(
                jurisdiction_id=jurisdiction_id,
                title=llm_output.title,
                slug=slug,
                content=llm_output.content,
                meta_description=llm_output.meta_description,
                keywords=llm_output.keywords,
                content_hash=content_hash,
                generation_model=generation_model,
                existing=existing_blog,
                breadcrumbs=breadcrumbs,
            )

            await self._update_job_status_async(job_id, BlogGenerationJobStatus.COMPLETED)

            return {
                "status": "success",
                "jurisdiction_id": str(jurisdiction_id),
                "message": "Blog post generated successfully",
                "version": blog_post.version,
            }

        except ProcessingError:
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error in generate_blog_post_async for {jurisdiction_id}: {e}",
                exc_info=True,
            )
            await self._update_job_status_async(
                job_id,
                BlogGenerationJobStatus.FAILED,
                error_message=f"Unexpected error: {str(e)}",
            )
            raise ProcessingError(message="Blog generation failed. Please try again.")

    async def _update_bulk_job_status_async(
        self,
        bulk_job_id: UUID,
        status: Optional[ProjectBulkBlogJobStatus] = None,
        processed: Optional[int] = None,
        failed: Optional[int] = None,
        skipped: Optional[int] = None,
        error_summary: Optional[str] = None,
    ) -> None:
        """Update ProjectBulkBlogJob status asynchronously."""
        try:
            stmt = select(ProjectBulkBlogJob).where(ProjectBulkBlogJob.id == bulk_job_id)
            result = await self.db.execute(stmt)
            job = result.scalar_one_or_none()
            if not job:
                return

            if status:
                job.status = status
                if status == ProjectBulkBlogJobStatus.IN_PROGRESS and not job.started_at:
                    job.started_at = datetime.now(timezone.utc)
                elif status in (
                    ProjectBulkBlogJobStatus.COMPLETED,
                    ProjectBulkBlogJobStatus.COMPLETED_WITH_ERRORS,
                    ProjectBulkBlogJobStatus.FAILED,
                ):
                    job.completed_at = datetime.now(timezone.utc)

            if processed is not None:
                job.processed = processed
            if failed is not None:
                job.failed = failed
            if skipped is not None:
                job.skipped = skipped
            if error_summary is not None:
                job.error_summary = error_summary

            self.db.add(job)
            await self.db.commit()
        except Exception as e:
            logger.error(f"Failed to update bulk job {bulk_job_id}: {e}", exc_info=True)

    async def _execute_bulk_generation_bg(self, bulk_job_id: UUID) -> None:
        """Background execution logic for a bulk blog generation job."""

        # 1. Fetch initial job state & project jurisdictions
        stmt = select(ProjectBulkBlogJob).where(ProjectBulkBlogJob.id == bulk_job_id)
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()
        if not job:
            return

        project_id = job.project_id
        publish_requested = job.publish_requested

        try:
            jur_stmt = select(Jurisdiction).where(Jurisdiction.project_id == project_id)
            jur_result = await self.db.execute(jur_stmt)
            jurisdictions = jur_result.scalars().all()

            if not jurisdictions:
                await self._update_bulk_job_status_async(
                    bulk_job_id=bulk_job_id,
                    status=ProjectBulkBlogJobStatus.FAILED,
                    error_summary="No jurisdictions found in project.",
                )
                return

            await self._update_bulk_job_status_async(
                bulk_job_id=bulk_job_id,
                status=ProjectBulkBlogJobStatus.IN_PROGRESS,
                processed=0,
                failed=0,
                skipped=0,
            )

            # 2. Iterate and process, continuing on error
            processed_count, failed_count, skipped_count = 0, 0, 0

            # Get project organization ID for publishing dependency
            proj_stmt = select(Project).where(Project.id == project_id)
            proj_res = await self.db.execute(proj_stmt)
            project = proj_res.scalar_one()

            for jur in jurisdictions:
                try:
                    # Pre-flight ledger check: never produce a Coming Soon placeholder
                    # during a bulk run. If the ledger is empty, the jurisdiction's
                    # scraping/consolidation pipeline has not yet completed for this
                    # jurisdiction. Mark it as skipped and move on.
                    state_svc = AsyncJurisdictionStateService(self.db)
                    has_ledger_data = await state_svc.get_jurisdiction_state(jur.id)
                    if not has_ledger_data:
                        logger.warning(
                            f"Bulk generation: jurisdiction {jur.id} ({jur.name!r}) "
                            "has an empty ledger — skipping to prevent Coming Soon spam. "
                            "Re-run bulk generation once scraping/consolidation is complete."
                        )
                        skipped_count += 1
                        continue

                    gen_result = await self.generate_blog_post_async(jur.id, None)

                    if gen_result.get("status") in ("skipped", "skipped_no_data"):
                        skipped_count += 1
                    elif gen_result.get("status") == "failed":
                        failed_count += 1
                    else:
                        processed_count += 1

                        if publish_requested:
                            # Use internal publish logic directly
                            await self.publish_blog_post(self.db, project.org_id, jur.id, True)

                except Exception as e:
                    logger.error(
                        f"Bulk generation failed for jurisdiction {jur.id}: {e}", exc_info=True
                    )
                    failed_count += 1

                # Update progress incrementally every 5 jurisdictions or at end
                if (processed_count + failed_count + skipped_count) % 5 == 0:
                    await self._update_bulk_job_status_async(
                        bulk_job_id=bulk_job_id,
                        processed=processed_count,
                        failed=failed_count,
                        skipped=skipped_count,
                    )

            # 3. Finalize Job Status
            final_status = ProjectBulkBlogJobStatus.COMPLETED
            if failed_count == len(jurisdictions):
                final_status = ProjectBulkBlogJobStatus.FAILED
            elif failed_count > 0:
                final_status = ProjectBulkBlogJobStatus.COMPLETED_WITH_ERRORS

            await self._update_bulk_job_status_async(
                bulk_job_id=bulk_job_id,
                status=final_status,
                processed=processed_count,
                failed=failed_count,
                skipped=skipped_count,
            )

        except Exception as e:
            logger.error(
                f"Critical error in bulk generation execution for job {bulk_job_id}: {e}",
                exc_info=True,
            )
            await self._update_bulk_job_status_async(
                bulk_job_id=bulk_job_id,
                status=ProjectBulkBlogJobStatus.FAILED,
                error_summary=str(e)[:500],
            )

    async def start_bulk_generation_async(
        self, project_id: UUID, user_id: UUID, publish_after_generate: bool = False
    ) -> ProjectBulkBlogJob:
        """Start a bulk blog generation job for a project synchronously and return job entity.

        Note: The actual background task dispatching happens in the route.
        """
        from app.api.core.custom_exceptions.exceptions import (
            EmptyJurisdictionSetError,
            ProjectBulkBlogInProgressError,
        )

        # Check for active job
        stmt = select(ProjectBulkBlogJob).where(
            ProjectBulkBlogJob.project_id == project_id,
            ProjectBulkBlogJob.status.in_(
                [ProjectBulkBlogJobStatus.PENDING, ProjectBulkBlogJobStatus.IN_PROGRESS]
            ),
        )
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            raise ProjectBulkBlogInProgressError()

        # Count jurisdictions
        count_stmt = (
            select(func.count())
            .select_from(Jurisdiction)
            .where(Jurisdiction.project_id == project_id)
        )
        count_result = await self.db.execute(count_stmt)
        total_jurisdictions = count_result.scalar() or 0

        if total_jurisdictions == 0:
            raise EmptyJurisdictionSetError()

        # Create job
        job = ProjectBulkBlogJob(
            project_id=project_id,
            status=ProjectBulkBlogJobStatus.PENDING,
            totals=total_jurisdictions,
            publish_requested=publish_after_generate,
            triggered_by=user_id,
        )
        self.db.add(job)
        try:
            await self.db.commit()
            await self.db.refresh(job)
        except IntegrityError:
            await self.db.rollback()
            raise ProjectBulkBlogInProgressError()

        return job

    def _resolve_domain_context(self, jurisdiction: Jurisdiction) -> Dict[str, str]:
        """Extract domain context from Jurisdiction → Project → Organization hierarchy.

        Args:
            jurisdiction: Jurisdiction model instance (with .project.organization loaded).

        Returns:
            dict: Context with industry, project_prompt, jurisdiction_prompt,
                jurisdiction_name. Note: org_type is intentionally omitted to
                ensure industry-generic content that doesn't reference clients.

        Examples:
            >>> context = service._resolve_domain_context(jurisdiction)
            >>> print(context["industry"])
            EOR
        """
        project = jurisdiction.project
        organization = project.organization if project else None

        return {
            "industry": organization.industry if organization else "General Compliance",
            "project_prompt": (
                project.master_prompt
                if project and project.master_prompt
                else "Regulatory monitoring"
            ),
            "jurisdiction_prompt": (
                jurisdiction.prompt if jurisdiction.prompt else "Monitor regulations"
            ),
            "jurisdiction_name": jurisdiction.name,
        }

    def _build_state_context(self, state_map: Dict[str, Any]) -> Tuple[str, str]:
        """Format jurisdiction state into LLM context string and compute hash.

        Args:
            state_map: Map of field_key -> JurisdictionState.

        Returns:
            tuple: (formatted_context, content_hash)

        Examples:
            >>> formatted, hash_val = service._build_state_context(state_map)
            >>> print(formatted[:50])
            - minimum_wage: $15.00/hour
        """
        lines = []
        for field_key, state in state_map.items():
            lines.append(f"- {field_key}: {state.value}")
            if state.source_evidence:
                sources_str = ", ".join(state.source_evidence[:3])
                lines.append(f"  Sources: {sources_str}")

        formatted = "\n".join(lines)
        content_hash = hashlib.sha256(formatted.encode("utf-8")).hexdigest()

        return formatted, content_hash

    def _slugify(self, name: str, industry: str) -> str:
        """Convert jurisdiction name and industry to URL-safe slug.

        Args:
            name: Jurisdiction name (e.g., "California").
            industry: Industry name (e.g., "EOR").

        Returns:
            str: URL slug (e.g., "eor-guide-california").

        Examples:
            >>> slug = service._slugify("California", "EOR")
            >>> print(slug)
            eor-guide-california
        """
        industry_safe = re.sub(r"[^\w\s-]", "", industry.lower()).strip()
        industry_safe = re.sub(r"[-\s]+", "-", industry_safe)

        name_safe = re.sub(r"[^\w\s-]", "", name.lower()).strip()
        name_safe = re.sub(r"[-\s]+", "-", name_safe)

        return f"{industry_safe}-guide-{name_safe}"[:100]

    @staticmethod
    def _slugify_segment(value: Optional[str]) -> str:
        """Convert an arbitrary label into a stable path segment.

        Args:
            value: Raw label value to convert.

        Returns:
            str: URL-safe path segment.

        Examples:
            >>> BlogGenerationService._slugify_segment("Employment Rules")
            'employment-rules'
        """
        if not value:
            return "item"

        normalized = re.sub(r"[^\w\s-]", "", value.lower()).strip()
        normalized = re.sub(r"[-\s]+", "-", normalized)
        return normalized or "item"

    @staticmethod
    async def _build_jurisdiction_hierarchy_segments(
        db: AsyncSession,
        jurisdiction: Jurisdiction,
    ) -> list[str]:
        """Build slugified jurisdiction hierarchy segments from root to current node.

        Args:
            db: Active async database session.
            jurisdiction: Current jurisdiction instance.

        Returns:
            list[str]: Ordered slug path segments.

        Examples:
            >>> segments = await BlogGenerationService._build_jurisdiction_hierarchy_segments(
            ...     db,
            ...     jurisdiction,
            ... )
            >>> len(segments) >= 1
            True
        """
        segments = [BlogGenerationService._slugify_segment(jurisdiction.name)]
        current_parent_id = jurisdiction.parent_id
        visited_parent_ids: set[UUID] = set()

        while current_parent_id and current_parent_id not in visited_parent_ids:
            visited_parent_ids.add(current_parent_id)
            parent_stmt = select(Jurisdiction).where(Jurisdiction.id == current_parent_id)
            parent_result = await db.execute(parent_stmt)
            parent = parent_result.scalar_one_or_none()

            if not parent:
                break

            segments.append(BlogGenerationService._slugify_segment(parent.name))
            current_parent_id = parent.parent_id

        segments.reverse()
        return segments

    @staticmethod
    async def _build_public_resource_path(
        db: AsyncSession,
        jurisdiction: Jurisdiction,
        blog_post: JurisdictionBlogPost,
    ) -> str:
        """Build canonical public resource path for a blog post.

        Args:
            db: Active async database session.
            jurisdiction: Jurisdiction associated with the blog post.
            blog_post: Blog post model instance.

        Returns:
            str: Canonical path beginning with ``resources/``.

        Examples:
            >>> path = await BlogGenerationService._build_public_resource_path(
            ...     db,
            ...     jurisdiction,
            ...     blog_post,
            ... )
            >>> path.startswith("resources/")
            True
        """
        project = await db.get(Project, jurisdiction.project_id)
        project_title = project.title if project else "project"
        project_segment = BlogGenerationService._slugify_segment(project_title)
        hierarchy_segments = await BlogGenerationService._build_jurisdiction_hierarchy_segments(
            db,
            jurisdiction,
        )
        post_segment = BlogGenerationService._slugify_segment(blog_post.slug)
        path_segments = [
            BlogGenerationService.RESOURCE_ROOT_SEGMENT,
            project_segment,
            *hierarchy_segments,
            post_segment,
        ]
        return "/".join(path_segments)

    @staticmethod
    def _build_public_resource_url(resource_path: str) -> str:
        """Build canonical absolute public URL from a resource path.

        Args:
            resource_path: Canonical resource path.

        Returns:
            str: Absolute URL for the published blog page.

        Examples:
            >>> BlogGenerationService._build_public_resource_url("resources/p/a/b")
            'https://legalwatch.dog/resources/p/a/b/'
        """
        return build_public_resource_url(resource_path)

    def _format_history_context(self, rows: list) -> str:
        """Format JurisdictionStateHistory query rows into a Markdown table string.

        Produces a table suitable for injection into BLOG_CONTENT_PROMPT's
        {history_context} placeholder.  Returns a sentinel line when there are
        no rows so the LLM still receives a valid (empty-state) instruction.

        Args:
            rows: List of Row objects with attributes field_key, previous_value,
                new_value, changed_at, change_reason.

        Returns:
            str: Markdown table rows, or a "No changes recorded" sentinel.

        Examples:
            >>> rows = [SimpleNamespace(field_key='minimum_wage',
            ...     previous_value='30000', new_value='70000',
            ...     changed_at=datetime(2024, 7, 1), change_reason='Accepted')]
            >>> print(service._format_history_context(rows))
            | Minimum Wage | 30000 | 70000 | 2024-07-01 | Accepted |
        """
        if not rows:
            return "No changes recorded."

        lines = [
            "| Field | Previous Value | New Value | Date Changed | Change Reason |",
            "|---|---|---|---|---|",
        ]
        for row in rows:
            field_label = self._format_history_field_label(row.field_key)
            prev = self._format_history_cell_value(row.previous_value)
            new_value = self._format_history_cell_value(row.new_value)
            change_reason = self._format_history_cell_value(row.change_reason)
            changed_at_str = (
                row.changed_at.strftime("%Y-%m-%d")
                if hasattr(row.changed_at, "strftime")
                else self._format_history_cell_value(row.changed_at)
            )
            lines.append(
                f"| {field_label} | {prev} | {new_value} | {changed_at_str} | {change_reason} |"
            )
        return "\n".join(lines)

    def _format_history_field_label(self, field_key: Optional[str]) -> str:
        """Convert a snake_case history field key into a user-friendly label.

        Args:
            field_key: Raw state field key (for example, "paye_tax_bands").

        Returns:
            str: Human-readable label with preserved known acronyms.

        Examples:
            >>> service._format_history_field_label("paye_tax_bands")
            'PAYE Tax Bands'
        """
        if not field_key:
            return "—"

        tokens = [token for token in field_key.split("_") if token]
        if not tokens:
            return "—"

        formatted_tokens = [
            self.HISTORY_FIELD_ACRONYMS.get(token.lower(), token.capitalize()) for token in tokens
        ]
        return " ".join(formatted_tokens)

    def _format_history_cell_value(self, value: Any) -> str:
        """Format and escape a markdown table cell value for history rows.

        Args:
            value: Raw value from history row columns.

        Returns:
            str: Safe markdown cell text with newlines and pipe characters escaped.

        Examples:
            >>> service._format_history_cell_value("A|B\nC")
            'A\\|B<br>C'
        """
        if value is None:
            return "—"

        text = str(value)
        if not text:
            return "—"

        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = text.replace("|", "\\|")
        return text.replace("\n", "<br>")

    def _load_history_context_sync(self, jurisdiction_id: UUID) -> str:
        """Load and format JurisdictionStateHistory rows synchronously.

        Queries all history entries for states belonging to the given
        jurisdiction, ordered by changed_at descending and capped at 100
        rows to avoid flooding the LLM context window.

        Args:
            jurisdiction_id: UUID of the jurisdiction whose history to load.

        Returns:
            str: Formatted Markdown table string, or "No changes recorded."

        Examples:
            >>> history = service._load_history_context_sync(jur_id)
            >>> assert "| Field |" in history or history == "No changes recorded."
        """
        try:
            stmt = (
                select(
                    JurisdictionState.field_key,
                    JurisdictionStateHistory.previous_value,
                    JurisdictionStateHistory.new_value,
                    JurisdictionStateHistory.changed_at,
                    JurisdictionStateHistory.change_reason,
                )
                .join(
                    JurisdictionState,
                    JurisdictionStateHistory.state_id == JurisdictionState.id,
                )
                .where(JurisdictionState.jurisdiction_id == jurisdiction_id)
                .order_by(JurisdictionStateHistory.changed_at.desc())
                .limit(100)
            )
            result = self.db.execute(stmt)
            rows = [
                row for row in result.all() if row.change_reason != "Initial State Initialization"
            ]
            return self._format_history_context(rows)
        except Exception as e:
            logger.warning(
                f"Failed to load history context for {jurisdiction_id}: {e}",
                exc_info=True,
            )
            return "No changes recorded."

    async def _load_history_context_async(self, jurisdiction_id: UUID) -> str:
        """Load and format JurisdictionStateHistory rows asynchronously.

        Async counterpart of _load_history_context_sync for use in FastAPI routes.

        Args:
            jurisdiction_id: UUID of the jurisdiction whose history to load.

        Returns:
            str: Formatted Markdown table string, or "No changes recorded."

        Examples:
            >>> history = await service._load_history_context_async(jur_id)
            >>> assert "| Field |" in history or history == "No changes recorded."
        """
        try:
            stmt = (
                select(
                    JurisdictionState.field_key,
                    JurisdictionStateHistory.previous_value,
                    JurisdictionStateHistory.new_value,
                    JurisdictionStateHistory.changed_at,
                    JurisdictionStateHistory.change_reason,
                )
                .join(
                    JurisdictionState,
                    JurisdictionStateHistory.state_id == JurisdictionState.id,
                )
                .where(JurisdictionState.jurisdiction_id == jurisdiction_id)
                .order_by(JurisdictionStateHistory.changed_at.desc())
                .limit(100)
            )
            result = await self.db.execute(stmt)
            rows = [
                row for row in result.all() if row.change_reason != "Initial State Initialization"
            ]
            return self._format_history_context(rows)
        except Exception as e:
            logger.warning(
                f"Failed to load history context for {jurisdiction_id}: {e}",
                exc_info=True,
            )
            return "No changes recorded."

    def _build_breadcrumbs_sync(
        self,
        jurisdiction: Jurisdiction,
        post_slug: str,
    ) -> list[Dict[str, str]]:
        """Build precomputed breadcrumb trail for a jurisdiction.

        Traverses the parent hierarchy to build a list of breadcrumb items
        from root to the current jurisdiction. Each item includes name and URL.

        The URL structure follows: /resources/{project}/{hierarchy}/{slug}/

        Args:
            jurisdiction: Jurisdiction model instance.
            post_slug: Slug of the blog post for URL building.

        Returns:
            list[Dict[str, str]]: List of breadcrumb items with name and url keys.

        Examples:
            >>> crumbs = service._build_breadcrumbs_sync(jurisdiction, "california")
            >>> len(crumbs) >= 1
            True
        """
        from app.api.core.config import settings

        base_url = (settings.BLOG_SITE_URL or "https://legalwatch.dog").rstrip("/")

        project = self.db.get(Project, jurisdiction.project_id)
        project_segment = self._slugify_segment(project.title) if project else "project"

        hierarchy_chain = [jurisdiction]
        current_parent_id = jurisdiction.parent_id
        visited = set()

        while current_parent_id and current_parent_id not in visited:
            visited.add(current_parent_id)
            parent = self.db.get(Jurisdiction, current_parent_id)
            if not parent:
                break
            hierarchy_chain.insert(0, parent)
            current_parent_id = parent.parent_id

        breadcrumbs = []
        for node in hierarchy_chain:
            node_slug = self._slugify_segment(node.name)
            path = f"/resources/{project_segment}/{node_slug}/{post_slug}/"
            breadcrumbs.append(
                {
                    "name": node.name,
                    "url": f"{base_url}{path}",
                }
            )

        return breadcrumbs

    async def _build_breadcrumbs_async(
        self,
        jurisdiction: Jurisdiction,
        post_slug: str,
    ) -> list[Dict[str, str]]:
        """Build precomputed breadcrumb trail for a jurisdiction (async version).

        Traverses the parent hierarchy to build a list of breadcrumb items
        from root to the current jurisdiction. Each item includes name and URL.

        Args:
            jurisdiction: Jurisdiction model instance.
            post_slug: Slug of the blog post for URL building.

        Returns:
            list[Dict[str, str]]: List of breadcrumb items with "name" and "url" keys.

        Examples:
            >>> crumbs = await service._build_breadcrumbs_async(jurisdiction, "california")
            >>> len(crumbs) >= 1
            True
        """
        from app.api.core.config import settings

        base_url = (settings.BLOG_SITE_URL or "https://legalwatch.dog").rstrip("/")

        project = await self.db.get(Project, jurisdiction.project_id)
        project_segment = self._slugify_segment(project.title) if project else "project"

        hierarchy_chain = [jurisdiction]
        current_parent_id = jurisdiction.parent_id
        visited = set()

        while current_parent_id and current_parent_id not in visited:
            visited.add(current_parent_id)
            parent = await self.db.get(Jurisdiction, current_parent_id)
            if not parent:
                break
            hierarchy_chain.insert(0, parent)
            current_parent_id = parent.parent_id

        breadcrumbs = []
        for node in hierarchy_chain:
            node_slug = self._slugify_segment(node.name)
            path = f"/resources/{project_segment}/{node_slug}/{post_slug}/"
            breadcrumbs.append(
                {
                    "name": node.name,
                    "url": f"{base_url}{path}",
                }
            )

        return breadcrumbs

    def _call_llm_sync(
        self, domain_context: Dict[str, str], formatted_state: str, history_context: str = ""
    ) -> Tuple[BlogLLMOutput, str]:
        """Call LLM synchronously to generate blog content.

        Args:
            domain_context: Context dict with industry, org_type, etc.
            formatted_state: Formatted Golden Record state string.
            history_context: Formatted regulatory change history table string.

        Returns:
            Tuple[BlogLLMOutput, str]: Validated LLM output and model name.

        Raises:
            ValidationError: If LLM output doesn't match schema.
            Exception: If LLM call fails.

        Examples:
            >>> output, model = service._call_llm_sync(context, state, history)
            >>> print(output.title)
        """
        llm_manager = LLMManager(db=self.db, enable_tracking=True)

        system_prompt = BLOG_SYSTEM_PROMPT.format(**domain_context)
        user_prompt = BLOG_CONTENT_PROMPT.format(
            formatted_state=formatted_state,
            history_context=history_context,
            **domain_context,
        )

        response = llm_manager.generate_with_tracking_sync(
            prompt=user_prompt,
            model_preference="balanced",
            temperature=0.3,
            max_tokens=3000,
            json_mode=True,  # Might not be needed when response_model is provided, but safe to keep
            system_prompt=system_prompt,
            endpoint="/api/v1/jurisdictions/blog/generate",
            response_model=BlogLLMOutput,
        )

        content = response.content
        if isinstance(content, BlogLLMOutput):
            return content, response.model

        if isinstance(content, dict):
            try:
                validated = BlogLLMOutput.model_validate(content)
                return validated, response.model
            except ValidationError as e:
                logger.error(f"Failed to validate dict output from LLM: {e}", exc_info=True)
                raise ProcessingError(message="LLM returned invalid blog content format") from e

        if isinstance(content, str):
            try:
                validated = BlogLLMOutput.model_validate_json(content)
                return validated, response.model
            except ValidationError as e:
                logger.error(f"Failed to validate string output from LLM: {e}", exc_info=True)
                raise ProcessingError(message="LLM returned invalid blog content format") from e

        logger.error(f"LLM returned unexpected type: {type(content)}")
        raise ProcessingError(message="LLM returned invalid blog content format")

    async def _call_llm_async(
        self,
        domain_context: Dict[str, str],
        formatted_state: str,
        history_context: str = "",
    ) -> Tuple[BlogLLMOutput, str]:
        """Call LLM asynchronously to generate blog content.

        Args:
            domain_context: Context dict with industry, org_type, etc.
            formatted_state: Formatted Golden Record state string.
            history_context: Formatted regulatory change history table string.

        Returns:
            Tuple[BlogLLMOutput, str]: Validated LLM output and model name.

        Raises:
            ValidationError: If LLM output doesn't match schema.
            Exception: If LLM call fails.

        Examples:
            >>> output, model = await service._call_llm_async(context, state, history)
        """
        llm_manager = LLMManager(db=self.db, enable_tracking=True)

        system_prompt = BLOG_SYSTEM_PROMPT.format(**domain_context)
        user_prompt = BLOG_CONTENT_PROMPT.format(
            formatted_state=formatted_state,
            history_context=history_context,
            **domain_context,
        )

        response = await llm_manager.generate_with_tracking(
            prompt=user_prompt,
            model_preference="balanced",
            temperature=0.3,
            max_tokens=3000,
            json_mode=True,
            system_prompt=system_prompt,
            endpoint="/api/v1/jurisdictions/blog/generate",
            response_model=BlogLLMOutput,
        )

        content = response.content
        if isinstance(content, BlogLLMOutput):
            return content, response.model

        if isinstance(content, dict):
            try:
                validated = BlogLLMOutput.model_validate(content)
                return validated, response.model
            except ValidationError as e:
                logger.error(f"Failed to validate dict await output from LLM: {e}", exc_info=True)
                raise ProcessingError(message="LLM returned invalid blog content format") from e

        if isinstance(content, str):
            try:
                validated = BlogLLMOutput.model_validate_json(content)
                return validated, response.model
            except ValidationError as e:
                logger.error(f"Failed to validate string await output from LLM: {e}", exc_info=True)
                raise ProcessingError(message="LLM returned invalid blog content format") from e

        logger.error(f"LLM returned unexpected type: {type(content)}")
        raise ProcessingError(message="LLM returned invalid blog content format")

    def _get_existing_blog_sync(self, jurisdiction_id: UUID) -> Optional[JurisdictionBlogPost]:
        """Get existing blog post synchronously.

        Args:
            jurisdiction_id: Jurisdiction ID.

        Returns:
            JurisdictionBlogPost or None if not found.

        Examples:
            >>> blog = service._get_existing_blog_sync(jur_id)
        """
        stmt = select(JurisdictionBlogPost).where(
            JurisdictionBlogPost.jurisdiction_id == jurisdiction_id
        )
        result = self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_existing_blog_async(
        self, jurisdiction_id: UUID
    ) -> Optional[JurisdictionBlogPost]:
        """Get existing blog post asynchronously.

        Args:
            jurisdiction_id: Jurisdiction ID.

        Returns:
            JurisdictionBlogPost or None.

        Examples:
            >>> blog = await service._get_existing_blog_async(jur_id)
        """
        stmt = select(JurisdictionBlogPost).where(
            JurisdictionBlogPost.jurisdiction_id == jurisdiction_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    def _upsert_blog_post_sync(
        self,
        jurisdiction_id: UUID,
        title: str,
        slug: str,
        content: str,
        meta_description: str,
        keywords: list,
        content_hash: str,
        generation_model: Optional[str] = None,
        existing: Optional[JurisdictionBlogPost] = None,
        breadcrumbs: Optional[list[Dict[str, str]]] = None,
    ) -> JurisdictionBlogPost:
        """Create or update blog post synchronously.

        Converts Markdown content to HTML at write time and stores both
        `content` (markdown source) and `content_html` (rendered body).

        Args:
            jurisdiction_id: Jurisdiction ID.
            title: Blog title.
            slug: URL slug.
            content: Markdown content (source of truth).
            meta_description: SEO description.
            keywords: SEO keywords.
            content_hash: SHA-256 hash of source data.
            generation_model: LLM model used for generation.
            existing: Existing blog post (if any).
            breadcrumbs: Precomputed breadcrumb trail for SEO markup.

        Returns:
            JurisdictionBlogPost: Created or updated post.

        Examples:
            >>> blog = service._upsert_blog_post_sync(...)
        """
        now = datetime.now(timezone.utc)
        content_html = render_html_body(content)

        if existing:
            existing.title = title
            existing.slug = slug
            existing.content = content
            existing.content_html = content_html
            existing.meta_description = meta_description
            existing.keywords = keywords
            existing.content_hash = content_hash
            existing.generation_model = generation_model
            existing.generated_at = now
            existing.breadcrumbs = breadcrumbs or existing.breadcrumbs
            existing.version += 1
            existing.updated_at = now
            self.db.add(existing)
            try:
                self.db.commit()
            except IntegrityError:
                self.db.rollback()
                existing.slug = f"{slug}-{uuid4().hex[:8]}"
                self.db.add(existing)
                self.db.commit()
            self.db.refresh(existing)
            logger.info(f"Updated blog post for {jurisdiction_id}, version {existing.version}")

            fields_to_index = {
                "title": existing.title,
                "content": existing.content,
                "meta_description": existing.meta_description,
                "keywords": existing.keywords,
            }

            blog_crud.update_post_tokens(
                db=cast(Session, self.db), post_id=existing.id, fields=fields_to_index
            )
            return existing
        else:
            new_post = JurisdictionBlogPost(
                jurisdiction_id=jurisdiction_id,
                title=title,
                slug=slug,
                content=content,
                content_html=content_html,
                meta_description=meta_description,
                keywords=keywords,
                is_published=False,
                version=1,
                content_hash=content_hash,
                generation_model=generation_model,
                generated_at=now,
                created_at=now,
                updated_at=now,
            )
            self.db.add(new_post)
            try:
                self.db.commit()
            except IntegrityError:
                self.db.rollback()
                new_post.slug = f"{slug}-{uuid4().hex[:8]}"
                self.db.add(new_post)
                self.db.commit()
            self.db.refresh(new_post)
            logger.info(f"Created new blog post for {jurisdiction_id}, version 1")

            fields_to_index = {
                "title": new_post.title,
                "content": new_post.content,
                "meta_description": new_post.meta_description,
                "keywords": new_post.keywords,
            }
            blog_crud.update_post_tokens(
                db=cast(Session, self.db), post_id=new_post.id, fields=fields_to_index
            )

            return new_post

    async def _upsert_blog_post_async(
        self,
        jurisdiction_id: UUID,
        title: str,
        slug: str,
        content: str,
        meta_description: str,
        keywords: list,
        content_hash: str,
        generation_model: Optional[str] = None,
        existing: Optional[JurisdictionBlogPost] = None,
        breadcrumbs: Optional[list[Dict[str, str]]] = None,
    ) -> JurisdictionBlogPost:
        """Create or update blog post asynchronously.

        Converts Markdown content to HTML at write time and stores both
        `content` (markdown source) and `content_html` (rendered body).

        Args:
            jurisdiction_id: Jurisdiction ID.
            title: Blog title.
            slug: URL slug.
            content: Markdown content (source of truth).
            meta_description: SEO description.
            keywords: SEO keywords.
            content_hash: SHA-256 hash of source data.
            generation_model: LLM model used for generation.
            existing: Existing blog post (if any).
            breadcrumbs: Precomputed breadcrumb trail for SEO markup.

        Returns:
            JurisdictionBlogPost: Created or updated post.

        Examples:
            >>> blog = await service._upsert_blog_post_async(...)
        """
        now = datetime.now(timezone.utc)
        content_html = render_html_body(content)

        if existing:
            existing.title = title
            existing.slug = slug
            existing.content = content
            existing.content_html = content_html
            existing.meta_description = meta_description
            existing.keywords = keywords
            existing.content_hash = content_hash
            existing.generation_model = generation_model
            existing.generated_at = now
            existing.breadcrumbs = breadcrumbs or existing.breadcrumbs
            existing.version += 1
            existing.updated_at = now
            self.db.add(existing)
            try:
                await self.db.commit()
            except IntegrityError:
                await self.db.rollback()
                existing.slug = f"{slug}-{uuid4().hex[:8]}"
                self.db.add(existing)
                await self.db.commit()
            await self.db.refresh(existing)
            logger.info(f"Updated blog post for {jurisdiction_id}, version {existing.version}")

            fields_to_index = {
                "title": existing.title,
                "content": existing.content,
                "meta_description": existing.meta_description,
                "keywords": existing.keywords,
            }

            blog_crud.update_post_tokens(
                db=cast(Session, self.db), post_id=existing.id, fields=fields_to_index
            )
            return existing
        else:
            new_post = JurisdictionBlogPost(
                jurisdiction_id=jurisdiction_id,
                title=title,
                slug=slug,
                content=content,
                content_html=content_html,
                meta_description=meta_description,
                keywords=keywords,
                breadcrumbs=breadcrumbs or [],
                is_published=False,
                version=1,
                content_hash=content_hash,
                generation_model=generation_model,
                generated_at=now,
                created_at=now,
                updated_at=now,
            )
            self.db.add(new_post)
            try:
                await self.db.commit()
            except IntegrityError:
                await self.db.rollback()
                new_post.slug = f"{slug}-{uuid4().hex[:8]}"
                self.db.add(new_post)
                await self.db.commit()
            await self.db.refresh(new_post)
            logger.info(f"Created new blog post for {jurisdiction_id}, version 1")

            fields_to_index = {
                "title": new_post.title,
                "content": new_post.content,
                "meta_description": new_post.meta_description,
                "keywords": new_post.keywords,
            }
            blog_crud.update_post_tokens(
                db=cast(Session, self.db), post_id=new_post.id, fields=fields_to_index
            )
            return new_post

    def _generate_placeholder_sync(
        self,
        jurisdiction_id: UUID,
        domain_context: Dict[str, str],
        jurisdiction: Jurisdiction,
    ) -> Dict[str, Any]:
        """Generate placeholder blog post synchronously when no state data exists.

        Args:
            jurisdiction_id: Jurisdiction ID.
            domain_context: Domain context dict.
            jurisdiction: Jurisdiction model instance for breadcrumb computation.

        Returns:
            dict: Generation result with status="placeholder".

        Examples:
            >>> result = service._generate_placeholder_sync(jur_id, context, jurisdiction)
        """
        content = BLOG_PLACEHOLDER_CONTENT.format(**domain_context)
        slug = self._slugify(domain_context["jurisdiction_name"], domain_context["industry"])
        breadcrumbs = self._build_breadcrumbs_sync(jurisdiction, slug)

        existing = self._get_existing_blog_sync(jurisdiction_id)

        blog_post = self._upsert_blog_post_sync(
            jurisdiction_id=jurisdiction_id,
            title=f"{domain_context['jurisdiction_name']} Compliance Guide — Coming Soon",
            slug=slug,
            content=content,
            meta_description=(
                f"Compliance guide for {domain_context['jurisdiction_name']} coming soon."
            ),
            keywords=[
                domain_context["jurisdiction_name"],
                domain_context["industry"],
                "compliance",
            ],
            content_hash="placeholder",
            existing=existing,
            breadcrumbs=breadcrumbs,
        )

        return {
            "status": "placeholder",
            "jurisdiction_id": str(jurisdiction_id),
            "message": "Placeholder blog post created (no state data available)",
            "version": blog_post.version,
        }

    async def _generate_placeholder_async(
        self,
        jurisdiction_id: UUID,
        domain_context: Dict[str, str],
        jurisdiction: Jurisdiction,
    ) -> Dict[str, Any]:
        """Generate placeholder blog post asynchronously when no state data exists.

        Args:
            jurisdiction_id: Jurisdiction ID.
            domain_context: Domain context dict.
            jurisdiction: Jurisdiction model instance for breadcrumb computation.

        Returns:
            dict: Generation result with status="placeholder".

        Examples:
            >>> result = await service._generate_placeholder_async(jur_id, context, jurisdiction)
        """
        content = BLOG_PLACEHOLDER_CONTENT.format(**domain_context)
        slug = self._slugify(domain_context["jurisdiction_name"], domain_context["industry"])
        breadcrumbs = await self._build_breadcrumbs_async(jurisdiction, slug)

        existing = await self._get_existing_blog_async(jurisdiction_id)

        blog_post = await self._upsert_blog_post_async(
            jurisdiction_id=jurisdiction_id,
            title=f"{domain_context['jurisdiction_name']} Compliance Guide — Coming Soon",
            slug=slug,
            content=content,
            meta_description=(
                f"Compliance guide for {domain_context['jurisdiction_name']} coming soon."
            ),
            keywords=[
                domain_context["jurisdiction_name"],
                domain_context["industry"],
                "compliance",
            ],
            content_hash="placeholder",
            existing=existing,
            breadcrumbs=breadcrumbs,
        )

        return {
            "status": "placeholder",
            "jurisdiction_id": str(jurisdiction_id),
            "message": "Placeholder blog post created (no state data available)",
            "version": blog_post.version,
        }

    def _update_job_status_sync(
        self,
        job_id: Optional[UUID],
        status: BlogGenerationJobStatus,
        error_message: Optional[str] = None,
    ) -> None:
        """Update BlogGenerationJob status synchronously.

        No-op if job_id is None (backward compat with callers that don't track jobs).

        Args:
            job_id: BlogGenerationJob ID (None to skip).
            status: New status to set.
            error_message: Error details if status is FAILED.

        Examples:
            >>> service._update_job_status_sync(job_id, BlogGenerationJobStatus.IN_PROGRESS)
        """
        if job_id is None:
            return

        try:
            stmt = select(BlogGenerationJob).where(BlogGenerationJob.id == job_id)
            result = self.db.execute(stmt)
            job = result.scalar_one_or_none()

            if not job:
                logger.warning(f"BlogGenerationJob {job_id} not found for status update")
                return

            now = datetime.now(timezone.utc)
            job.status = status

            if status == BlogGenerationJobStatus.IN_PROGRESS:
                job.started_at = now
            elif status in (
                BlogGenerationJobStatus.COMPLETED,
                BlogGenerationJobStatus.FAILED,
            ):
                job.completed_at = now

            if error_message:
                job.error_message = error_message

            self.db.add(job)
            self.db.commit()
            self.db.refresh(job)
            logger.info(f"Updated BlogGenerationJob {job_id} to {status.value}")
        except Exception as e:
            logger.error(f"Failed to update job {job_id} status: {e}", exc_info=True)
            try:
                self.db.rollback()
            except Exception:
                pass

    async def _update_job_status_async(
        self,
        job_id: Optional[UUID],
        status: BlogGenerationJobStatus,
        error_message: Optional[str] = None,
    ) -> None:
        """Update BlogGenerationJob status asynchronously.

        No-op if job_id is None (backward compat with callers that don't track jobs).

        Args:
            job_id: BlogGenerationJob ID (None to skip).
            status: New status to set.
            error_message: Error details if status is FAILED.

        Examples:
            >>> await service._update_job_status_async(job_id, BlogGenerationJobStatus.COMPLETED)
        """
        if job_id is None:
            return

        try:
            stmt = select(BlogGenerationJob).where(BlogGenerationJob.id == job_id)
            result = await self.db.execute(stmt)
            job = result.scalar_one_or_none()

            if not job:
                logger.warning(f"BlogGenerationJob {job_id} not found for status update")
                return

            now = datetime.now(timezone.utc)
            job.status = status

            if status == BlogGenerationJobStatus.IN_PROGRESS:
                job.started_at = now
            elif status in (
                BlogGenerationJobStatus.COMPLETED,
                BlogGenerationJobStatus.FAILED,
            ):
                job.completed_at = now

            if error_message:
                job.error_message = error_message

            self.db.add(job)
            await self.db.commit()
            await self.db.refresh(job)
            logger.info(f"Updated BlogGenerationJob {job_id} to {status.value}")
        except Exception as e:
            logger.error(f"Failed to update job {job_id} status: {e}", exc_info=True)
            try:
                await self.db.rollback()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Static route-handler methods (called from blog_routes.py)
    # ------------------------------------------------------------------

    @staticmethod
    async def _get_jurisdiction(
        db: AsyncSession, organization_id: UUID, jurisdiction_id: UUID
    ) -> Jurisdiction:
        """Validate and return a jurisdiction belonging to an organization.

        Raises ResourceNotFoundError if not found.
        """
        stmt = (
            select(Jurisdiction)
            .join(Project, Jurisdiction.project_id == Project.id)
            .where(
                Jurisdiction.id == jurisdiction_id,
                Project.org_id == organization_id,
            )
        )
        result = await db.execute(stmt)
        jurisdiction = result.scalar_one_or_none()

        if not jurisdiction:
            raise ResourceNotFoundError("Jurisdiction not found in this organization")

        return jurisdiction

    @staticmethod
    async def get_blog_post(db: AsyncSession, organization_id: UUID, jurisdiction_id: UUID) -> dict:
        """Retrieve the blog post for a jurisdiction.

        Returns dict with status_code, message, data.
        Raises ResourceNotFoundError when jurisdiction or blog post missing.
        """
        try:
            jurisdiction = await BlogGenerationService._get_jurisdiction(
                db,
                organization_id,
                jurisdiction_id,
            )

            stmt = select(JurisdictionBlogPost).where(
                JurisdictionBlogPost.jurisdiction_id == jurisdiction_id
            )
            result = await db.execute(stmt)
            blog_post = result.scalar_one_or_none()

            if not blog_post:
                raise ResourceNotFoundError("Blog post not found for this jurisdiction")

            payload = BlogPostResponse.model_validate(blog_post).model_dump()
            if blog_post.is_published:
                resource_path = await BlogGenerationService._build_public_resource_path(
                    db,
                    jurisdiction,
                    blog_post,
                )
                payload["resource_path"] = resource_path
                payload["public_url"] = BlogGenerationService._build_public_resource_url(
                    resource_path
                )
            else:
                payload["resource_path"] = None
                payload["public_url"] = None

            return {
                "status_code": http_status.HTTP_200_OK,
                "message": "Blog post retrieved successfully",
                "data": payload,
            }
        except ResourceNotFoundError:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.info("Failed to retrieve blog post: %s", e)
            raise ProcessingError("An unexpected error occurred while retrieving the blog post")

    @staticmethod
    async def trigger_generation(
        db: AsyncSession, organization_id: UUID, jurisdiction_id: UUID
    ) -> dict:
        """Create a BlogGenerationJob and return job info.

        Returns dict with status_code, message, data (including _job for background dispatch).
        Raises ResourceNotFoundError, BlogGenerationInProgressError.
        """
        try:
            await BlogGenerationService._get_jurisdiction(
                db,
                organization_id,
                jurisdiction_id,
            )

            job = BlogGenerationJob(
                jurisdiction_id=jurisdiction_id,
                status=BlogGenerationJobStatus.PENDING,
            )
            db.add(job)
            await db.commit()
            await db.refresh(job)

            return {
                "status_code": http_status.HTTP_202_ACCEPTED,
                "message": "Blog generation triggered. Check back in a few moments.",
                "data": {
                    "job_id": str(job.id),
                    "jurisdiction_id": str(jurisdiction_id),
                    "status": job.status.value,
                    "message": "Blog generation job queued successfully",
                },
                "_job": job,
            }
        except ResourceNotFoundError:
            await db.rollback()
            raise
        except IntegrityError:
            await db.rollback()
            raise BlogGenerationInProgressError()
        except Exception as e:
            await db.rollback()
            logger.info("Failed to trigger blog generation: %s", e)
            raise ProcessingError("An unexpected error occurred while triggering blog generation")

    @staticmethod
    async def get_generation_status(
        db: AsyncSession, organization_id: UUID, jurisdiction_id: UUID, job_id: UUID
    ) -> dict:
        """Get the status of a specific blog generation job.

        Returns dict with status_code, message, data.
        Raises ResourceNotFoundError when jurisdiction or job missing.
        """
        try:
            await BlogGenerationService._get_jurisdiction(db, organization_id, jurisdiction_id)

            stmt = select(BlogGenerationJob).where(
                BlogGenerationJob.id == job_id,
                BlogGenerationJob.jurisdiction_id == jurisdiction_id,
            )
            result = await db.execute(stmt)
            job = result.scalar_one_or_none()

            if not job:
                raise ResourceNotFoundError("Blog generation job not found")

            return {
                "status_code": http_status.HTTP_200_OK,
                "message": "Blog generation job status retrieved successfully",
                "data": BlogGenerationJobResponse.model_validate(job).model_dump(mode="json"),
            }
        except ResourceNotFoundError:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.info("Failed to retrieve generation status: %s", e)
            raise ProcessingError("An unexpected error occurred while retrieving job status")

    @staticmethod
    async def list_generation_jobs(
        db: AsyncSession,
        organization_id: UUID,
        jurisdiction_id: UUID,
        page: int,
        limit: int,
    ) -> dict:
        """List blog generation jobs for a jurisdiction with pagination.

        Returns dict with status_code, message, data containing items and pagination.
        Raises ResourceNotFoundError when jurisdiction missing.
        """
        try:
            await BlogGenerationService._get_jurisdiction(db, organization_id, jurisdiction_id)

            count_query = (
                select(func.count())
                .select_from(BlogGenerationJob)
                .where(BlogGenerationJob.jurisdiction_id == jurisdiction_id)
            )
            count_result = await db.execute(count_query)
            total = count_result.scalar() or 0

            jobs_query = (
                select(BlogGenerationJob)
                .where(BlogGenerationJob.jurisdiction_id == jurisdiction_id)
                .order_by(BlogGenerationJob.created_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            )
            jobs_result = await db.execute(jobs_query)
            jobs = jobs_result.scalars().all()

            jobs_data = [
                BlogGenerationJobResponse.model_validate(job).model_dump(mode="json")
                for job in jobs
            ]
            pagination = calculate_pagination(total, page, limit)

            return {
                "status_code": http_status.HTTP_200_OK,
                "message": "Blog generation jobs retrieved successfully",
                "data": {"items": jobs_data, "pagination": pagination},
            }
        except ResourceNotFoundError:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.info("Failed to retrieve generation jobs: %s", e)
            raise ProcessingError("An unexpected error occurred while retrieving generation jobs")

    @staticmethod
    async def get_bulk_generation_status(
        db: AsyncSession, project_id: UUID, bulk_job_id: UUID
    ) -> dict:
        """Get the status of a specific project-level bulk blog generation job.

        Fetches the parent job and aggregates the latest statuses of individual
        jurisdiction jobs associated with this project.
        """
        from app.api.modules.v1.jurisdictions.schemas.blog_schema import (
            ProjectBulkBlogJobItemResponse,
            ProjectBulkBlogJobResponse,
        )

        try:
            # 1. Fetch parent job
            stmt = select(ProjectBulkBlogJob).where(
                ProjectBulkBlogJob.id == bulk_job_id,
                ProjectBulkBlogJob.project_id == project_id,
            )
            result = await db.execute(stmt)
            job = result.scalar_one_or_none()

            if not job:
                raise ResourceNotFoundError("Bulk blog generation job not found")

            # 2. Convert to dict for response merging
            job_data = ProjectBulkBlogJobResponse.model_validate(job).model_dump(mode="json")

            # 3. If the job is active or recently finished, we can fetch individual items
            # In a real heavy-load scenario, we might paginate items,
            # but for 50-100 jurisdictions it's fine.
            jur_stmt = select(Jurisdiction).where(Jurisdiction.project_id == project_id)
            jur_res = await db.execute(jur_stmt)
            jurisdictions = jur_res.scalars().all()

            # Fetch latest individual blog jobs for these jurisdictions
            items = []

            # This is a broad stroke: we fetch the latest blog gen jobs
            # for the project's jurisdictions
            # Alternatively, we could link BlogGenerationJob to bulk_job_id explicitly.
            # Assuming we added `bulk_job_id` to BlogGenerationJob earlier:

            item_stmt = select(BlogGenerationJob).where(
                BlogGenerationJob.bulk_job_id == bulk_job_id
            )
            item_res = await db.execute(item_stmt)
            item_jobs = item_res.scalars().all()

            # Mapping jurisdiction_id to latest job status
            job_map = {j.jurisdiction_id: j for j in item_jobs}

            for jur in jurisdictions:
                status = "PENDING"
                msg = "Waiting to process"
                if jur.id in job_map:
                    ijob = job_map[jur.id]
                    status = ijob.status.value
                    msg = ijob.error_message or "Processed"

                # Fetch public URL if published
                public_url = None
                if job.status in (
                    ProjectBulkBlogJobStatus.COMPLETED,
                    ProjectBulkBlogJobStatus.COMPLETED_WITH_ERRORS,
                ):
                    post_stmt = select(JurisdictionBlogPost).where(
                        JurisdictionBlogPost.jurisdiction_id == jur.id,
                        JurisdictionBlogPost.is_published.is_(True),
                    )
                    post_res = await db.execute(post_stmt)
                    post = post_res.scalar_one_or_none()
                    if post:
                        # Reconstruct public URL
                        resource_path = await BlogGenerationService._build_public_resource_path(
                            db, jur, post
                        )
                        public_url = BlogGenerationService._build_public_resource_url(resource_path)

                items.append(
                    ProjectBulkBlogJobItemResponse(
                        jurisdiction_id=jur.id, status=status, message=msg, public_url=public_url
                    ).model_dump(mode="json")
                )

            job_data["items"] = items

            return {
                "status_code": http_status.HTTP_200_OK,
                "message": "Bulk blog generation status retrieved",
                "data": job_data,
            }
        except ResourceNotFoundError:
            raise
        except Exception as e:
            logger.info("Failed to retrieve bulk generation status: %s", e)
            raise ProcessingError("An unexpected error occurred while retrieving bulk job status")

    @staticmethod
    async def list_bulk_generation_jobs(
        db: AsyncSession,
        project_id: UUID,
        page: int,
        limit: int,
    ) -> dict:
        """List bulk blog generation jobs for a project with pagination."""
        from app.api.modules.v1.jurisdictions.schemas.blog_schema import ProjectBulkBlogJobResponse

        try:
            count_query = (
                select(func.count())
                .select_from(ProjectBulkBlogJob)
                .where(ProjectBulkBlogJob.project_id == project_id)
            )
            count_result = await db.execute(count_query)
            total = count_result.scalar() or 0

            jobs_query = (
                select(ProjectBulkBlogJob)
                .where(ProjectBulkBlogJob.project_id == project_id)
                .order_by(ProjectBulkBlogJob.created_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            )
            jobs_result = await db.execute(jobs_query)
            jobs = jobs_result.scalars().all()

            jobs_data = [
                ProjectBulkBlogJobResponse.model_validate(job).model_dump(mode="json")
                for job in jobs
            ]

            # Exclude items array for list view to save bandwidth
            for data in jobs_data:
                data.pop("items", None)

            pagination = calculate_pagination(total, page, limit)

            return {
                "status_code": http_status.HTTP_200_OK,
                "message": "Bulk blog generation jobs retrieved successfully",
                "data": {"items": jobs_data, "pagination": pagination},
            }
        except Exception as e:
            logger.info("Failed to retrieve bulk generation jobs: %s", e)
            raise ProcessingError(
                "An unexpected error occurred while retrieving bulk generation jobs"
            )

    async def publish_blog_post(
        db: AsyncSession,
        organization_id: UUID,
        jurisdiction_id: UUID,
        is_published: bool,
    ) -> dict:
        """Publish or unpublish a blog post.

        Returns dict with status_code, message, data.
        Raises ResourceNotFoundError when jurisdiction or blog post missing.
        """
        try:
            jurisdiction = await BlogGenerationService._get_jurisdiction(
                db,
                organization_id,
                jurisdiction_id,
            )

            stmt = select(JurisdictionBlogPost).where(
                JurisdictionBlogPost.jurisdiction_id == jurisdiction_id
            )
            result = await db.execute(stmt)
            blog_post = result.scalar_one_or_none()

            if not blog_post:
                raise ResourceNotFoundError("Blog post not found for this jurisdiction")

            blog_post.is_published = is_published
            if is_published and not blog_post.published_at:
                blog_post.published_at = datetime.now(timezone.utc)
            elif not is_published:
                blog_post.published_at = None

            blog_post.updated_at = datetime.now(timezone.utc)

            db.add(blog_post)
            await db.commit()
            await db.refresh(blog_post)

            resource_path = await BlogGenerationService._build_public_resource_path(
                db,
                jurisdiction,
                blog_post,
            )
            public_url = BlogGenerationService._build_public_resource_url(resource_path)

            # Write or remove the static HTML artifact on the server
            import asyncio

            if is_published:
                await asyncio.to_thread(write_artifact, blog_post, resource_path)
            else:
                await asyncio.to_thread(delete_artifact, resource_path, blog_post.slug)

            message = (
                "Blog post published successfully"
                if is_published
                else "Blog post unpublished successfully"
            )

            return {
                "status_code": http_status.HTTP_200_OK,
                "message": message,
                "data": {
                    "id": str(blog_post.id),
                    "jurisdiction_id": str(blog_post.jurisdiction_id),
                    "title": blog_post.title,
                    "slug": blog_post.slug,
                    "is_published": blog_post.is_published,
                    "public_url": public_url if blog_post.is_published else None,
                    "published_at": (
                        blog_post.published_at.isoformat() if blog_post.published_at else None
                    ),
                },
            }
        except ResourceNotFoundError:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.info("Failed to publish/unpublish blog post: %s", e)
            raise ProcessingError("An unexpected error occurred while updating the blog post")
