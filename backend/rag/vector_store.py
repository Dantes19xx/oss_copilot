"""Qdrant-backed vector store for repo documentation chunks.

One shared collection, filtered by `repo` payload field per query, rather than one
collection per repo — simpler to operate and avoids collection sprawl as more repos
get indexed.
"""

import os
import uuid

from qdrant_client import AsyncQdrantClient, models

from backend.rag.embeddings import EMBEDDING_DIM

COLLECTION_NAME = "repo_docs"

_client: AsyncQdrantClient | None = None


def _get_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(url=os.environ.get("QDRANT_URL", "http://localhost:6333"))
    return _client


async def ensure_collection() -> None:
    client = _get_client()
    if not await client.collection_exists(COLLECTION_NAME):
        await client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(size=EMBEDDING_DIM, distance=models.Distance.COSINE),
        )


def _point_id(repo: str, source: str, index: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{repo}:{source}:{index}"))


async def upsert_chunks(repo: str, source: str, chunks: list[str], vectors: list[list[float]]) -> None:
    if not chunks:
        return
    await ensure_collection()
    points = [
        models.PointStruct(
            id=_point_id(repo, source, i),
            vector=vector,
            payload={"repo": repo, "source": source, "text": chunk},
        )
        for i, (chunk, vector) in enumerate(zip(chunks, vectors))
    ]
    await _get_client().upsert(collection_name=COLLECTION_NAME, points=points)


async def search(repo: str, query_vector: list[float], limit: int = 5) -> list[dict]:
    await ensure_collection()
    result = await _get_client().query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=models.Filter(must=[models.FieldCondition(key="repo", match=models.MatchValue(value=repo))]),
        limit=limit,
    )
    return [
        {"text": p.payload["text"], "source": p.payload["source"], "score": p.score}
        for p in result.points
    ]
