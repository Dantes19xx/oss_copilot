import os

from langsmith import traceable
from openai import AsyncOpenAI

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client


@traceable(run_type="embedding", name="text-embedding-3-small")
async def embed_texts(texts: list[str]) -> list[list[float]]:
    # langchain_openai's OpenAIEmbeddings does NOT get auto-traced by LangSmith (it's
    # not a Runnable) — @traceable makes this call show up in the dashboard like every
    # other LLM call in the project instead of being a silent gap. See PROGRESS.md stage 8.
    if not texts:
        return []
    client = _get_client()
    response = await client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]
