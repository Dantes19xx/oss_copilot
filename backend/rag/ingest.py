"""Index a repo's README.md / CONTRIBUTING.md into the shared Qdrant collection so
review/repo-matching prompts can be grounded in the project's own conventions.

Usage: PYTHONPATH=. python -m backend.rag.ingest <owner> <repo>
"""

import asyncio
import sys

from backend.mcp_server.github_client import GitHubClient
from backend.rag.chunking import chunk_markdown
from backend.rag.embeddings import embed_texts
from backend.rag.vector_store import upsert_chunks

DOC_PATHS = ["README.md", "CONTRIBUTING.md"]


async def ingest_repo_docs(owner: str, repo: str) -> dict:
    client = GitHubClient()
    full_name = f"{owner}/{repo}"
    ingested_sources = []
    total_chunks = 0

    for path in DOC_PATHS:
        content = await client.get_file_content(owner, repo, path)
        if not content:
            continue
        chunks = chunk_markdown(content)
        if not chunks:
            continue
        vectors = await embed_texts(chunks)
        await upsert_chunks(full_name, path, chunks, vectors)
        ingested_sources.append(path)
        total_chunks += len(chunks)

    return {"repo": full_name, "sources": ingested_sources, "chunks": total_chunks}


async def _main() -> None:
    owner, repo = sys.argv[1], sys.argv[2]
    result = await ingest_repo_docs(owner, repo)
    print(result)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv(override=True)
    asyncio.run(_main())
