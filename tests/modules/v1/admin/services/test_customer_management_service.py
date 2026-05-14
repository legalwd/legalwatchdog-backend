import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.core.custom_exceptions.exceptions import (
    CustomerDataRetrievalError,
    CustomerNotFoundError,
    InvalidCustomerFilterError,
    PaymentStatusError,
)
from app.api.modules.v1.admin.services.customer_management_service import (
    CustomerManagementService,
)


class MockScalarsResult:
    """Mock class to simulate result.scalars().all() behavior."""

    def __init__(self, items):
        self.items = items

    def all(self):
        return self.items


class MockExecuteResult:
    """Mock class to simulate db.execute() behavior."""

    def __init__(self, scalar=None, scalars_items=None, fetchone_result=None):
        self.scalar_value = scalar
        self.scalars_items = scalars_items
        self.fetchone_result = fetchone_result

    def scalar(self):
        return self.scalar_value

    def scalars(self):
        return MockScalarsResult(self.scalars_items)

    def fetchone(self):
        return self.fetchone_result


@pytest.mark.asyncio
async def test_list_customers_success():
    mock_db = AsyncMock()

    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.name = "John Doe"
    mock_user.email = "john@example.com"
    mock_user.created_at = datetime.now(timezone.utc)
    mock_user.last_active = datetime.now(timezone.utc)

    # Set up mock execute to return MockExecuteResult
    async def execute_side_effect(query):
        if "COUNT" in str(query):
            return MockExecuteResult(scalar=1)
        return MockExecuteResult(scalars_items=[mock_user])

    mock_db.execute.side_effect = execute_side_effect

    mock_nested = MagicMock()
    mock_nested.__aenter__ = AsyncMock(return_value=None)
    mock_nested.__aexit__ = AsyncMock(return_value=None)
    mock_db.begin_nested = MagicMock(return_value=mock_nested)

    service = CustomerManagementService(mock_db)

    with patch.object(
        service,
        "_get_user_with_payment_status",
        AsyncMock(
            return_value={
                "id": str(mock_user.id),
                "name": "John Doe",
                "email": "john@example.com",
                "payment_status": "paid",
                "registration_date": "2024-01-15T10:00:00Z",
                "last_active": "2024-02-10T15:30:00Z",
                "credits_used": 50000,
                "amount_spent": 150.00,
            }
        ),
    ):
        result = await service.list_customers()

    assert "data" in result
    assert "meta" in result
    assert "total" in result
    assert len(result["data"]["customers"]) == 1
    assert result["data"]["customers"][0]["name"] == "John Doe"
    assert result["data"]["customers"][0]["payment_status"] == "paid"


@pytest.mark.asyncio
async def test_list_customers_with_payment_status_filter():
    mock_db = AsyncMock()

    # Set up mock execute to return MockExecuteResult
    async def execute_side_effect(query):
        if "COUNT" in str(query):
            return MockExecuteResult(scalar=0)
        return MockExecuteResult(scalars_items=[])

    mock_db.execute.side_effect = execute_side_effect

    service = CustomerManagementService(mock_db)

    with patch.object(service, "_get_user_with_payment_status", AsyncMock()):
        result = await service.list_customers(payment_status="paid")

    assert result["data"]["customers"] == []
    assert result["total"] == 0


@pytest.mark.asyncio
async def test_list_customers_with_search_filter():
    mock_db = AsyncMock()

    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.name = "John Doe"
    mock_user.email = "john@example.com"

    async def execute_side_effect(query):
        if "COUNT" in str(query):
            return MockExecuteResult(scalar=1)
        return MockExecuteResult(scalars_items=[mock_user])

    mock_db.execute.side_effect = execute_side_effect

    mock_nested = MagicMock()
    mock_nested.__aenter__ = AsyncMock(return_value=None)
    mock_nested.__aexit__ = AsyncMock(return_value=None)
    mock_db.begin_nested = MagicMock(return_value=mock_nested)

    service = CustomerManagementService(mock_db)

    with patch.object(
        service,
        "_get_user_with_payment_status",
        AsyncMock(
            return_value={
                "id": str(mock_user.id),
                "name": "John Doe",
                "email": "john@example.com",
                "payment_status": "paid",
                "credits_used": 50000,
                "amount_spent": 150.00,
            }
        ),
    ):
        result = await service.list_customers(search="john")

    assert len(result["data"]["customers"]) == 1
    assert result["data"]["customers"][0]["name"] == "John Doe"


