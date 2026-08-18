"""Vector store abstraction for semantic retrieval (Qdrant + in-memory fallback).

Embeddings are produced either by the NVIDIA NIM embedding endpoint (when an
API key is present) or by a deterministic local hashing embedder — which keeps
the retrieval pipeline fully functional offline.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from typing import Any, Protocol

from ..config import Settings
from ..log import get_logger

log = get_logger("storage.vector")

VECTOR_DIM = 384


class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...

    @property
    def dimension(self) -> int: ...


class HashEmbedder:
    """Deterministic, dependency-free bag-of-token hashing embedder."""

    def __init__(self, dimension: int = VECTOR_DIM) -> None:
        self._dim = dimension

    @property
    def dimension(self) -> int:
        return self._dim

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self._dim
            for token in _tokenize(text):
                digest = hashlib.md5(token.encode("utf-8")).digest()
                idx = int.from_bytes(digest[:4], "little") % self._dim
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                vec[idx] += sign
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vectors.append([v / norm for v in vec])
        return vectors


class NimEmbedder:
    """NVIDIA NIM embedding client (used when an API key is configured)."""

    def __init__(self, settings: Settings) -> None:
        import httpx

        self._settings = settings
        self._client = httpx.Client(timeout=settings.http_timeout_seconds)

    @property
    def dimension(self) -> int:
        return VECTOR_DIM

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        import json

        url = f"{self._settings.nim_base_url}/embeddings"
        headers = {"Authorization": f"Bearer {self._settings.nim_api_key_plain()}"}
        payload = {
            "input": list(texts),
            "model": self._settings.nim_model,
            "encoding_format": "float",
        }
        resp = self._client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = json.loads(resp.text)
        return [item["embedding"] for item in data["data"]]


class VectorStore(Protocol):
    def upsert(self, collection: str, ids: list[str], texts: list[str], payloads: list[dict[str, Any]]) -> None: ...

    def search(self, collection: str, text: str, limit: int = 5) -> list[dict[str, Any]]: ...


class QdrantVectorStore:
    """Real Qdrant store; falls back to an embedded local instance when no URL."""

    def __init__(self, settings: Settings, embedder: Embedder | None = None) -> None:
        from qdrant_client import QdrantClient

        self._settings = settings
        self._embedder = embedder or HashEmbedder()
        self._dim = self._embedder.dimension
        if settings.qdrant_url:
            self._client = QdrantClient(url=settings.qdrant_url)
        else:
            local_dir = settings.data_dir / "qdrant"
            local_dir.mkdir(parents=True, exist_ok=True)
            self._client = QdrantClient(path=str(local_dir))
        log.info("vector store ready", fields={"dim": self._dim, "url": settings.qdrant_url})

    def _ensure(self, collection: str) -> None:
        from qdrant_client.models import Distance, VectorParams

        try:
            self._client.get_collection(collection)
        except Exception:
            self._client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=self._dim, distance=Distance.COSINE),
            )

    def upsert(
        self,
        collection: str,
        ids: list[str],
        texts: list[str],
        payloads: list[dict[str, Any]],
    ) -> None:
        from qdrant_client.models import PointStruct

        self._ensure(collection)
        vectors = self._embedder.embed(texts)
        points = [
            PointStruct(id=i, vector=v, payload=p)
            for i, v, p in zip(ids, vectors, payloads, strict=True)
        ]
        if points:
            self._client.upsert(collection_name=collection, points=points)

    def search(self, collection: str, text: str, limit: int = 5) -> list[dict[str, Any]]:
        self._ensure(collection)
        vector = self._embedder.embed([text])[0]
        hits = self._client.search(collection_name=collection, query_vector=vector, limit=limit)
        return [
            {"id": h.id, "score": h.score, "payload": h.payload or {}}
            for h in hits
        ]


class InMemoryVectorStore:
    """Pure in-memory store used by tests; identical interface."""

    def __init__(self, embedder: Embedder | None = None) -> None:
        self._embedder = embedder or HashEmbedder()
        self._collections: dict[str, dict[str, tuple[list[float], dict[str, Any]]]] = {}

    def upsert(
        self,
        collection: str,
        ids: list[str],
        texts: list[str],
        payloads: list[dict[str, Any]],
    ) -> None:
        vectors = self._embedder.embed(texts)
        store = self._collections.setdefault(collection, {})
        for i, v, p in zip(ids, vectors, payloads, strict=True):
            store[i] = (v, p)

    def search(self, collection: str, text: str, limit: int = 5) -> list[dict[str, Any]]:
        vector = self._embedder.embed([text])[0]
        store = self._collections.get(collection, {})
        scored = []
        for pid, (vec, payload) in store.items():
            score = _cosine(vector, vec)
            scored.append((score, pid, payload))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"id": pid, "score": score, "payload": payload} for score, pid, payload in scored[:limit]]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


def _tokenize(text: str) -> list[str]:
    import re

    tokens = re.findall(r"[a-z0-9]+", text.lower())
    if not tokens:
        return [text.strip().lower() or "empty"]
    bigrams = [f"{tokens[i]}_{tokens[i + 1]}" for i in range(len(tokens) - 1)]
    return tokens + bigrams


def make_vector_store(settings: Settings) -> VectorStore:
    return QdrantVectorStore(settings)
