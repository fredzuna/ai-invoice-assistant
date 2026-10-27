"""Minimal SQL migration runner: applies app/internal/migrations/*.sql once, in name order."""

import asyncio
from pathlib import Path

from psycopg_pool import AsyncConnectionPool

from app.config import get_settings
from app.internal.db import create_pool

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


async def migrate(pool: AsyncConnectionPool) -> list[str]:
    """Apply pending migrations and return the names that were applied."""
    applied_now: list[str] = []
    async with pool.connection() as conn:
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        cursor = await conn.execute("SELECT name FROM schema_migrations")
        already = {row["name"] for row in await cursor.fetchall()}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in already:
                continue
            async with conn.transaction():
                await conn.execute(path.read_text())
                await conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
            applied_now.append(path.name)
    return applied_now


async def _main() -> None:
    pool = await create_pool(get_settings().database_url, max_size=2)
    try:
        applied = await migrate(pool)
    finally:
        await pool.close()
    print(f"applied migrations: {', '.join(applied) if applied else 'none (up to date)'}")


if __name__ == "__main__":
    asyncio.run(_main())
