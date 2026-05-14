# API Response Guide

This guide explains how to use the standardized response functions in the Legal Watch Dog API. All responses follow a framework-agnostic schema to ensure consistency, security, and predictability across the application.

## Overview

The API uses three main response functions from `app/api/utils/response_payloads.py`:

- `success_response`: For successful operations
- `auth_response`: For authentication successes (includes access token)
- `error_response`: For errors and failures

Global exception handlers are implemented in `main.py` to automatically handle unhandled errors using `error_response`.

## Response Schema

### Success Response
```json
{
  "status": "success",
  "status_code": 200,
  "message": "Operation completed successfully",
  "data": {
    // Payload data here
  }
}
```

### Error Response
```json
{
  "status": "failure",
  "status_code": 400,
  "message": "Validation failed",
  "error": {}
}
```

## Using Success Responses

Import the function:
```python
from app.api.utils.response_payloads import success_response
```

### Basic Success Example
```python
from app.api.utils.response_payloads import success_response

@app.get("/users/{user_id}")
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        # Handle error (see below)
        pass
    
    return success_response(
        status_code=200,
        message="User retrieved successfully",
        data={"user": user.to_dict()}
    )
```

### Success with Metadata
```python
@app.get("/users")
async def get_users(page: int = 1, limit: int = 10, db: AsyncSession = Depends(get_db)):
    users = await db.query(User).offset((page-1)*limit).limit(limit).all()
    total = await db.query(User).count()
    
    return success_response(
        status_code=200,
        message="Users retrieved successfully",
        data={
            "users": [user.to_dict() for user in users],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total
            }
        }
    )
```

### Auth Success Example
```python
from app.api.utils.response_payloads import auth_response

@app.post("/auth/login")
async def login(credentials: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, credentials.email, credentials.password)
    token = create_access_token(user.id)
    
    return auth_response(
        status_code=200,
        message="Login successful",
        access_token=token,
        data={"user": user.to_dict()}
    )
```

## Using Error Responses

Import the function:
```python
from app.api.utils.response_payloads import error_response
```

### Validation Error Example
```python
@app.post("/users")
async def create_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check if email exists
    existing = await db.query(User).filter(User.email == user_data.email).first()
    if existing:
        return error_response(
            status_code=409,
            message="User with this email already exists",
        )
    
    # Create user...
    return success_response(
        status_code=201,
        message="User created successfully",
        data={"user": new_user.to_dict()}
    )
```

### Not Found Error Example
```python
@app.get("/projects/{project_id}")
async def get_project(project_id: int, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        return error_response(
            status_code=404,
            message="Project not found",
        )
    
    return success_response(
        status_code=200,
        message="Project retrieved successfully",
        data={"project": project.to_dict()}
    )
```

### Forbidden Error Example
```python
@app.put("/projects/{project_id}")
async def update_project(project_id: int, update_data: ProjectUpdate, 
                        current_user: User = Depends(get_current_user), 
                        db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        return error_response(status_code=404, message="Project not found")
    
    # Check permissions
    if project.organization_id != current_user.organization_id:
        return error_response(
            status_code=403,
            message="You don't have permission to update this project",
        )
    
    # Update project...
    return success_response(
        status_code=200,
        message="Project updated successfully",
        data={"project": updated_project.to_dict()}
    )
```

## Global Exception Handling

The application automatically handles unhandled exceptions through global exception handlers in `main.py`:

- **RequestValidationError**: Converts Pydantic validation errors to standardized format
- **HTTPException**: Converts FastAPI HTTP exceptions to standardized format  
- **Exception**: Catches all other exceptions and returns generic 500 error

These handlers:
- Log full error details server-side with a `trace_id`
- Return only safe, user-friendly information in the response
- Prevent leaking internal stack traces or framework details

### Example of Automatic Error Handling

If your code raises an unhandled exception:
```python
@app.get("/test-error")
async def test_error():
    raise ValueError("Something went wrong")
```

The global handler will catch it and return:
```json
{
  "status": "failure",
  "status_code": 500,
  "message": "Internal server error",
}
```

While logging the full stack trace server-side for debugging.

## Best Practices

1. **Always use response functions**: Never return raw dicts or raise HTTPException directly in routes
2. **Include trace_id in errors**: For debugging, include a UUID trace_id in error responses
3. **Use appropriate status codes**: Follow HTTP conventions (200 OK, 201 Created, 400 Bad Request, etc.)
4. **Structure error data**: Use `data["errors"]` for field-level validation errors
5. **Keep messages user-friendly**: Error messages should be clear but not reveal internals
6. **Log full details**: Use the global handlers or manual logging for debugging info
7. **Test responses**: Ensure your endpoints return the correct response schema

## Testing

Add tests to verify response formats:

```python
def test_success_response():
    response = success_response(200, "OK", {"key": "value"})
    assert response.status_code == 200
    data = response.body
    assert data["status"] == "success"
    assert data["data"]["key"] == "value"

def test_error_response():
    response = error_response(400, "Bad Request", {"errors": {"field": ["error"]}})
    assert response.status_code == 400
    data = response.body
    assert data["status"] == "failure"
```