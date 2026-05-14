import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.api.core.dependencies.api_key_auth import api_key_has_scope, get_api_key_from_header
from app.api.db.database import get_db
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.utils.response_payloads import success_response

from .docs.external_extracted_data_route_docs import (
    download_jurisdiction_extracted_data_custom_errors,
    download_jurisdiction_extracted_data_custom_success,
    download_jurisdiction_extracted_data_responses,
    download_project_extracted_data_custom_errors,
    download_project_extracted_data_custom_success,
    download_project_extracted_data_responses,
    download_source_extracted_data_custom_errors,
    download_source_extracted_data_custom_success,
    download_source_extracted_data_responses,
    get_jurisdiction_extracted_data_custom_errors,
    get_jurisdiction_extracted_data_custom_success,
    get_jurisdiction_extracted_data_responses,
    get_project_extracted_data_custom_errors,
    get_project_extracted_data_custom_success,
    get_project_extracted_data_responses,
    get_source_extracted_data_custom_errors,
    get_source_extracted_data_custom_success,
    get_source_extracted_data_responses,
    list_jurisdictions_custom_errors,
    list_jurisdictions_custom_success,
    list_jurisdictions_responses,
    list_projects_custom_errors,
    list_projects_custom_success,
    list_projects_responses,
    list_sources_custom_errors,
    list_sources_custom_success,
    list_sources_responses,
)

router = APIRouter(prefix="/external", tags=["External Extracted Data"])


@router.get(
    "/sources",
    status_code=status.HTTP_200_OK,
    responses=list_sources_responses,
)
async def list_sources(
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=500),
    name: Optional[str] = Query(None, description="Optional name filter"),
    slug: Optional[str] = Query(None, description="Optional slug filter"),
    api_key=Depends(get_api_key_from_header),
    db: AsyncSession = Depends(get_db),
):
    """
    List sources visible to the API key.

    Returns a paginated list of sources (id, name, slug, jurisdiction_id). If the
    API key is scoped to an organization, results are restricted to that organization.
    """
    required_scope = "read:source"
    if not api_key_has_scope(api_key, required_scope):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient scope")

    stmt = select(Source)
    if name:
        stmt = stmt.where(Source.name.ilike(f"%{name}%"))
    if slug:
        stmt = stmt.where(getattr(Source, "slug", None) == slug)

    if getattr(api_key, "organization_id", None):
        stmt = (
            stmt.join(Jurisdiction, Source.jurisdiction_id == Jurisdiction.id)
            .join(Project, Jurisdiction.project_id == Project.id)
            .where(Project.org_id == getattr(api_key, "organization_id"))
        )

    stmt = stmt.offset(skip).limit(limit)
    res = await db.execute(stmt)
    items = [
        {
            "id": str(s.id),
            "name": s.name,
            "slug": getattr(s, "slug", None),
            "jurisdiction_id": str(s.jurisdiction_id) if s.jurisdiction_id else None,
        }
        for s in res.scalars().all()
    ]

    return success_response(
        status_code=status.HTTP_200_OK, message="Sources listed", data={"items": items}
    )


list_sources._custom_errors = list_sources_custom_errors
list_sources._custom_success = list_sources_custom_success


@router.get(
    "/jurisdictions",
    status_code=status.HTTP_200_OK,
    responses=list_jurisdictions_responses,
)
async def list_jurisdictions(
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=500),
    name: Optional[str] = Query(None, description="Optional name filter"),
    api_key=Depends(get_api_key_from_header),
    db: AsyncSession = Depends(get_db),
):
    """
    List jurisdictions visible to the API key.

    Returns a paginated list of jurisdictions (id, name, project_id). If the API
    key is org-scoped, results are restricted to that organization.
    """
    required_scope = "read:jurisdiction"
    if not api_key_has_scope(api_key, required_scope):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient scope")

    from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
    from app.api.modules.v1.projects.models.project_model import Project

    stmt = select(Jurisdiction)
    if name:
        stmt = stmt.where(Jurisdiction.name.ilike(f"%{name}%"))

    if getattr(api_key, "organization_id", None):
        stmt = stmt.join(Project, Jurisdiction.project_id == Project.id).where(
            Project.org_id == getattr(api_key, "organization_id")
        )

    stmt = stmt.offset(skip).limit(limit)
    res = await db.execute(stmt)
    items = [
        {"id": str(j.id), "name": j.name, "project_id": str(j.project_id)}
        for j in res.scalars().all()
    ]

    return success_response(
        status_code=status.HTTP_200_OK, message="Jurisdictions listed", data={"items": items}
    )