@pytest.mark.asyncio
async def test_list_customers_invalid_payment_status():
    mock_db = AsyncMock()
    service = CustomerManagementService(mock_db)

    with pytest.raises(PaymentStatusError):
        await service.list_customers(payment_status="invalid_status")


@pytest.mark.asyncio
async def test_list_customers_invalid_sort_field():
    mock_db = AsyncMock()
    service = CustomerManagementService(mock_db)

    with pytest.raises(InvalidCustomerFilterError):
        await service.list_customers(sort_by="invalid_field")


@pytest.mark.asyncio
async def test_list_customers_invalid_sort_order():
    mock_db = AsyncMock()
    service = CustomerManagementService(mock_db)

    with pytest.raises(InvalidCustomerFilterError):
        await service.list_customers(sort_order="invalid")


@pytest.mark.asyncio
async def test_list_customers_data_retrieval_error():
    mock_db = AsyncMock()
    mock_db.execute.side_effect = Exception("Database error")

    service = CustomerManagementService(mock_db)

    with pytest.raises(CustomerDataRetrievalError):
        await service.list_customers()


@pytest.mark.asyncio
async def test_get_user_with_payment_status_success():
    mock_db = AsyncMock()
    user_id = uuid.uuid4()

    class MockRow:
        def __init__(self):
            self.id = user_id
            self.name = "John Doe"
            self.email = "john@example.com"
            self.created_at = datetime.now(timezone.utc)
            self.last_active = datetime.now(timezone.utc)
            self.is_approved = True
            self.payment_status = "ACTIVE"
            self.plan_tier = None
            self.plan_label = None
            self.plan_interval = None
            self.plan_amount = None

    mock_row = MockRow()

    async def execute_side_effect(query):
        query_str = str(query)
        if "users.id" in query_str or ("SELECT" in query_str and "users.name" in query_str):
            return MockExecuteResult(fetchone_result=mock_row)
        elif "total_tokens" in query_str:
            return MockExecuteResult(scalar=50000)
        elif "cost_usd" in query_str:
            return MockExecuteResult(scalar=0.025)
        else:
            return MockExecuteResult(scalar=None, scalars_items=[])

    mock_db.execute.side_effect = execute_side_effect

    service = CustomerManagementService(mock_db)

    with patch.object(service, "_get_user_organization_ids", AsyncMock(return_value=[])):
        result = await service._get_user_with_payment_status(user_id)

    assert result["id"] == str(user_id)
    assert result["name"] == "John Doe"
    assert result["email"] == "john@example.com"
    assert result["is_approved"] is True
    assert result["payment_status"] == "paid"
    assert result["credits_used"] == 50000
    assert result["amount_spent"] == 0.025


@pytest.mark.asyncio
async def test_get_user_with_payment_status_not_found():
    mock_db = AsyncMock()
    user_id = uuid.uuid4()

    mock_db.execute.return_value = MockExecuteResult(fetchone_result=None)

    service = CustomerManagementService(mock_db)

    with pytest.raises(CustomerNotFoundError):
        await service._get_user_with_payment_status(user_id)


@pytest.mark.asyncio
async def test_get_user_with_payment_status_database_error():
    mock_db = AsyncMock()
    user_id = uuid.uuid4()

    mock_db.execute.side_effect = Exception("Database error")

    service = CustomerManagementService(mock_db)

    with patch.object(service, "_get_user_organization_ids", AsyncMock(return_value=[])):
        with pytest.raises(Exception, match="Database error"):
            await service._get_user_with_payment_status(user_id)


