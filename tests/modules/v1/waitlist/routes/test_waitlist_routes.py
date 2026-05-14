"""
This module contains integration tests for the waitlist API routes.

It uses pytest fixtures to set up a test FastAPI application with an in-memory
PostgreSQL database session, allowing for isolated and repeatable tests of
the `/api/v1/waitlist` endpoints.

Tests cover:
- Successful waitlist signup.
- Handling of invalid input data (e.g., email format validation).
- Database interactions to ensure waitlist entries are correctly created and stored.
- Verification of HTTP status codes and response payloads.
"""

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport
from pytest_asyncio import fixture as pytest_asyncio_fixture
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.modules.v1.waitlist.models.waitlist_model import Waitlist
from app.api.modules.v1.waitlist.routes.waitlist_route import router as waitlist_router
from app.api.modules.v1.waitlist.schemas.waitlist_schema import WaitlistSignup


@pytest_asyncio_fixture
async def app(pg_async_session: AsyncSession):
    """Async fixture for FastAPI app with overridden database dependency."""
    app = FastAPI()

    from fastapi.exceptions import RequestValidationError

    from app.api.core.custom_exceptions.exceptions import CustomDomainException
    from app.api.core.custom_exceptions.handlers import domain_exception_handler
    from app.api.core.exceptions import validation_exception_handler

    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(CustomDomainException, domain_exception_handler)

    app.include_router(waitlist_router, prefix="/api/v1")

    async def override_get_db():
        yield pg_async_session

    from app.api.db.database import get_db

    app.dependency_overrides[get_db] = override_get_db

    yield app