list_jurisdictions._custom_errors = list_jurisdictions_custom_errors
list_jurisdictions._custom_success = list_jurisdictions_custom_success


@router.get(
    "/projects",
    status_code=status.HTTP_200_OK,
    responses=list_projects_responses,
)
async def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=500),
    name: Optional[str] = Query(None, description="Optional name filter"),
    api_key=Depends(get_api_key_from_header),
    db: AsyncSession = Depends(get_db),
):
    """
    List projects visible to the API key.

    Returns a paginated list of projects (id, title, org_id). If the API key is
    org-scoped, returns only projects for that org.
    """
    required_scope = "read:project"
    if not api_key_has_scope(api_key, required_scope):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient scope")

    from app.api.modules.v1.projects.models.project_model import Project

    stmt = select(Project)
    if name:
        stmt = stmt.where(Project.title.ilike(f"%{name}%"))

    if getattr(api_key, "organization_id", None):
        stmt = stmt.where(Project.org_id == getattr(api_key, "organization_id"))

    stmt = stmt.offset(skip).limit(limit)
    res = await db.execute(stmt)
    items = [
        {"id": str(p.id), "title": p.title, "org_id": str(p.org_id)} for p in res.scalars().all()
    ]

    return success_response(
        status_code=status.HTTP_200_OK, message="Projects listed", data={"items": items}
    )


def _iter_json_bytes(revisions):
    """Helper generator to stream JSON for download responses."""
    yield b"["
    first = True
    for r in revisions:
        if not first:
            yield b","
        else:
            first = False
        yield json.dumps(r).encode("utf-8")
    yield b"]"


list_projects._custom_errors = list_projects_custom_errors
list_projects._custom_success = list_projects_custom_success


