"""Ingest a local PDF or DOCX style guide into the SAME RAG collection
backend/rag/ingest.py uses for a repo's README/CONTRIBUTING — the review pipeline
retrieves from one shared collection (backend/rag/vector_store.py) filtered by repo, so
a chunk from an uploaded style guide is grounded into `analyze_file`'s review prompt
exactly the same way a README chunk already is, with zero changes to retrieval or the
graph. This is the "style-guide personalization" idea from PLAN.md §5, actually built:
a team can upload their own internal coding-standards document (a PDF or DOCX,
company style guides are rarely committed as a repo file) and have reviews grounded in
it, not just whatever happens to be in the target repo's own CONTRIBUTING.md.

Usage: PYTHONPATH=. python -m backend.rag.document_ingest <owner> <repo> <path/to/file.pdf|.docx>
"""

import asyncio
import sys
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from backend.rag.chunking import chunk_document
from backend.rag.embeddings import embed_texts
from backend.rag.vector_store import upsert_chunks

SUPPORTED_SUFFIXES = {".pdf", ".docx"}


def _extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx_text(path: Path) -> str:
    doc = Document(str(path))
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf_text(path)
    if suffix == ".docx":
        return _extract_docx_text(path)
    raise ValueError(f"Unsupported document type {suffix!r} — expected one of {sorted(SUPPORTED_SUFFIXES)}")


async def ingest_document(owner: str, repo: str, path: Path) -> dict:
    full_name = f"{owner}/{repo}"
    text = extract_text(path)
    chunks = chunk_document(text)
    if not chunks:
        return {"repo": full_name, "source": path.name, "chunks": 0}

    vectors = await embed_texts(chunks)
    await upsert_chunks(full_name, path.name, chunks, vectors)
    return {"repo": full_name, "source": path.name, "chunks": len(chunks)}


async def _main() -> None:
    owner, repo, file_path = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    result = await ingest_document(owner, repo, file_path)
    print(result)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv(override=True)
    asyncio.run(_main())