@pytest.mark.asyncio
async def test_get_customer_detail_success():
    mock_db = AsyncMock()
    user_id = uuid.uuid4()

    service = CustomerManagementService(mock_db)

    with patch.object(
        service,
        "_get_user_with_payment_status",
        AsyncMock(
            return_value={
                "id": str(user_id),
                "name": "John Doe",
                "email": "john@example.com",
                "payment_status": "paid",
                "credits_used": 50000,
                "amount_spent": 150.00,
            }
        ),
    ):
        with patch.object(
            service,
            "get_feature_usage_breakdown",
            AsyncMock(
                return_value=[
                    {
                        "feature": "AI Source Extraction",
                        "credits_used": 30000,
                        "usage_count": 100,
                    }
                ]
            ),
        ):
            with patch.object(service, "_get_user_organization_ids", AsyncMock(return_value=[])):
                with patch(
                    "app.api.core.llm.usage_tracker.LLMUsageTracker.get_usage_stats",
                    new_callable=AsyncMock,
                ) as mock_llm:
                    mock_llm.return_value = {
                        "total_requests": 50,
                        "total_cost_usd": 5.00,
                        "total_tokens": 25000,
                    }

                    with patch(
                        "app.api.core.parallel.usage_tracker.ParallelUsageTracker.get_usage_stats",
                        new_callable=AsyncMock,
                    ) as mock_parallel:
                        mock_parallel.return_value = {
                            "total_requests": 30,
                            "total_cost_usd": 3.00,
                            "total_content_mb": 15.5,
                        }

                        result = await service.get_customer_detail(user_id)

    assert "profile" in result
    assert "feature_usage" in result
    assert "llm_usage" in result
    assert "parallel_usage" in result
    assert result["profile"]["id"] == str(user_id)
    assert result["llm_usage"]["total_requests"] == 50
    assert result["parallel_usage"]["total_content_mb"] == 15.5


@pytest.mark.asyncio
async def test_get_customer_detail_user_not_found():
    mock_db = AsyncMock()
    user_id = uuid.uuid4()

    service = CustomerManagementService(mock_db)

    with patch.object(
        service,
        "_get_user_with_payment_status",
        AsyncMock(side_effect=CustomerNotFoundError("Customer not found")),
    ):
        with pytest.raises(CustomerNotFoundError):
            await service.get_customer_detail(user_id)


@pytest.mark.asyncio
async def test_get_customer_activity_success():
    mock_db = AsyncMock()
    user_id = uuid.uuid4()

    service = CustomerManagementService(mock_db)

    with patch.object(
        service,
        "_get_user_with_payment_status",
        AsyncMock(
            return_value={
                "id": str(user_id),
                "name": "John Doe",
                "email": "john@example.com",
                "payment_status": "paid",
            }
        ),
    ):
        with patch.object(
            service,
            "get_feature_usage_breakdown",
            AsyncMock(
                return_value=[
                    {"feature": "AI Source Extraction", "credits_used": 5000, "usage_count": 50}
                ]
            ),
        ):
            result = await service.get_customer_activity(user_id, days=7)

    assert "user_id" in result
    assert "date_range" in result
    assert "feature_usage" in result
    assert result["user_id"] == str(user_id)
    assert result["date_range"]["days"] == 7
    assert len(result["feature_usage"]) == 1


@pytest.mark.asyncio
async def test_get_customer_activity_invalid_days():
    mock_db = AsyncMock()
    user_id = uuid.uuid4()

    service = CustomerManagementService(mock_db)

    with pytest.raises(InvalidCustomerFilterError):
        await service.get_customer_activity(user_id, days=100)


