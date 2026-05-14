# AGENTS.md - FastAPI Application Template

> A comprehensive guide for AI coding agents working on this FastAPI application.
> This file serves as an **operating manual** for automated coding assistants, defining conventions, patterns, and boundaries.

---

## Project Overview

**Tech Stack:**
- Python 3.12+ with FastAPI 0.121+
- SQLModel 0.0.27+ / SQLAlchemy 2.0.44+ (async with asyncpg)
- PostgreSQL 14+ (primary) / SQLite (dev fallback)
- Pydantic 2.0+ for validation and schemas
- Redis 5.0+ for caching, rate limiting, and pub/sub
- Celery 5.4+ with Redis broker for async tasks
- Alembic for database migrations
- UV for dependency management
- Ruff for linting and formatting

**Architecture Pattern:** Modular Separation of Concerns (SoC) with SOLID principles.

---

## Setup Commands

```bash
# Install dependencies
uv sync

# Activate virtual environment
.venv\Scripts\Activate  # Windows (PowerShell)
source .venv/bin/activate  # Linux/macOS

# Run application
uv run python main.py

# Run tests
pytest
pytest --cov=app  # with coverage

# Linting & Formatting
uv run ruff check .
uv run ruff format --check .
uv run ruff check . --fix  # auto-fix

# Database migrations
alembic upgrade head  # apply migrations
alembic revision --autogenerate -m "description"  # create migration

# Pre-commit hooks
pre-commit install
pre-commit run --all-files
```

---

## Project Structure

```
legal-watch-dog-be/
├── main.py                    # FastAPI app entry point
├── app/
│   ├── celery_app.py          # Celery configuration
│   └── api/
│       ├── core/              # Core utilities & config
│       │   ├── config.py      # Settings (env-based)
│       │   ├── exceptions.py  # Global exception handlers
│       │   ├── custom_exceptions/  # Domain exceptions
│       │   │   ├── exceptions.py   # CustomDomainException classes
│       │   │   ├── handlers.py     # Exception handlers
│       │   │   └── register.py     # Registration to FastAPI
│       │   ├── dependencies/  # Depends() factories
│       │   ├── middleware/    # Request middleware
│       │   ├── llm/           # LLM provider integrations
│       │   └── security.py    # JWT & auth utilities
│       ├── db/
│       │   └── database.py    # DB engine & session factories
│       ├── utils/             # Shared utilities
│       │   ├── response_payloads.py  # success_response, error_response
│       │   ├── pagination.py
│       │   └── ...
│       └── modules/v1/        # Feature modules (SoC)
│           ├── auth/
│           ├── users/
│           ├── organization/
│           ├── ... (feature modules)
│           └── <module>/
│               ├── models/    # SQLModel ORM models
│               ├── schemas/   # Pydantic request/response schemas
│               ├── service/   # Business logic (services)
│               └── routes/    # FastAPI route handlers
│                   └── docs/  # OpenAPI documentation
├── alembic/                   # Database migrations
│   └── versions/
├── tests/                     # Pytest test suite
├── scripts/                   # Utility scripts
└── pyproject.toml             # Project config & deps
```

---

## Code Style & Conventions

### Naming Conventions
- **Functions/Methods:** `snake_case` (`get_user_by_id`, `create_organization`)
- **Classes:** `PascalCase` (`UserCRUD`, `RegistrationService`)
- **Constants:** `UPPER_SNAKE_CASE` (`MAX_RETRIES`, `DEFAULT_PAGE_SIZE`)
- **File Names:** `snake_case.py` (`users_model.py`, `register_service.py`)
- **Modules:** Pluralized for collections (`users/`, `tickets/`)

### Code Formatting
- Line length: 100 characters
- Double quotes for strings
- Imports sorted: stdlib → third-party → local (Ruff handles this)
- No trailing whitespace

---

## Service Layer Pattern

Services contain all business logic. Routes MUST NOT contain try-catch blocks for business logic.

### ✅ Good - Service with Exception-Based Error Handling:
```python
# service/register_service.py
from app.api.core.custom_exceptions.exceptions import (
    UserAlreadyRegisteredError,
    ProcessingError,
)

class RegistrationService:
    """Service class for user registration business logic."""

    def __init__(self, db: AsyncSession, redis_client: Redis):
        """
        Initialize registration service.

        Args:
            db: Async database session
            redis_client: Redis client instance
        """
        self.db = db
        self.redis_client = redis_client

    async def register_user(self, payload: RegisterRequest) -> dict:
        """
        Handle user registration.

        Args:
            payload: Registration request with email, name, password.

        Returns:
            dict: Registration result with user email.

        Raises:
            UserAlreadyRegisteredError: If email already exists.
            ProcessingError: If unexpected error occurs.
        """
        try:
            existing_user = await UserCRUD.get_by_email(self.db, payload.email)
            if existing_user:
                raise UserAlreadyRegisteredError()

            # ... business logic ...
            return {"email": payload.email}

        except UserAlreadyRegisteredError:
            raise  # Re-raise domain exceptions
        except Exception as e:
            logger.error(f"Registration failed: {e}", exc_info=True)
            raise ProcessingError(message="Registration failed. Please try again.")
```