@router.get(
    "/sources/{source_id}/extracted-data",
    status_code=status.HTTP_200_OK,
    responses=get_source_extracted_data_responses,
)
async def get_source_extracted_data(
    source_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    start_date: Optional[str] = Query(
        None, description="ISO8601 start datetime to filter scraped_at"
    ),
    end_date: Optional[str] = Query(None, description="ISO8601 end datetime to filter scraped_at"),
    only_with_extracted: bool = Query(
        False, description="Return only revisions with extracted_data"
    ),
    api_key=Depends(get_api_key_from_header),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve extracted data for a given source.

    Returns paginated revision records for `source_id`, optionally filtered
    by date range and whether they contain extracted data.

    **Query Parameters**
    - skip: Records to skip (≥0)
    - limit: Max records to return (1-1000)
    - start_date / end_date: ISO8601 datetime filters for `scraped_at`
    - only_with_extracted: Return only revisions with `extracted_data`

    **Path Parameters**
    - source_id: UUID of the source

    Requires a valid API key in the header.

    **Returns**
    - List of revision objects matching the filters.

    **Status Codes**
    - 200 OK: Data retrieved successfully
    """
    required_scope = "read:source"
    if not api_key_has_scope(api_key, required_scope):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient scope")

    if getattr(api_key, "organization_id", None):
        stmt_check = select(Source).where(
            and_(Source.id == source_id, Source.jurisdiction_id.isnot(None))
        )
        res_check = await db.execute(stmt_check)
        src = res_check.scalars().first()
        if not src:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

        from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction

        stmt_j = select(Jurisdiction).where(Jurisdiction.id == src.jurisdiction_id)
        rj = await db.execute(stmt_j)
        jur = rj.scalars().first()
        if not jur:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Jurisdiction not found"
            )

        from app.api.modules.v1.projects.models.project_model import Project

        stmt_p = select(Project).where(Project.id == jur.project_id)
        rp = await db.execute(stmt_p)
        proj = rp.scalars().first()
        if not proj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        if getattr(api_key, "organization_id", None) != getattr(proj, "org_id", None):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Organization mismatch"
            )

    stmt = select(DataRevision).where(DataRevision.source_id == source_id)

    if start_date:
        try:
            sd = datetime.fromisoformat(start_date)
            stmt = stmt.where(DataRevision.scraped_at >= sd)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid start_date"
            )
    if end_date:
        try:
            ed = datetime.fromisoformat(end_date)
            stmt = stmt.where(DataRevision.scraped_at <= ed)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid end_date")

    if only_with_extracted:
        stmt = stmt.where(DataRevision.extracted_data.isnot(None))

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    revisions = result.scalars().all()

    payload = [
        {
            "id": str(r.id),
            "source_id": str(r.source_id),
            "scraped_at": getattr(r, "scraped_at", None).isoformat()
            if getattr(r, "scraped_at", None)
            else None,
            "extracted_data": r.extracted_data or {},
        }
        for r in revisions
    ]

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Extracted data retrieved",
        data={"revisions": payload},
    )


get_source_extracted_data._custom_errors = get_source_extracted_data_custom_errors
get_source_extracted_data._custom_success = get_source_extracted_data_custom_success


@router.get(
    "/sources/{source_id}/extracted-data/download",
    status_code=status.HTTP_200_OK,
    responses=download_source_extracted_data_responses,
)
async def download_source_extracted_data(
    source_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=5000),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    only_with_extracted: bool = Query(False),
    api_key=Depends(get_api_key_from_header),
    db: AsyncSession = Depends(get_db),
):
    """
    Download extracted data for a given source.

    Returns a file containing revision records for `source_id`, optionally
    filtered by date range and whether they include extracted data. Supports
    pagination via `skip` and `limit`.

    **Query Parameters**
    - skip: Number of records to skip (≥0)
    - limit: Maximum number of records to include (1-5000)
    - start_date / end_date: Optional ISO8601 datetime filters
    - only_with_extracted: If True, include only revisions with extracted data

    **Path Parameters**
    - source_id: UUID of the source

    Requires a valid API key in the header.

    **Returns**
    - File download containing the extracted data.

    **Status Codes**
    - 200 OK: File ready for download
    """
    required_scope = "download:data_revision"
    if not api_key_has_scope(api_key, required_scope):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient scope")

    from app.api.modules.v1.scraping.models.data_revision import DataRevision

    stmt = select(DataRevision).where(DataRevision.source_id == source_id)
    if start_date:
        try:
            sd = datetime.fromisoformat(start_date)
            stmt = stmt.where(DataRevision.scraped_at >= sd)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid start_date"
            )
    if end_date:
        try:
            ed = datetime.fromisoformat(end_date)
            stmt = stmt.where(DataRevision.scraped_at <= ed)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid end_date")
    if only_with_extracted:
        stmt = stmt.where(DataRevision.extracted_data.isnot(None))

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    revisions = result.scalars().all()

    payload = [
        {
            "id": str(r.id),
            "source_id": str(r.source_id),
            "scraped_at": getattr(r, "scraped_at", None).isoformat()
            if getattr(r, "scraped_at", None)
            else None,
            "extracted_data": r.extracted_data or {},
        }
        for r in revisions
    ]

    headers = {
        "Content-Disposition": f"attachment; filename=source_{source_id}_extracted_data.json"
    }
    return StreamingResponse(
        _iter_json_bytes(payload), media_type="application/json", headers=headers
    )


download_source_extracted_data._custom_errors = download_source_extracted_data_custom_errors
download_source_extracted_data._custom_success = download_source_extracted_data_custom_success


@router.get(
    "/jurisdictions/{jurisdiction_id}/extracted-data/download",
    status_code=status.HTTP_200_OK,
    responses=download_jurisdiction_extracted_data_responses,
)
async def download_jurisdiction_extracted_data(
    jurisdiction_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=5000),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    only_with_extracted: bool = Query(False),
    api_key=Depends(get_api_key_from_header),
    db: AsyncSession = Depends(get_db),
):
    """
    Download extracted data for a given jurisdiction.

    Returns a file containing revision records for `jurisdiction_id`, with
    optional filtering by date range and whether they include extracted data.
    Supports pagination via `skip` and `limit`.

    **Query Parameters**
    - skip: Number of records to skip (≥0)
    - limit: Maximum number of records to include (1-5000)
    - start_date / end_date: Optional ISO8601 datetime filters
    - only_with_extracted: If True, include only revisions with extracted data

    **Path Parameters**
    - jurisdiction_id: UUID of the jurisdiction

    Requires a valid API key in the header.

    **Returns**
    - File download containing the extracted data.

    **Status Codes**
    - 200 OK: File ready for download
    """
    required_scope = "download:data_revision"
    if not api_key_has_scope(api_key, required_scope):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient scope")

    from app.api.modules.v1.scraping.models.data_revision import DataRevision
    from app.api.modules.v1.scraping.models.source_model import Source

    stmt = (
        select(DataRevision)
        .join(Source, DataRevision.source_id == Source.id)
        .where(Source.jurisdiction_id == jurisdiction_id)
    )
    if start_date:
        try:
            sd = datetime.fromisoformat(start_date)
            stmt = stmt.where(DataRevision.scraped_at >= sd)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid start_date"
            )
    if end_date:
        try:
            ed = datetime.fromisoformat(end_date)
            stmt = stmt.where(DataRevision.scraped_at <= ed)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid end_date")
    if only_with_extracted:
        stmt = stmt.where(DataRevision.extracted_data.isnot(None))

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    revisions = result.scalars().all()

    payload = [
        {
            "id": str(r.id),
            "source_id": str(r.source_id),
            "scraped_at": getattr(r, "scraped_at", None).isoformat()
            if getattr(r, "scraped_at", None)
            else None,
            "extracted_data": r.extracted_data or {},
        }
        for r in revisions
    ]

    headers = {
        "Content-Disposition": f"attachment; "
        f"filename=jurisdiction_{jurisdiction_id}_extracted_data.json"
    }
    return StreamingResponse(
        _iter_json_bytes(payload), media_type="application/json", headers=headers
    )


download_jurisdiction_extracted_data._custom_errors = (
    download_jurisdiction_extracted_data_custom_errors
)
download_jurisdiction_extracted_data._custom_success = (
    download_jurisdiction_extracted_data_custom_success
)


@router.get(
    "/projects/{project_id}/extracted-data/download",
    status_code=status.HTTP_200_OK,
    responses=download_project_extracted_data_responses,
)
async def download_project_extracted_data(
    project_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=5000),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    only_with_extracted: bool = Query(False),
    api_key=Depends(get_api_key_from_header),
    db: AsyncSession = Depends(get_db),
):
    """
    Download extracted data for a given project.

    Returns a file containing revision records for `project_id`, optionally
    filtered by date range and whether they contain extracted data. Supports
    pagination via `skip` and `limit`.

    **Query Parameters**
    - skip: Number of records to skip (≥0)
    - limit: Maximum number of records to include (1-5000)
    - start_date / end_date: Optional ISO8601 datetime filters
    - only_with_extracted: If True, include only revisions with extracted data

    **Path Parameters**
    - project_id: UUID of the project

    Requires a valid API key in the header.

    **Returns**
    - File download containing the extracted data.

    **Status Codes**
    - 200 OK: File ready for download
    """
    required_scope = "download:data_revision"
    if not api_key_has_scope(api_key, required_scope):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient scope")

    from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
    from app.api.modules.v1.scraping.models.data_revision import DataRevision
    from app.api.modules.v1.scraping.models.source_model import Source

    stmt = (
        select(DataRevision)
        .join(Source, DataRevision.source_id == Source.id)
        .join(Jurisdiction, Source.jurisdiction_id == Jurisdiction.id)
        .where(Jurisdiction.project_id == project_id)
    )
    if start_date:
        try:
            sd = datetime.fromisoformat(start_date)
            stmt = stmt.where(DataRevision.scraped_at >= sd)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid start_date"
            )
    if end_date:
        try:
            ed = datetime.fromisoformat(end_date)
            stmt = stmt.where(DataRevision.scraped_at <= ed)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid end_date")
    if only_with_extracted:
        stmt = stmt.where(DataRevision.extracted_data.isnot(None))

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    revisions = result.scalars().all()

    payload = [
        {
            "id": str(r.id),
            "source_id": str(r.source_id),
            "scraped_at": getattr(r, "scraped_at", None).isoformat()
            if getattr(r, "scraped_at", None)
            else None,
            "extracted_data": r.extracted_data or {},
        }
        for r in revisions
    ]

    headers = {
        "Content-Disposition": f"attachment; filename=project_{project_id}_extracted_data.json"
    }
    return StreamingResponse(
        _iter_json_bytes(payload), media_type="application/json", headers=headers
    )


download_project_extracted_data._custom_errors = download_project_extracted_data_custom_errors
download_project_extracted_data._custom_success = download_project_extracted_data_custom_success


@router.get(
    "/jurisdictions/{jurisdiction_id}/extracted-data",
    status_code=status.HTTP_200_OK,
    responses=get_jurisdiction_extracted_data_responses,
)
async def get_jurisdiction_extracted_data(
    jurisdiction_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    start_date: Optional[str] = Query(
        None, description="ISO8601 start datetime to filter scraped_at"
    ),
    end_date: Optional[str] = Query(None, description="ISO8601 end datetime to filter scraped_at"),
    only_with_extracted: bool = Query(
        False, description="Return only revisions with extracted_data"
    ),
    api_key=Depends(get_api_key_from_header),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve extracted data for a given jurisdiction.

    Returns paginated revision records for `jurisdiction_id`, optionally
    filtered by date range and whether they contain extracted data.

    **Query Parameters**
    - skip: Number of records to skip (≥0)
    - limit: Maximum number of records to return (1-1000)
    - start_date / end_date: ISO8601 datetime filters for `scraped_at`
    - only_with_extracted: If True, return only revisions with `extracted_data`

    **Path Parameters**
    - jurisdiction_id: UUID of the jurisdiction

    Requires a valid API key in the header.

    **Returns**
    - List of revision objects matching the filters.

    **Status Codes**
    - 200 OK: Data retrieved successfully
    """
    required_scope = "read:jurisdiction"
    if not api_key_has_scope(api_key, required_scope):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient scope")

    from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
    from app.api.modules.v1.projects.models.project_model import Project
    from app.api.modules.v1.scraping.models.data_revision import DataRevision
    from app.api.modules.v1.scraping.models.source_model import Source

    if getattr(api_key, "organization_id", None):
        stmt_proj = (
            select(Project)
            .join(Jurisdiction, Jurisdiction.project_id == Project.id)
            .where(Jurisdiction.id == jurisdiction_id)
        )
        rp = await db.execute(stmt_proj)
        proj = rp.scalars().first()
        if not proj or getattr(api_key, "organization_id", None) != getattr(proj, "org_id", None):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Organization mismatch"
            )

    stmt = (
        select(DataRevision)
        .join(Source, DataRevision.source_id == Source.id)
        .where(Source.jurisdiction_id == jurisdiction_id)
    )

    if start_date:
        try:
            sd = datetime.fromisoformat(start_date)
            stmt = stmt.where(DataRevision.scraped_at >= sd)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid start_date"
            )
    if end_date:
        try:
            ed = datetime.fromisoformat(end_date)
            stmt = stmt.where(DataRevision.scraped_at <= ed)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid end_date")

    if only_with_extracted:
        stmt = stmt.where(DataRevision.extracted_data.isnot(None))

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    revisions = result.scalars().all()

    payload = [
        {
            "id": str(r.id),
            "source_id": str(r.source_id),
            "scraped_at": getattr(r, "scraped_at", None).isoformat()
            if getattr(r, "scraped_at", None)
            else None,
            "extracted_data": r.extracted_data or {},
        }
        for r in revisions
    ]

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Extracted data retrieved",
        data={"revisions": payload},
    )


