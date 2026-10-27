from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


async def create_pool(
    database_url: str, *, max_size: int = 10, search_path: str | None = None
) -> AsyncConnectionPool:
    """Open an async pool. Connections are autocommit; use conn.transaction() for writes."""
    kwargs: dict = {"autocommit": True, "row_factory": dict_row}
    if search_path:
        kwargs["options"] = f"-c search_path={search_path}"
    pool = AsyncConnectionPool(
        database_url, min_size=1, max_size=max_size, kwargs=kwargs, open=False
    )
    await pool.open(wait=True, timeout=30)
    return pool


def vector_literal(values: list[float]) -> str:
    """Render a list of floats as a pgvector text literal, e.g. '[0.1,0.2]'."""
    return "[" + ",".join(f"{v:.6f}" for v in values) + "]"