### ✅ Good - Route Handler (No try-catch):
```python
# routes/auth_routes.py
from app.api.utils.response_payloads import success_response

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
):
    """
    Initiate user registration.

    Args:
        payload: Registration details.
        db: Database session.
        redis_client: Redis client.

    Returns:
        dict: Standardized success response.
    """
    service = RegistrationService(db, redis_client)
    result = await service.register_user(payload)

    return success_response(
        status_code=status.HTTP_201_CREATED,
        message="Registration initiated. Verify OTP sent to email.",
        data=result,
    )
```

### ❌ Bad - Route with try-catch:
```python
@router.post("/register")
async def register_user(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    try:  # ❌ NO try-catch in routes
        service = RegistrationService(db)
        result = await service.register_user(payload)
        return {"data": result}  # ❌ Wrong response format
    except Exception as e:
        return {"error": str(e)}  # ❌ Wrong error format
```

---

## Custom Exceptions

All domain exceptions inherit from `CustomDomainException` and are auto-registered to FastAPI.

### Creating New Exceptions:
```python
# app/api/core/custom_exceptions/exceptions.py

class CustomDomainException(Exception):
    """Base exception for all domain-specific errors."""

    def __init__(self, message: str, code: str):
        self.message = message
        self.code = code
        super().__init__(message)


class ResourceNotFoundError(CustomDomainException):
    """Raised when a requested resource is not found."""

    def __init__(self, message: str = ""):
        message = "The requested resource was not found." if not message else message
        super().__init__(message=message, code="NOT_FOUND")


class InvalidCredentialsError(CustomDomainException):
    """Raised when authentication fails."""

    def __init__(self, message: str = ""):
        message = (
            "The email or password you entered is incorrect."
            if not message
            else message
        )
        super().__init__(message=message, code="INVALID_CREDENTIALS")
```

### Exception Pattern Hierarchy:
```
CustomDomainException
├── NotFoundError (404)
├── PermissionDeniedError (403)
├── AlreadyExistsError (409)
├── InvalidCredentialsError (401)
├── ProcessingError (500)
├── RateLimitExceededError (429)
└── ... (domain-specific exceptions)
```

---

## Response Payloads

ALWAYS use standardized response functions from `app/api/utils/response_payloads.py`.

### Success Response:
```python
from app.api.utils.response_payloads import success_response

return success_response(
    status_code=200,
    message="User retrieved successfully",
    data={"user_id": str(user.id), "email": user.email},
)
# Output:
# {
#     "status": "SUCCESS",
#     "status_code": 200,
#     "message": "User retrieved successfully",
#     "data": {"user_id": "...", "email": "..."}
# }
```

### Error Response (for special cases in routes):
```python
from app.api.utils.response_payloads import error_response

return error_response(
    status_code=401,
    message="Please register to accept this invitation.",
    error_code="AUTHORIZATION_REQUIRED",
)
# Output:
# {
#     "error_code": "AUTHORIZATION_REQUIRED",
#     "message": "Please register to accept this invitation.",
#     "status_code": 401,
#     "errors": {}
# }
```

---

## SQLModel / Database Patterns

### Model Definition:
```python
# models/users_model.py
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.organization.models import Organization

class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )
    email: str = Field(max_length=255, nullable=False, unique=True, index=True)
    name: str = Field(index=True, max_length=255)
    is_active: bool = Field(default=True, nullable=False)
    
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    # Relationships (use TYPE_CHECKING for forward references)
    organizations: list["Organization"] = Relationship(
        back_populates="users",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
```

### Database Session Pattern:
```python
# Async session injection (routes)
from app.api.db.database import get_db

@router.get("/users/{user_id}")
async def get_user(user_id: UUID, db: AsyncSession = Depends(get_db)):
    ...

# Never create sessions manually in services - always inject
```

### Query Optimization:
```python
# Use selectinload/joinedload for relationships
from sqlalchemy.orm import selectinload

stmt = select(User).options(selectinload(User.organizations)).where(User.id == user_id)

# Use indexes for frequently queried columns
email: str = Field(..., index=True)

# Use pagination for large result sets
from app.api.utils.pagination import paginate
```

---

## Pydantic Schemas

### Request/Response Schemas:
```python
# schemas/user_schema.py
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

class UserCreateRequest(BaseModel):
    """Request schema for creating a user."""
    email: EmailStr
    name: str
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserResponse(BaseModel):
    """Response schema for user data."""
    id: UUID
    email: str
    name: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
```

---

## OpenAPI Documentation Pattern

Each route has a dedicated docs file with responses and custom error/success markers.