@pytest.mark.asyncio
async def test_get_customer_activity_user_not_found():
    mock_db = AsyncMock()
    user_id = uuid.uuid4()

    service = CustomerManagementService(mock_db)

    with patch.object(
        service,
        "_get_user_with_payment_status",
        AsyncMock(side_effect=CustomerNotFoundError("Customer not found")),
    ):
        with pytest.raises(CustomerNotFoundError):
            await service.get_customer_activity(user_id, days=7)


@pytest.mark.asyncio
async def test_get_feature_usage_breakdown():
    mock_db = AsyncMock()
    user_id = uuid.uuid4()

    service = CustomerManagementService(mock_db)

    with patch.object(service, "_get_user_organization_ids", AsyncMock(return_value=[])):
        with patch(
            "app.api.modules.v1.admin.services.superadmin_metrics_service.SuperadminMetricsService.get_feature_usage_breakdown",
            new_callable=AsyncMock,
        ) as mock_feature_usage:
            mock_feature_usage.return_value = [
                {
                    "feature": "AI Source Extraction",
                    "credits_used": 30000,
                    "usage_count": 100,
                }
            ]

            result = await service.get_feature_usage_breakdown(user_id)

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["feature"] == "AI Source Extraction"
    assert result[0]["credits_used"] == 30000
    assert result[0]["usage_count"] == 100


@pytest.mark.asyncio
async def test_get_llm_usage_success():
    mock_db = AsyncMock()
    user_id = uuid.uuid4()

    service = CustomerManagementService(mock_db)

    with patch.object(service, "_get_user_organization_ids", AsyncMock(return_value=[])):
        with patch(
            "app.api.core.llm.usage_tracker.LLMUsageTracker.get_usage_stats",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_llm.return_value = {
                "total_requests": 100,
                "total_cost_usd": 10.00,
                "total_tokens": 50000,
            }

            result = await service._get_llm_usage(user_id)

    assert result["total_requests"] == 100
    assert result["total_cost_usd"] == 10.00
    assert result["total_tokens"] == 50000


@pytest.mark.asyncio
async def test_get_llm_usage_error():
    mock_db = AsyncMock()
    user_id = uuid.uuid4()

    service = CustomerManagementService(mock_db)

    with patch(
        "app.api.core.llm.usage_tracker.LLMUsageTracker.get_usage_stats",
        new_callable=AsyncMock,
        side_effect=Exception("LLM service error"),
    ):
        result = await service._get_llm_usage(user_id)

    assert result["total_requests"] == 0
    assert result["total_cost_usd"] == 0.0
    assert result["total_tokens"] == 0


@pytest.mark.asyncio
async def test_get_parallel_usage_success():
    mock_db = AsyncMock()
    user_id = uuid.uuid4()

    service = CustomerManagementService(mock_db)

    with patch.object(service, "_get_user_organization_ids", AsyncMock(return_value=[])):
        with patch(
            "app.api.core.parallel.usage_tracker.ParallelUsageTracker.get_usage_stats",
            new_callable=AsyncMock,
        ) as mock_parallel:
            mock_parallel.return_value = {
                "total_requests": 50,
                "total_cost_usd": 5.00,
                "total_content_mb": 25.5,
            }

            result = await service._get_parallel_usage(user_id)

    assert result["total_requests"] == 50
    assert result["total_cost_usd"] == 5.00
    assert result["total_content_mb"] == 25.5


@pytest.mark.asyncio
async def test_get_parallel_usage_error():
    mock_db = AsyncMock()
    user_id = uuid.uuid4()

    service = CustomerManagementService(mock_db)

    with patch(
        "app.api.core.parallel.usage_tracker.ParallelUsageTracker.get_usage_stats",
        new_callable=AsyncMock,
        side_effect=Exception("Parallel service error"),
    ):
        result = await service._get_parallel_usage(user_id)

    assert result["total_requests"] == 0
    assert result["total_cost_usd"] == 0.0
    assert result["total_content_mb"] == 0.0
