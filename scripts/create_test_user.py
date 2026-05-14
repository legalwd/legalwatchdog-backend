import asyncio

from sqlalchemy import text

from app.api.db.database import get_db
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.password import hash_password, verify_password


async def create_test_user():
    async for db in get_db():
        existing = await db.execute(text("SELECT id FROM users WHERE email = 'test@example.com'"))
        if existing.scalar():
            await db.execute(text("DELETE FROM users WHERE email = 'test@example.com'"))
            await db.commit()
            print("Deleted existing test user")

        hashed_password = hash_password("password123")
        print(f"Password hash generated: {hashed_password}")

        is_valid = verify_password("password123", hashed_password)
        print(f"Hash verification: {is_valid}")

        test_user = User(
            email="test@example.com",
            hashed_password=hashed_password,
            auth_provider="local",
            name="Test User",
            is_active=True,
            is_verified=True,
        )

        db.add(test_user)
        await db.commit()
        print("Test user created successfully!")
        print("Email: test@example.com")
        print("Password: password123")


if __name__ == "__main__":
    asyncio.run(create_test_user())