```python
# routes/docs/user_routes_docs.py

get_user_responses = {
    200: {
        "description": "User Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "User Found",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "User retrieved successfully",
                            "data": {
                                "id": "123e4567-e89b-12d3-a456-426614174000",
                                "email": "user@example.com",
                                "name": "John Doe",
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "User Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "User Does Not Exist",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "User not found",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

get_user_custom_errors = ["404", "500"]
get_user_custom_success = {
    "status_code": 200,
    "description": "User retrieved successfully.",
}
```

### Route Integration:
```python
# routes/users_route.py
from .docs.user_routes_docs import (
    get_user_responses,
    get_user_custom_errors,
    get_user_custom_success,
)

@router.get("/{user_id}", responses=get_user_responses)
async def get_user(user_id: UUID, db: AsyncSession = Depends(get_db)):
    ...

# Attach custom markers for OpenAPI generator
get_user._custom_errors = get_user_custom_errors
get_user._custom_success = get_user_custom_success
```

---

## Docstring Standards

Use Google-style docstrings with Args, Returns, Raises, and Examples.

```python
async def create_user(
    self,
    name: str,
    email: str,
    hashed_password: str,
) -> User:
    """
    Create a new user in the database.

    Args:
        name: User's full name.
        email: User's email address (must be unique).
        hashed_password: Bcrypt-hashed password.

    Returns:
        User: The newly created user object.

    Raises:
        AlreadyExistsError: If email already exists.
        ProcessingError: If database operation fails.

    Examples:
        >>> user = await user_crud.create_user(
        ...     name="John Doe",
        ...     email="john@example.com",
        ...     hashed_password="$2b$12$..."
        ... )
        >>> print(user.id)
        UUID('...')
    """
```

---

## Testing Standards

```bash
# Run all tests
pytest

# Run specific module
pytest tests/api/modules/v1/auth/

# Run with coverage
pytest --cov=app --cov-report=html

# Run single test
pytest -k "test_user_registration"
```

### Test File Structure:
```
tests/
└── api/
    └── modules/
        └── v1/
            └── auth/
                ├── test_register.py
                ├── test_login.py
                └── conftest.py  # Fixtures
```

---

## Git Workflow

- **Branch from:** `dev`
- **PR Target:** `dev`
- **Title Format:** `[module] Brief description`
- **Pre-commit:** Run `pre-commit run --all-files` before committing

---

## Boundaries

### ✅ Always Do:
- Use `success_response()` and `error_response()` for all API responses
- Inherit custom exceptions from `CustomDomainException`
- Put business logic in service classes, not routes
- Add comprehensive docstrings with Args/Returns/Raises
- Use UUID for primary keys, datetime with timezone
- Add indexes for frequently queried columns
- Run `ruff check` and `ruff format` before commits
- Write tests for new functionality
- Use `TYPE_CHECKING` for forward references in models

### ⚠️ Ask First:
- Database schema changes (require Alembic migration)
- Adding new dependencies to `pyproject.toml`
- Modifying `main.py` or core middleware
- Creating new exception types
- Changes to authentication/authorization logic
- Modifying CI/CD configuration (`.github/workflows/`)

### 🚫 Never Do:
- Add try-catch blocks in route handlers for business logic
- Return raw dicts instead of `success_response`/`error_response`
- Create database sessions manually (always use `Depends(get_db)`)
- Commit `.env` files or secrets
- Skip docstrings for public functions/classes
- Use mutable default arguments
- Ignore type hints
- Edit `alembic/versions/` files directly (auto-generated)
- Remove failing tests without investigation

---

## Celery Workers

```bash
# Scraping worker (gevent pool)
celery -A app.celery_app worker --pool=gevent --concurrency=200 --queues=scraping

# Processing worker (prefork pool)
celery -A app.celery_app worker --pool=prefork --concurrency=4 --queues=processing

# Persistence worker
celery -A app.celery_app worker --pool=prefork --concurrency=2 --queues=persistence

# Beat scheduler
celery -A app.celery_app beat --loglevel=info
```

---

## Quick Reference - New Feature Checklist

1. [ ] Create module directory: `app/api/modules/v1/<feature>/`
2. [ ] Add subdirectories: `models/`, `schemas/`, `service/`, `routes/`, `routes/docs/`
3. [ ] Define SQLModel in `models/<feature>_model.py`
4. [ ] Create Pydantic schemas in `schemas/<feature>_schema.py`
5. [ ] Implement service class in `service/<feature>_service.py`
6. [ ] Create routes in `routes/<feature>_routes.py`
7. [ ] Add OpenAPI docs in `routes/docs/<feature>_docs.py`
8. [ ] Register router in `app/api/modules/v1/__init__.py`
9. [ ] Add custom exceptions if needed
10. [ ] Create Alembic migration: `alembic revision --autogenerate -m "add <feature>"`
11. [ ] Write tests in `tests/api/modules/v1/<feature>/`
12. [ ] Run linting: `uv run ruff check . --fix && uv run ruff format .`

---

*This AGENTS.md follows the [AGENTS.md standard](https://agents.md) and is compatible with GitHub Copilot, Cursor, Codex, Jules, Gemini CLI, and other AI coding agents.*
