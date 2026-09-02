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

        try:
            print("Ensuring search_vector exists on knowledge_article table...")
            if conn.dialect.name == "postgresql":
                await conn.execute(text("ALTER TABLE knowledge_article ADD COLUMN IF NOT EXISTS search_vector TSVECTOR;"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_knowledge_article_search_vector ON knowledge_article USING gin(search_vector);"))
            else:
                await conn.execute(text("ALTER TABLE knowledge_article ADD COLUMN search_vector TEXT;"))
            print("KnowledgeArticle table verified.")
        except Exception as e:
            print(f"Note on search_vector column: {e}")

        try:
            print("Ensuring sla_breached exists on ticket table...")
            if conn.dialect.name == "postgresql":
                await conn.execute(text("ALTER TABLE ticket ADD COLUMN IF NOT EXISTS sla_breached BOOLEAN DEFAULT FALSE;"))
            else:
                await conn.execute(text("ALTER TABLE ticket ADD COLUMN sla_breached BOOLEAN DEFAULT 0;"))
            print("Ticket sla_breached column verified.")
        except Exception as e:
            print(f"Note on sla_breached column: {e}")

if __name__ == "__main__":
    asyncio.run(main())
