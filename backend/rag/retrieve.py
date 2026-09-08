from backend.rag.embeddings import embed_texts
from backend.rag.vector_store import search


async def retrieve_context(owner: str, repo: str, query: str, limit: int = 5) -> list[dict]:
    full_name = f"{owner}/{repo}"
    [vector] = await embed_texts([query])
    return await search(full_name, vector, limit=limit)
