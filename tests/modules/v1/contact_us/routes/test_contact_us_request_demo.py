import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport
from pytest_asyncio import fixture as pytest_asyncio_fixture
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.core.custom_exceptions.exceptions import CustomDomainException
from app.api.core.custom_exceptions.handlers import domain_exception_handler
from app.api.core.exceptions import (
    general_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.api.db.database import get_db
from app.api.modules.v1.contact_us.models.demo_request_model import DemoRequest
from app.api.modules.v1.contact_us.routes.contact_us import router as contact_us_router


@pytest_asyncio_fixture
async def app(pg_async_session: AsyncSession):
    """Async fixture for FastAPI app with overridden DB and exception handlers."""

    app = FastAPI()

    # Register global exception handlers used by main application
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(CustomDomainException, domain_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    app.include_router(contact_us_router, prefix="/api/v1")

    async def override_get_db():
        yield pg_async_session

    app.dependency_overrides[get_db] = override_get_db

    yield app


def _valid_demo_payload(overrides: dict | None = None) -> dict:
    payload = {
        "first_name": "Jane",
        "last_name": "Doe",
        "company_name": "Acme Corp",
        "company_size": "51-200",
        "industry": "Technology",
        "company_website_url": "https://acme.example.com",
        "country": "United States",
        "work_email": "jane.doe@acme.example.com",
        "job_title": "Head of Legal",
        "additional_context": "We would like a tailored walkthrough.",
    }
    if overrides:
        payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_request_demo_success_creates_record_and_returns_201(app, pg_async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/contact-us/request-demo",
            json=_valid_demo_payload(),
        )

    assert response.status_code == 201
    body = response.json()

    assert body["status"] == "SUCCESS"
    assert body["status_code"] == 201
    assert body["message"] == "Demo request submitted. Our team will reach out shortly."

    data = body["data"]
    assert data["first_name"] == "Jane"
    assert data["last_name"] == "Doe"
    assert data["company_name"] == "Acme Corp"
    assert data["work_email"] == "jane.doe@acme.example.com"
    assert "id" in data

    # Ensure record is actually persisted in the database
    demo_id = uuid.UUID(data["id"])
    result = await pg_async_session.exec(select(DemoRequest).where(DemoRequest.id == demo_id))
    saved = result.first()
    assert saved is not None
    assert saved.work_email == "jane.doe@acme.example.com"


@pytest.mark.asyncio
async def test_request_demo_pydantic_validation_error_returns_422(app):
    payload = _valid_demo_payload(
        {
            "first_name": "",  # will fail strip_text validator
            "work_email": "not-an-email",
        }
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/contact-us/request-demo",
            json=payload,
        )

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "VALIDATION_ERROR"
    assert "first_name" in body["errors"] or "work_email" in body["errors"]


@pytest.mark.asyncio
async def test_request_demo_invalid_company_size_returns_422(app):
    payload = _valid_demo_payload({"company_size": "0-0"})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/contact-us/request-demo",
            json=payload,
        )

    # Now handled by Pydantic Enum validation in schema
    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "VALIDATION_ERROR"
    assert "company_size" in body["errors"]


@pytest.mark.asyncio
async def test_request_demo_processing_error_uses_domain_exception_pipeline(app, monkeypatch):
    from app.api.modules.v1.contact_us.service import contact_us as contact_us_service_module

    mock_create = AsyncMock(side_effect=Exception("DB down"))
    monkeypatch.setattr(
        contact_us_service_module.DemoRequestCRUD,
        "create",
        mock_create,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/contact-us/request-demo",
            json=_valid_demo_payload(),
        )

    assert response.status_code == 500
    body = response.json()
    assert body["error_code"] == "PROCESSING_ERROR"


@pytest.mark.asyncio
async def test_request_demo_rate_limit_exceeded_returns_429(app, monkeypatch):
    """Verify rate limit violations return 429 via http_exception_handler.

    We patch the `check_rate_limit` function as imported in the
    `contact_us` routes module so that it always returns False,
    simulating that the caller has exceeded the limit.
    """

    from app.api.modules.v1.contact_us.service import contact_us as contact_service_module

    mock_rate_limit = AsyncMock(return_value=False)
    monkeypatch.setattr(contact_service_module, "check_rate_limit", mock_rate_limit)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/contact-us/request-demo",
            json=_valid_demo_payload(),
        )

    assert response.status_code == 429
    body = response.json()
    assert body["error_code"] == "RATE_LIMIT_EXCEEDED"
    assert "demo requests" in body["message"].lower() or "too many" in body["message"].lower()
