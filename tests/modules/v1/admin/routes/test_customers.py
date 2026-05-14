import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from app.api.core.custom_exceptions.exceptions import CustomerNotFoundError
from app.api.modules.v1.admin.routes.customers import (
    activate_customer,
    deactivate_customer,
    get_customer_activity,
    get_customer_detail,
    list_customers,
)
from app.api.modules.v1.users.models.users_model import User


@pytest.mark.asyncio
async def test_list_customers_success():
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    mock_current_user.email = "admin@example.com"

    mock_db = AsyncMock()

    mock_service_result = {
        "data": {
            "customers": [
                {
                    "id": str(uuid.uuid4()),
                    "name": "John Doe",
                    "email": "john@example.com",
                    "payment_status": "Paid",
                    "credits_used": 50000,
                    "amount_spent": 150.00,
                }
            ]
        },
        "meta": {"page": 1, "limit": 20, "total": 1, "total_pages": 1},
        "total": 1,
    }

    with patch(
        "app.api.modules.v1.admin.routes.customers.CustomerManagementService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.list_customers = AsyncMock(return_value=mock_service_result)

        response = await list_customers(
            current_user=mock_current_user,
            db=mock_db,
            page=1,
            limit=20,
            payment_status=None,
            search=None,
            sort_by="created_at",
            sort_order="desc",
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK
        assert response_data["message"] == "Customers retrieved successfully"
        assert "customers" in response_data["data"]
        assert response_data["data"]["meta"]["page"] == 1


@pytest.mark.asyncio
async def test_list_customers_with_filters():
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    mock_current_user.email = "admin@example.com"

    mock_db = AsyncMock()

    mock_service_result = {
        "data": {"customers": []},
        "meta": {"page": 1, "limit": 20, "total": 0, "total_pages": 0},
        "total": 0,
    }

    with patch(
        "app.api.modules.v1.admin.routes.customers.CustomerManagementService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.list_customers = AsyncMock(return_value=mock_service_result)

        response = await list_customers(
            current_user=mock_current_user,
            db=mock_db,
            page=1,
            limit=20,
            payment_status="paid",
            search="john",
            sort_by="last_active",
            sort_order="asc",
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK
        assert response_data["data"]["customers"] == []


@pytest.mark.asyncio
async def test_list_customers_invalid_payment_status():
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    mock_current_user.email = "admin@example.com"

    mock_db = AsyncMock()

    with patch(
        "app.api.modules.v1.admin.routes.customers.CustomerManagementService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.list_customers = AsyncMock(side_effect=Exception("Invalid status"))

        with pytest.raises(Exception):
            await list_customers(
                current_user=mock_current_user,
                db=mock_db,
                payment_status="invalid",
            )


@pytest.mark.asyncio
async def test_list_customers_data_retrieval_error():
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    mock_current_user.email = "admin@example.com"

    mock_db = AsyncMock()

    with patch(
        "app.api.modules.v1.admin.routes.customers.CustomerManagementService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.list_customers = AsyncMock(side_effect=Exception("Database error"))

        with pytest.raises(Exception):
            await list_customers(
                current_user=mock_current_user,
                db=mock_db,
                page=1,
                limit=20,
                payment_status=None,
                search=None,
                sort_by="created_at",
                sort_order="desc",
            )


@pytest.mark.asyncio
async def test_get_customer_detail_success():
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    mock_current_user.email = "admin@example.com"
    user_id = uuid.uuid4()

    mock_db = AsyncMock()

    mock_customer_data = {
        "profile": {
            "id": str(user_id),
            "name": "John Doe",
            "email": "john@example.com",
            "payment_status": "Paid",
        },
        "feature_usage": [{"feature": "scraping", "usage_count": 100}],
        "llm_usage": {"total_requests": 50, "total_cost_usd": 5.00},
        "parallel_usage": {"total_requests": 30, "total_cost_usd": 3.00},
    }

    with patch(
        "app.api.modules.v1.admin.routes.customers.CustomerManagementService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.get_customer_detail = AsyncMock(return_value=mock_customer_data)

        response = await get_customer_detail(
            user_id=user_id,
            current_user=mock_current_user,
            db=mock_db,
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK
        assert response_data["message"] == "Customer details retrieved successfully"
        assert response_data["data"]["profile"]["id"] == str(user_id)


@pytest.mark.asyncio
async def test_get_customer_detail_not_found():
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    mock_current_user.email = "admin@example.com"
    user_id = uuid.uuid4()

    mock_db = AsyncMock()

    with patch(
        "app.api.modules.v1.admin.routes.customers.CustomerManagementService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.get_customer_detail = AsyncMock(side_effect=Exception("Not found"))

        with pytest.raises(Exception):
            await get_customer_detail(
                user_id=user_id,
                current_user=mock_current_user,
                db=mock_db,
            )


@pytest.mark.asyncio
async def test_get_customer_activity_success():
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    mock_current_user.email = "admin@example.com"
    user_id = uuid.uuid4()

    mock_db = AsyncMock()

    mock_activity_data = {
        "user_id": str(user_id),
        "date_range": {
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-01-08T00:00:00Z",
            "days": 7,
        },
        "feature_usage": [{"feature": "scraping", "usage_count": 5}],
    }

    with patch(
        "app.api.modules.v1.admin.routes.customers.CustomerManagementService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.get_customer_activity = AsyncMock(return_value=mock_activity_data)

        response = await get_customer_activity(
            user_id=user_id,
            current_user=mock_current_user,
            db=mock_db,
            days=7,
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK
        assert (
            response_data["message"]
            == "Customer activity for the last 7 days retrieved successfully"
        )
        assert response_data["data"]["user_id"] == str(user_id)


@pytest.mark.asyncio
async def test_get_customer_activity_not_found():
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    mock_current_user.email = "admin@example.com"
    user_id = uuid.uuid4()

    mock_db = AsyncMock()

    with patch(
        "app.api.modules.v1.admin.routes.customers.CustomerManagementService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.get_customer_activity = AsyncMock(side_effect=Exception("Not found"))

        with pytest.raises(Exception):
            await get_customer_activity(
                user_id=user_id,
                current_user=mock_current_user,
                db=mock_db,
                days=7,
            )


@pytest.mark.asyncio
async def test_get_customer_activity_invalid_days():
    """Test get customer activity with invalid days parameter."""
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    mock_current_user.email = "admin@example.com"
    user_id = uuid.uuid4()

    mock_db = AsyncMock()

    with patch(
        "app.api.modules.v1.admin.routes.customers.CustomerManagementService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.get_customer_activity = AsyncMock(side_effect=Exception("Invalid days"))

        with pytest.raises(Exception):
            await get_customer_activity(
                user_id=user_id,
                current_user=mock_current_user,
                db=mock_db,
                days=100,
            )


@pytest.mark.asyncio
async def test_activate_customer_success():
    """Test successful customer activation."""
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    mock_current_user.email = "admin@example.com"
    user_id = uuid.uuid4()

    mock_db = AsyncMock()
    mock_background_tasks = MagicMock()

    mock_result = {
        "id": str(user_id),
        "email": "customer@example.com",
        "name": "Jane Smith",
        "is_approved": True,
        "approved_at": "2024-01-26T12:00:00+00:00",
    }

    with patch(
        "app.api.modules.v1.admin.routes.customers.CustomerManagementService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.activate_customer = AsyncMock(return_value=mock_result)

        response = await activate_customer(
            user_id=user_id,
            background_tasks=mock_background_tasks,
            current_user=mock_current_user,
            db=mock_db,
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK
        assert response_data["message"] == "Customer approved successfully"
        assert response_data["data"]["id"] == str(user_id)
        assert response_data["data"]["is_approved"] is True
        assert "approved_at" in response_data["data"]


@pytest.mark.asyncio
async def test_activate_customer_not_found():
    """Test activating a non-existent customer."""
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    mock_current_user.email = "admin@example.com"
    user_id = uuid.uuid4()

    mock_db = AsyncMock()
    mock_background_tasks = MagicMock()

    with patch(
        "app.api.modules.v1.admin.routes.customers.CustomerManagementService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.activate_customer = AsyncMock(
            side_effect=CustomerNotFoundError(f"Customer with ID {user_id} not found")
        )

        with pytest.raises(CustomerNotFoundError):
            await activate_customer(
                user_id=user_id,
                background_tasks=mock_background_tasks,
                current_user=mock_current_user,
                db=mock_db,
            )


@pytest.mark.asyncio
async def test_deactivate_customer_success():
    """Test successful customer deactivation."""
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    mock_current_user.email = "admin@example.com"
    user_id = uuid.uuid4()

    mock_db = AsyncMock()

    mock_result = {
        "id": str(user_id),
        "email": "customer@example.com",
        "name": "Jane Smith",
        "is_approved": False,
        "approved_at": None,
    }

    with patch(
        "app.api.modules.v1.admin.routes.customers.CustomerManagementService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.deactivate_customer = AsyncMock(return_value=mock_result)

        response = await deactivate_customer(
            user_id=user_id,
            current_user=mock_current_user,
            db=mock_db,
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK
        assert response_data["message"] == "Customer approval revoked successfully"
        assert response_data["data"]["id"] == str(user_id)
        assert response_data["data"]["is_approved"] is False


@pytest.mark.asyncio
async def test_deactivate_customer_not_found():
    """Test deactivating a non-existent customer."""
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    mock_current_user.email = "admin@example.com"
    user_id = uuid.uuid4()

    mock_db = AsyncMock()

    with patch(
        "app.api.modules.v1.admin.routes.customers.CustomerManagementService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.deactivate_customer = AsyncMock(
            side_effect=CustomerNotFoundError(f"Customer with ID {user_id} not found")
        )

        with pytest.raises(CustomerNotFoundError):
            await deactivate_customer(
                user_id=user_id,
                current_user=mock_current_user,
                db=mock_db,
            )


@pytest.mark.asyncio
async def test_activate_already_active_customer():
    """Test approving an already approved customer (idempotent)."""
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    mock_current_user.email = "admin@example.com"
    user_id = uuid.uuid4()

    mock_db = AsyncMock()
    mock_background_tasks = MagicMock()

    mock_result = {
        "id": str(user_id),
        "email": "customer@example.com",
        "name": "Jane Smith",
        "is_approved": True,
        "approved_at": "2024-01-26T12:00:00+00:00",
    }

    with patch(
        "app.api.modules.v1.admin.routes.customers.CustomerManagementService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.activate_customer = AsyncMock(return_value=mock_result)

        response = await activate_customer(
            user_id=user_id,
            background_tasks=mock_background_tasks,
            current_user=mock_current_user,
            db=mock_db,
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["data"]["is_approved"] is True


@pytest.mark.asyncio
async def test_deactivate_already_inactive_customer():
    """Test revoking approval for an already unapproved customer (idempotent)."""
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    mock_current_user.email = "admin@example.com"
    user_id = uuid.uuid4()

    mock_db = AsyncMock()

    mock_result = {
        "id": str(user_id),
        "email": "customer@example.com",
        "name": "Jane Smith",
        "is_approved": False,
        "approved_at": None,
    }

    with patch(
        "app.api.modules.v1.admin.routes.customers.CustomerManagementService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.deactivate_customer = AsyncMock(return_value=mock_result)

        response = await deactivate_customer(
            user_id=user_id,
            current_user=mock_current_user,
            db=mock_db,
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["data"]["is_approved"] is False
