"""
Service layer for Source CRUD operations.

Handles all business logic for source management including:
- CRUD operations for sources
- Encryption/decryption of auth details
- Validation and error handling
- Database transactions
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from app.api.core.custom_exceptions.exceptions import (
    BadRequestError,
    NotFoundError,
    ProcessingError,
)
from app.api.core.security import encrypt_auth_details
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.scraping.schemas.source_service import (
    SourceCreate,
    SourceRead,
    SourceUpdate,
)
from app.api.modules.v1.scraping.validators import URLValidationError, URLValidator
from app.api.modules.v1.scraping.validators.exception import (
    DuplicateSourceError,
    SourceNotFoundError,
)

logger = logging.getLogger("app")


class SourceService:
    """
    Business logic for Source entity operations.

    Provides centralized handling of:
    - Source creation with encrypted auth details
    - Source retrieval (single and list)
    - Source updates
    - Source deletion
    - Secure credential management
    """

    async def create_source(
        self,
        db: AsyncSession,
        source_data: SourceCreate,
        strict_validation: bool = True,
        auto_commit: bool = True,
    ) -> SourceRead:
        """Create a new source with encrypted auth details.

        Args:
            db: Database session.
            source_data: Source creation data.
            strict_validation: If True (manual mode), requires verified URLs.
                             If False (batch/campaign mode), allows unverified
                             sources with retryable status.
            auto_commit: If True, commits the transaction within this method.
                         If False, flushes only and lets the caller manage commit.

        Returns:
            SourceRead: The created source with sanitized fields.

        Raises:
            HTTPException: 400 if required prompts are missing or URL already exists.
            HTTPException: 422 if URL is invalid (format/domain issues).
            HTTPException: 500 if creation fails.

        Examples:
            >>> service = SourceService()
            >>> # Strict mode (manual creation)
            >>> source = await service.create_source(db, source_data, strict_validation=True)
            >>> # Batch mode (campaign discovery)
            >>> source = await service.create_source(db, source_data, strict_validation=False)
        """
        try:
            # Format and domain validation (ALWAYS strict)
            is_valid, error_msg, error_code = URLValidator.validate_url_format(str(source_data.url))
            if not is_valid:
                logger.warning(f"URL format validation failed for {source_data.url}: {error_msg}")
                raise URLValidationError(error_msg, error_code)

            is_valid, error_msg, error_code = URLValidator.validate_domain(str(source_data.url))
            if not is_valid:
                logger.warning(f"URL domain validation failed for {source_data.url}: {error_msg}")
                raise URLValidationError(error_msg, error_code)

            # Reachability validation (conditional based on mode)
            verification_status = "unverified_retryable"
            if strict_validation:
                # Manual mode: Require verification
                is_reachable, error_msg, error_code = await URLValidator.check_url_reachability(
                    str(source_data.url)
                )
                if not is_reachable:
                    logger.warning(
                        f"URL reachability check failed for {source_data.url}: {error_msg}"
                    )
                    raise URLValidationError(error_msg, error_code)
                verification_status = "verified"
            else:
                # Batch mode: Verify but allow retryable failures
                from app.api.modules.v1.scraping.service.source_verification_service import (
                    SourceVerificationService,
                    VerificationStatus,
                )

                result = await SourceVerificationService._verify_single(str(source_data.url))
                verification_status = result.status

                # Only block on permanent failures
                if result.status == VerificationStatus.UNVERIFIED_PERMANENT:
                    logger.warning(
                        f"Permanent verification failure for {source_data.url}: "
                        f"{result.error_message}"
                    )
                    raise URLValidationError(
                        result.user_message or "URL appears invalid",
                        "INVALID_URL",
                    )

                # Log retryable failures but continue
                if result.status != VerificationStatus.VERIFIED:
                    logger.info(
                        f"Source {source_data.url} could not be verified "
                        f"({result.status}), but will be created for later retry: "
                        f"{result.error_message}"
                    )

            await self._ensure_prompt_requirements(db, source_data.jurisdiction_id)
            existing_source = await db.scalar(
                select(Source).where(
                    Source.url == str(source_data.url),
                    Source.jurisdiction_id == source_data.jurisdiction_id,
                    ~Source.is_deleted,
                )
            )
            if existing_source:
                raise DuplicateSourceError(
                    "Source with this URL already exists in the jurisdiction",
                )

            encrypted_auth = None
            if source_data.auth_details:
                encrypted_auth = encrypt_auth_details(source_data.auth_details)
                logger.info(f"Encrypted auth details for source: {source_data.name}")

            db_source = Source(
                jurisdiction_id=source_data.jurisdiction_id,
                name=source_data.name,
                url=str(source_data.url),
                source_type=source_data.source_type,
                scrape_frequency=source_data.scrape_frequency,
                scraping_rules=source_data.scraping_rules or {},
                auth_details_encrypted=encrypted_auth,
                verification_status=verification_status,
                verification_attempts=0 if strict_validation else 1,
            )

            db.add(db_source)
            if auto_commit:
                await db.commit()
            else:
                await db.flush()
            await db.refresh(db_source)

            logger.info(f"Successfully created source: {db_source.id} - {db_source.name}")

            return self._to_read_schema(db_source)

        except (URLValidationError, DuplicateSourceError, NotFoundError, BadRequestError):
            if auto_commit:
                await db.rollback()
            raise
        except Exception as e:
            if auto_commit:
                await db.rollback()
            logger.error(f"Failed to create source: {str(e)}", exc_info=True)
            raise ProcessingError(
                "We're unable to create the data source at this time. "
                "Please try again later or contact support."
            )

    async def bulk_create_sources(
        self,
        db: AsyncSession,
        sources_data: List["SourceCreate"],
    ) -> List[SourceRead]:
        """
        Create multiple sources in a single transaction.

        Args:
            db (AsyncSession): Database session.
            sources_data (List[SourceCreate]): List of source creation data.

        Returns:
            List[SourceRead]: List of created sources with sanitized fields.

        Raises:
            HTTPException: 400 if required prompts are missing or URLs already exist.
            HTTPException: 422 if any URL is unreachable or invalid.
            HTTPException: 500 if creation fails.

        Examples:
            >>> sources = await service.bulk_create_sources(db, sources_data)
            >>> print(f"Created {len(sources)} sources")
            Created 3 sources
        """
        if not sources_data:
            return []

        try:
            for idx, source_data in enumerate(sources_data):
                try:
                    await URLValidator.validate_url_comprehensive(
                        source_data.url,
                        check_reachability=True,
                    )
                except URLValidationError as e:
                    logger.warning(
                        f"URL validation failed for source #{idx + 1} "
                        f"({source_data.url}): {e.message}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"URL validation failed for source #{idx + 1}: {e.message}",
                    )

            unique_jurisdiction_ids = {source.jurisdiction_id for source in sources_data}
            for jurisdiction_id in unique_jurisdiction_ids:
                await self._ensure_prompt_requirements(db, jurisdiction_id)
            created_sources = []
            urls_to_check = [str(source.url) for source in sources_data]

            existing_sources = await db.execute(
                select(Source.url).where(
                    Source.url.in_(urls_to_check),
                    Source.jurisdiction_id.in_(unique_jurisdiction_ids),
                    ~Source.is_deleted,
                )
            )
            existing_urls = set(existing_sources.scalars().all())

            duplicates = [url for url in urls_to_check if url in existing_urls]
            if duplicates:
                raise DuplicateSourceError(field_errors={"url": duplicates})

            for source_data in sources_data:
                encrypted_auth = None
                if source_data.auth_details:
                    encrypted_auth = encrypt_auth_details(source_data.auth_details)
                    logger.info(f"Encrypted auth details for source: {source_data.name}")

                db_source = Source(
                    jurisdiction_id=source_data.jurisdiction_id,
                    name=source_data.name,
                    url=str(source_data.url),
                    source_type=source_data.source_type,
                    scrape_frequency=source_data.scrape_frequency,
                    scraping_rules=source_data.scraping_rules or {},
                    auth_details_encrypted=encrypted_auth,
                )

                db.add(db_source)
                created_sources.append(db_source)

            await db.commit()

            for source in created_sources:
                await db.refresh(source)

            logger.info(f"Successfully created {len(created_sources)} sources in bulk")

            return [self._to_read_schema(source) for source in created_sources]

        except (DuplicateSourceError, URLValidationError):
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to bulk create sources: {str(e)}", exc_info=True)
            raise ProcessingError("Failed to create sources")

    async def get_source(
        self,
        db: AsyncSession,
        source_id: uuid.UUID,
        include_deleted: bool = True,
    ) -> SourceRead:
        """
        Retrieve a single source by ID.

        Args:
            db (AsyncSession): Database session.
            source_id (uuid.UUID): The source UUID.
            include_deleted (bool): If True, include soft-deleted sources.
                Default is True (for recovery).

        Returns:
            SourceRead: The source with sanitized fields.

        Raises:
            HTTPException: If source not found (404).

        Examples:
            >>> source = await service.get_source(db, source_id)
            >>> print(source.has_auth)
            True
        """
        try:
            source = await db.get(Source, source_id)

            if not source:
                logger.warning(f"Source not found: {source_id}")
                raise SourceNotFoundError("Source not found")

            if source.is_deleted and not include_deleted:
                logger.warning(f"Source is deleted and cannot be accessed: {source_id}")
                raise SourceNotFoundError("Source not found")

            logger.info(f"Retrieved source: {source_id}")
            return self._to_read_schema(source)
        except SourceNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to retrieve source: {str(e)}", exc_info=True)
            raise ProcessingError("An unexpected error occurred, unable to retrieve source")

    async def get_sources(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        jurisdiction_id: Optional[uuid.UUID] = None,
        is_active: Optional[bool] = None,
        include_deleted: bool = False,
        is_deleted: Optional[bool] = None,
    ) -> List[SourceRead]:
        """
        Retrieve a list of sources with optional filtering.

        Args:
            db (AsyncSession): Database session.
            skip (int): Number of records to skip (pagination).
            limit (int): Maximum number of records to return.
            jurisdiction_id (Optional[uuid.UUID]): Filter by jurisdiction.
            is_active (Optional[bool]): Filter by active status.
            include_deleted (bool): If True, include soft-deleted sources. Default is False.

        Returns:
            List[SourceRead]: List of sources with sanitized fields.

        Examples:
            >>> sources = await service.get_sources(db, jurisdiction_id=juris_id)
            >>> len(sources)
            5
        """
        try:
            query = select(Source)

            if jurisdiction_id:
                query = query.where(Source.jurisdiction_id == jurisdiction_id)
            if is_active is not None:
                query = query.where(Source.is_active == is_active)

            if is_deleted is not None:
                query = query.where(Source.is_deleted == is_deleted)

            elif not include_deleted:
                query = query.where(~Source.is_deleted)

            query = query.offset(skip).limit(limit)

            result = await db.execute(query)
            sources = result.scalars().all()

            if not sources:
                logger.warning(f"Sources not found for jurisdiction: {jurisdiction_id}")
                return []

            logger.info(f"Retrieved {len(sources)} sources")
            return [self._to_read_schema(source) for source in sources]
        except Exception as e:
            logger.error(
                f"Failed to retrieve sources for {jurisdiction_id}, {str(e)}", exc_info=True
            )
            raise ProcessingError("An unexpected error occurred, unable to retrieve sources")

    async def update_source(
        self,
        db: AsyncSession,
        source_id: uuid.UUID,
        source_data: SourceUpdate,
    ) -> SourceRead:
        """
        Update an existing source.

        Args:
            db (AsyncSession): Database session.
            source_id (uuid.UUID): The source UUID to update.
            source_data (SourceUpdate): Updated source data (partial allowed).

        Returns:
            SourceRead: The updated source with sanitized fields.

        Raises:
            HTTPException: If source not found (404) or update fails.

        Examples:
            >>> updated = await service.update_source(db, source_id, update_data)
            >>> print(updated.scrape_frequency)
        """
        source = await db.get(Source, source_id)

        if not source:
            logger.warning(f"Cannot update - source not found: {source_id}")
            raise SourceNotFoundError("Source not found")

        logger.debug(f"Updating source {source_id}, is_deleted={source.is_deleted}")

        try:
            update_data = source_data.model_dump(exclude_unset=True)

            if "auth_details" in update_data:
                auth_details = update_data.pop("auth_details")
                if auth_details:
                    source.auth_details_encrypted = encrypt_auth_details(auth_details)
                    logger.info(f"Updated encrypted auth for source: {source_id}")
                else:
                    source.auth_details_encrypted = None

            for field, value in update_data.items():
                if field == "url" and value:
                    value = str(value)
                setattr(source, field, value)

            await db.commit()
            await db.refresh(source)

            logger.info(f"Successfully updated source: {source_id}")
            return self._to_read_schema(source)

        except SourceNotFoundError:
            await db.rollback()
            raise

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to update source {source_id}: {str(e)}", exc_info=True)
            raise ProcessingError("Failed to update source")

    async def delete_source(
        self,
        db: AsyncSession,
        source_id: uuid.UUID,
        permanent: bool = False,
    ) -> Dict[str, Any]:
        """
        Delete a source by ID (soft delete by default, hard delete if permanent=True).

        Args:
            db (AsyncSession): Database session.
            source_id (uuid.UUID): The source UUID to delete.
            permanent (bool): If True, perform hard delete; otherwise soft delete.

        Returns:
            Dict[str, Any]: Confirmation message.

        Raises:
            HTTPException: If source not found (404) or deletion fails.

        Examples:
            >>> result = await service.delete_source(db, source_id)
            >>> print(result["message"])
            'Source successfully deleted'
            >>> result = await service.delete_source(db, source_id, permanent=True)
            >>> print(result["message"])
            'Source permanently deleted'
        """
        source = await db.get(Source, source_id)

        if not source:
            logger.warning(f"Cannot delete - source not found: {source_id}")
            raise SourceNotFoundError(
                "Source not found",
            )

        try:
            if permanent:
                await db.delete(source)
                await db.commit()
                logger.info(f"Permanently deleted source: {source_id}")
                return {
                    "message": "Source permanently deleted",
                    "source_id": str(source_id),
                }
            else:
                source.is_deleted = True
                await db.commit()
                await db.refresh(source)
                logger.info(f"Soft deleted source: {source_id}")
                return {
                    "message": "Source successfully deleted",
                    "source_id": str(source_id),
                }

        except SourceNotFoundError:
            await db.rollback()
            raise

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to delete source {source_id}: {str(e)}", exc_info=True)
            raise ProcessingError(
                "Failed to delete source",
            )

    async def get_source_revisions(
        self,
        db: AsyncSession,
        source_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[List[DataRevision], int]:
        """
        Retrieve revision history for a specific source.

        Fetches all data revisions associated with a source, ordered by most recent first.
        Supports pagination for large revision histories.

        Args:
            db (AsyncSession): Database session.
            source_id (uuid.UUID): The source UUID to get revisions for.
            skip (int): Number of records to skip (pagination). Default: 0.
            limit (int): Maximum number of records to return. Default: 50.

        Returns:
            tuple: (List[DataRevision], int) - List of revisions and total count.

        Raises:
            HTTPException: 404 if source not found.

        Examples:
            >>> revisions, total = await service.get_source_revisions(db, source_id)
            >>> print(f"Found {total} revisions, showing {len(revisions)}")
            Found 150 revisions, showing 50
        """

        try:
            source = await db.get(Source, source_id)
            if not source:
                logger.warning(f"Cannot fetch revisions - source not found: {source_id}")
                raise SourceNotFoundError("Source not found")

            query = (
                select(DataRevision)
                .where(DataRevision.source_id == source_id)
                .order_by(DataRevision.scraped_at.desc())
                .offset(skip)
                .limit(limit)
            )

            result = await db.execute(query)
            revisions = result.scalars().all()

            count_query = select(func.count()).where(DataRevision.source_id == source_id)
            count_result = await db.execute(count_query)
            total = count_result.scalar_one()

            logger.info(
                f"Retrieved {len(revisions)} revisions for source {source_id} (total: {{total}})"
            )
            return revisions, total
        except SourceNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to retrieve revisions for {source_id} : {str(e)}")
            ProcessingError("An unexpected error occurred. Revisions not retrieved")

    def _to_read_schema(self, source: Source) -> SourceRead:
        """
        Convert a Source model to SourceRead schema.

        Ensures auth details are never exposed in responses.

        Args:
            source (Source): Source database model.

        Returns:
            SourceRead: Sanitized source response schema.
        """
        return SourceRead(
            id=source.id,
            jurisdiction_id=source.jurisdiction_id,
            name=source.name,
            url=source.url,
            source_type=source.source_type,
            scrape_frequency=source.scrape_frequency,
            is_active=source.is_active,
            is_deleted=source.is_deleted,
            auto_create_tickets=source.auto_create_tickets,
            has_auth=bool(source.auth_details_encrypted),
            created_at=source.created_at,
        )

    async def _ensure_prompt_requirements(
        self,
        db: AsyncSession,
        jurisdiction_id: uuid.UUID,
    ) -> None:
        """Validate that jurisdiction prompt exists before source creation.

        Args:
            db (AsyncSession): Async database session used for lookups.
            jurisdiction_id (uuid.UUID): Jurisdiction identifier associated with the source.

        Returns:
            None

        Raises:
            HTTPException: 404 if jurisdiction or project cannot be located.
            HTTPException: 400 if jurisdiction prompt is missing.

        Examples:
            >>> service = SourceService()
            >>> await service._ensure_prompt_requirements(db, jurisdiction_id)
            >>> # Continues without raising when jurisdiction prompt is available
        """

        jurisdiction = await db.get(Jurisdiction, jurisdiction_id)
        if not jurisdiction or jurisdiction.is_deleted:
            raise NotFoundError(
                "Jurisdiction not found",
            )

        project = await db.get(Project, jurisdiction.project_id)
        if not project or project.is_deleted:
            raise NotFoundError("Project not found for jurisdiction")

        jurisdiction_prompt = (jurisdiction.prompt or "").strip()

        if not jurisdiction_prompt:
            raise BadRequestError(
                "Add jurisdiction prompt before adding sources. "
                "These instructions guide the AI scraping pipeline."
            )