get_jurisdiction_extracted_data._custom_errors = get_jurisdiction_extracted_data_custom_errors
get_jurisdiction_extracted_data._custom_success = get_jurisdiction_extracted_data_custom_success


@router.get(
    "/projects/{project_id}/extracted-data",
    status_code=status.HTTP_200_OK,
    responses=get_project_extracted_data_responses,
)
async def get_project_extracted_data(
    project_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    start_date: Optional[str] = Query(
        None, description="ISO8601 start datetime to filter scraped_at"
    ),
    end_date: Optional[str] = Query(None, description="ISO8601 end datetime to filter_scraped_at"),
    only_with_extracted: bool = Query(
        False, description="Return only revisions with extracted_data"
    ),
    api_key=Depends(get_api_key_from_header),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve extracted data for a given project.

    Returns paginated revision records for `project_id`, optionally filtered
    by date range and whether they contain extracted data.

    **Query Parameters**
    - skip: Number of records to skip (≥0)
    - limit: Maximum number of records to return (1-1000)
    - start_date / end_date: ISO8601 datetime filters for `scraped_at`
    - only_with_extracted: If True, return only revisions with `extracted_data`

    **Path Parameters**
    - project_id: UUID of the project

    Requires a valid API key in the header.

    **Returns**
    - List of revision objects matching the filters.

    **Status Codes**
    - 200 OK: Data retrieved successfully
    """
    required_scope = "read:project"
    if not api_key_has_scope(api_key, required_scope):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient scope")

    from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
    from app.api.modules.v1.projects.models.project_model import Project
    from app.api.modules.v1.scraping.models.data_revision import DataRevision
    from app.api.modules.v1.scraping.models.source_model import Source

    if getattr(api_key, "organization_id", None):
        stmt_p = select(Project).where(Project.id == project_id)
        rp = await db.execute(stmt_p)
        proj = rp.scalars().first()
        if not proj or getattr(api_key, "organization_id", None) != getattr(proj, "org_id", None):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Organization mismatch"
            )

    stmt = (
        select(DataRevision)
        .join(Source, DataRevision.source_id == Source.id)
        .join(Jurisdiction, Source.jurisdiction_id == Jurisdiction.id)
        .where(Jurisdiction.project_id == project_id)
    )

    # apply date filters
    if start_date:
        try:
            sd = datetime.fromisoformat(start_date)
            stmt = stmt.where(DataRevision.scraped_at >= sd)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid start_date"
            )
    if end_date:
        try:
            ed = datetime.fromisoformat(end_date)
            stmt = stmt.where(DataRevision.scraped_at <= ed)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid end_date")

    if only_with_extracted:
        stmt = stmt.where(DataRevision.extracted_data.isnot(None))

    stmt = stmt.offset(skip).limit(limit)

    result = await db.execute(stmt)
    revisions = result.scalars().all()

    payload = [
        {
            "id": str(r.id),
            "source_id": str(r.source_id),
            "scraped_at": getattr(r, "scraped_at", None).isoformat()
            if getattr(r, "scraped_at", None)
            else None,
            "extracted_data": r.extracted_data or {},
        }
        for r in revisions
    ]

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Extracted data retrieved",
        data={"revisions": payload},
    )


get_project_extracted_data._custom_errors = get_project_extracted_data_custom_errors
get_project_extracted_data._custom_success = get_project_extracted_data_custom_success
