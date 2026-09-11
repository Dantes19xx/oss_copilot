import os

from langsmith import traceable
from openai import AsyncOpenAI

from backend.graph.cache import FileCache

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

_client: AsyncOpenAI | None = None
_cache = FileCache("embeddings")


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client


@traceable(run_type="embedding", name="text-embedding-3-small")
async def _embed_uncached(texts: list[str]) -> list[list[float]]:
    # langchain_openai's OpenAIEmbeddings does NOT get auto-traced by LangSmith (it's
    # not a Runnable) — @traceable makes this call show up in the dashboard like every
    # other LLM call in the project instead of being a silent gap. See PROGRESS.md stage 8.
    # Only ever called on a cache miss — a cache hit means no API call happened, so it
    # correctly doesn't get a trace entry either.
    client = _get_client()
    response = await client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embeddings are a pure deterministic function of (model, text) — unlike
    review_file(), there's no reproducibility concern a cache could mask, so caching
    here is unconditional. Cached per-text (not per-batch call) so a batch with some
    already-seen texts still only pays for the new ones — this is the common case:
    retrieve_style_context() re-embeds the exact same fixed query string on every
    single review run for a given repo (see backend/graph/nodes_review.py)."""
    if not texts:
        return []
    keys = [(EMBEDDING_MODEL, text) for text in texts]
    results: list[list[float] | None] = [_cache.get(key) for key in keys]

    missing_indices = [i for i, r in enumerate(results) if r is None]
    if missing_indices:
        fetched = await _embed_uncached([texts[i] for i in missing_indices])
        for idx, vector in zip(missing_indices, fetched):
            results[idx] = vector
            _cache.set(keys[idx], vector)

    return results  # type: ignore[return-value]
