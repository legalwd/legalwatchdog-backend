import pytest
from sqlmodel import Field, SQLModel, select


class TestUser(SQLModel, table=True):
    __test__ = False
    id: int | None = Field(default=None, primary_key=True)
    name: str


@pytest.mark.asyncio
async def test_database_write_and_read(pg_async_session):
    """Test writing and reading a TestUser from the database."""

    session = pg_async_session

    user = TestUser(name="John Doe")
    session.add(user)
    await session.commit()

    result = await session.exec(select(TestUser))
    saved_user = result.first()

    assert saved_user is not None
    assert saved_user.name == "John Doe"
