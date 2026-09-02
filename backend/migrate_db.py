import asyncio
from sqlalchemy import text
from app.db.session import engine
from app.db.base import Base
# Import all models so metadata is complete
import app.models  # noqa: F401

async def main():
    async with engine.begin() as conn:
        try:
            print("Enabling vector extension...")
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            print("Vector extension ready.")
        except Exception as e:
            print(f"Note on vector extension: {e}")

        try:
            print("Creating all tables in Base.metadata...")
            await conn.run_sync(Base.metadata.create_all)
            print("Tables created successfully.")
        except Exception as e:
            print(f"Error creating tables: {e}")

        try:
            print("Ensuring ai_metadata exists on ticket table...")
            await conn.execute(text("ALTER TABLE ticket ADD COLUMN IF NOT EXISTS ai_metadata JSONB;"))
            print("Ticket table verified.")
        except Exception as e:
            print(f"Note on ticket column: {e}")

if __name__ == "__main__":
    asyncio.run(main())
