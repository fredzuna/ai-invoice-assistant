import httpx

from app.clients.errors import UpstreamError
from app.middleware.metrics import record_embed_call


class EmbeddingClient:
    """Async client for the embedding service. One HTTP call embeds a whole batch."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def embed(self, texts: list[str]) -> list[list[float]]:
        record_embed_call()
        try:
            response = await self._client.post("/v1/embeddings", json={"input": texts})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise UpstreamError(f"embedding service failed: {exc!r}") from exc
        data = sorted(response.json()["data"], key=lambda item: item["index"])
        return [item["embedding"] for item in data]
