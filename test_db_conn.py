from sqlalchemy import create_engine, text


def test_sync_connection():
    url = "postgresql+psycopg2://postgres:password@localhost:5432/watchdog_test"
    print(f"Connecting to {url}...")
    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print(f"Sync Connection successful: {result.scalar()}")
        engine.dispose()
    except Exception as e:
        print(f"Sync Connection failed: {e}")


if __name__ == "__main__":
    test_sync_connection()
