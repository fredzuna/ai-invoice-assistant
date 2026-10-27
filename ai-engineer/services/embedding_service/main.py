"""Embedding service simulation.

Deterministic embeddings built by hashing character n-grams into a fixed-size,
L2-normalised vector. Every call takes ~150 ms, like a real hosted provider.
"""

import asyncio
import hashlib
import math
import os
import re
from collections import Counter

from fastapi import FastAPI
from pydantic import BaseModel, Field

DIM = 512
NGRAM_SIZES = (3, 4)
LATENCY_S = int(os.environ.get("EMBEDDING_LATENCY_MS", "150")) / 1000
MODEL_NAME = f"hash-ngram-{DIM}"

app = FastAPI(title="embedding-service")


class EmbeddingRequest(BaseModel):
    input: list[str] = Field(min_length=1, max_length=256)


def embed_text(text: str) -> list[float]:
    normalized = " " + re.sub(r"[^a-z0-9]+", " ", text.lower()).strip() + " "
    counts: Counter[tuple[int, int]] = Counter()
    for n in NGRAM_SIZES:
        for i in range(len(normalized) - n + 1):
            digest = hashlib.blake2b(normalized[i : i + n].encode(), digest_size=8).digest()
            value = int.from_bytes(digest, "big")
            sign = 1 if (value >> 40) & 1 else -1
            counts[(value % DIM, sign)] += 1

    vector = [0.0] * DIM
    for (index, sign), count in counts.items():
        vector[index] += sign * (1.0 + math.log(count))
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [round(v / norm, 6) for v in vector]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/embeddings")
async def embeddings(body: EmbeddingRequest) -> dict:
    await asyncio.sleep(LATENCY_S)
    return {
        "model": MODEL_NAME,
        "dim": DIM,
        "data": [{"index": i, "embedding": embed_text(t)} for i, t in enumerate(body.input)],
    }
