"""Markdown chunking: split by headers first (keeps semantically related content
together), then fall back to fixed-size token windows with overlap for any section
that's still too large for one embedding call."""

import re

import tiktoken

_ENCODING = tiktoken.get_encoding("cl100k_base")
CHUNK_SIZE_TOKENS = 500
CHUNK_OVERLAP_TOKENS = 50

_HEADER_RE = re.compile(r"^#{1,6}\s")


def _split_by_headers(markdown: str) -> list[str]:
    sections: list[str] = []
    current: list[str] = []
    for line in markdown.splitlines():
        if _HEADER_RE.match(line) and current:
            sections.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("\n".join(current))
    return [s.strip() for s in sections if s.strip()]


def _split_fixed(text: str) -> list[str]:
    tokens = _ENCODING.encode(text)
    if len(tokens) <= CHUNK_SIZE_TOKENS:
        return [text]
    chunks = []
    start = 0
    while start < len(tokens):
        end = start + CHUNK_SIZE_TOKENS
        chunks.append(_ENCODING.decode(tokens[start:end]))
        if end >= len(tokens):
            break
        start = end - CHUNK_OVERLAP_TOKENS
    return chunks


def chunk_markdown(text: str) -> list[str]:
    sections = _split_by_headers(text) or [text]
    chunks: list[str] = []
    for section in sections:
        chunks.extend(_split_fixed(section))
    return [c for c in chunks if c.strip()]