@pytest.mark.asyncio
async def test_signup_waitlist_success(app, pg_async_session):
    payload = WaitlistSignup(
        organization_email="success@company.com", organization_name="Success Company"
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/v1/waitlist/signup", json=payload.model_dump())

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert "Successfully added to waitlist" in data["message"]


@pytest.mark.asyncio
async def test_signup_waitlist_success_with_punctuation(app, pg_async_session):
    payload = WaitlistSignup(
        organization_email="contact@smithjones.com", organization_name="Smith & Jones, Inc"
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/v1/waitlist/signup", json=payload.model_dump())

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "SUCCESS"


@pytest.mark.asyncio
async def test_signup_waitlist_duplicate_email(app, pg_async_session):
    entry = Waitlist(organization_email="dup@company.com", organization_name="Dup Company")
    pg_async_session.add(entry)
    await pg_async_session.commit()

    payload = WaitlistSignup(organization_email="dup@company.com", organization_name="Dup Company")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/v1/waitlist/signup", json=payload.model_dump())

    assert response.status_code == 409
    data = response.json()
    assert data["error_code"] == "EMAIL_ALREADY_EXISTS"
    assert "Email is already registered" in data["message"]


@pytest.mark.asyncio
async def test_signup_organization_name_with_numbers(app):
    payload = {"organization_email": "test@company.com", "organization_name": "Company123"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/v1/waitlist/signup", json=payload)

    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "organization_name" in data["errors"]
    assert "cannot contain numbers" in data["errors"]["organization_name"][0].lower()


@pytest.mark.asyncio
async def test_signup_organization_name_empty(app):
    payload = {"organization_email": "test@company.com", "organization_name": ""}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/v1/waitlist/signup", json=payload)

    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "organization_name" in data["errors"]
    assert "cannot be empty" in data["errors"]["organization_name"][0].lower()


@pytest.mark.asyncio
async def test_signup_organization_name_too_short(app):
    payload = {"organization_email": "test@company.com", "organization_name": "A"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/v1/waitlist/signup", json=payload)

    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "organization_name" in data["errors"]
    assert "at least 2 characters" in data["errors"]["organization_name"][0].lower()


@pytest.mark.asyncio
async def test_signup_organization_name_too_long(app):
    payload = {
        "organization_email": "test@company.com",
        "organization_name": "A" * 101,  # 101 characters
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/v1/waitlist/signup", json=payload)

    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "organization_name" in data["errors"]
    assert "cannot exceed 100 characters" in data["errors"]["organization_name"][0].lower()


@pytest.mark.asyncio
async def test_signup_organization_name_only_special_characters(app):
    payload = {"organization_email": "test@company.com", "organization_name": "###"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/v1/waitlist/signup", json=payload)

    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "organization_name" in data["errors"]
    assert "at least one letter" in data["errors"]["organization_name"][0].lower()


@pytest.mark.asyncio
async def test_signup_organization_name_invalid_special_characters(app):
    payload = {"organization_email": "test@company.com", "organization_name": "Company@#$%"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/v1/waitlist/signup", json=payload)

    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "organization_name" in data["errors"]


@pytest.mark.asyncio
async def test_signup_organization_name_excessive_spaces(app):
    payload = {"organization_email": "test@company.com", "organization_name": "Company    Name"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/v1/waitlist/signup", json=payload)

    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "organization_name" in data["errors"]
    assert "excessive consecutive spaces" in data["errors"]["organization_name"][0].lower()


@pytest.mark.asyncio
async def test_signup_organization_name_consecutive_punctuation(app):
    payload = {"organization_email": "test@company.com", "organization_name": "Company,,, Inc"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/v1/waitlist/signup", json=payload)

    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "organization_name" in data["errors"]
    assert "consecutive punctuation" in data["errors"]["organization_name"][0].lower()


@pytest.mark.asyncio
async def test_signup_organization_name_starts_with_punctuation(app):
    payload = {"organization_email": "test@company.com", "organization_name": "-Company Name"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/v1/waitlist/signup", json=payload)

    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "organization_name" in data["errors"]
    assert "cannot start with punctuation" in data["errors"]["organization_name"][0].lower()


@pytest.mark.asyncio
async def test_signup_organization_name_ends_with_punctuation(app):
    payload = {"organization_email": "test@company.com", "organization_name": "Company Name-"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/v1/waitlist/signup", json=payload)

    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "organization_name" in data["errors"]
    assert "cannot end with punctuation" in data["errors"]["organization_name"][0].lower()


@pytest.mark.asyncio
async def test_signup_dummy_email_test_domain(app):
    payload = {"organization_email": "test@test.com", "organization_name": "Valid Company"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/v1/waitlist/signup", json=payload)

    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "organization_email" in data["errors"]
    assert (
        "dummy" in data["errors"]["organization_email"][0].lower()
        or "test" in data["errors"]["organization_email"][0].lower()
    )


@pytest.mark.asyncio
async def test_signup_dummy_email_example_domain(app):
    payload = {"organization_email": "info@example.com", "organization_name": "Valid Company"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/v1/waitlist/signup", json=payload)

    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "organization_email" in data["errors"]


@pytest.mark.asyncio
async def test_signup_dummy_email_prefix(app):
    payload = {"organization_email": "dummy@realcompany.com", "organization_name": "Valid Company"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/v1/waitlist/signup", json=payload)

    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "organization_email" in data["errors"]


@pytest.mark.asyncio
async def test_signup_invalid_email_format(app):
    payload = {"organization_email": "not-an-email", "organization_name": "Valid Company"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/v1/waitlist/signup", json=payload)

    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "organization_email" in data["errors"]


@pytest.mark.asyncio
async def test_signup_email_without_domain(app):
    payload = {"organization_email": "test@nodomain", "organization_name": "Valid Company"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/v1/waitlist/signup", json=payload)

    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "organization_email" in data["errors"]


@pytest.mark.asyncio
async def test_signup_disposable_email_mailinator(app):
    payload = {"organization_email": "test@mailinator.com", "organization_name": "Valid Company"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/v1/waitlist/signup", json=payload)

    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "organization_email" in data["errors"]
    assert (
        "disposable" in data["errors"]["organization_email"][0].lower()
        or "temporary" in data["errors"]["organization_email"][0].lower()
    )


@pytest.mark.asyncio
async def test_signup_disposable_email_guerrillamail(app):
    payload = {"organization_email": "user@guerrillamail.com", "organization_name": "Valid Company"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/v1/waitlist/signup", json=payload)

    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "organization_email" in data["errors"]
    assert (
        "disposable" in data["errors"]["organization_email"][0].lower()
        or "temporary" in data["errors"]["organization_email"][0].lower()
    )


@pytest.mark.asyncio
async def test_signup_disposable_email_10minutemail(app):
    payload = {"organization_email": "test@10minutemail.com", "organization_name": "Valid Company"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/v1/waitlist/signup", json=payload)

    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "organization_email" in data["errors"]
    assert (
        "disposable" in data["errors"]["organization_email"][0].lower()
        or "temporary" in data["errors"]["organization_email"][0].lower()
    )


@pytest.mark.asyncio
async def test_signup_disposable_email_yopmail(app):
    payload = {"organization_email": "contact@yopmail.com", "organization_name": "Valid Company"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/v1/waitlist/signup", json=payload)

    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "organization_email" in data["errors"]
    assert (
        "disposable" in data["errors"]["organization_email"][0].lower()
        or "temporary" in data["errors"]["organization_email"][0].lower()
    )
