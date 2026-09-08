"""Vision analysis of screenshots/diagrams attached to a PR description.

Meaningful use case: PR bodies for UI changes commonly include a before/after
screenshot or a short demo GIF. Reading it lets the review catch things a text-only
diff can't — a broken layout, an error toast, a UI element that doesn't match what the
PR claims to do — the way a human reviewer would actually look at the screenshot.
"""

import re

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

_MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\((https?://\S+?)\)")
_HTML_IMG_RE = re.compile(r'<img[^>]+src=["\'](https?://[^"\']+)["\']', re.IGNORECASE)
_IMAGE_EXT_RE = re.compile(r"\.(png|jpe?g|gif|webp)(\?\S*)?$", re.IGNORECASE)
_ASSET_HOST_RE = re.compile(r"(user-images\.githubusercontent\.com|github\.com/[^\s]+/assets/)")

VISION_PROMPT = """You are reviewing an image attached to a GitHub pull request \
description (a before/after screenshot or short demo). Describe what it shows in 1-3 \
sentences, and flag anything that looks like a visual bug, broken layout, error \
message, or inconsistency with what a typical UI review would catch. If nothing looks \
wrong, say so briefly instead of inventing issues."""


def extract_image_urls(text: str | None, limit: int = 3) -> list[str]:
    if not text:
        return []
    urls = _MARKDOWN_IMAGE_RE.findall(text) + _HTML_IMG_RE.findall(text)
    seen: list[str] = []
    for url in urls:
        if url not in seen and (_IMAGE_EXT_RE.search(url) or _ASSET_HOST_RE.search(url)):
            seen.append(url)
    return seen[:limit]


async def analyze_image(url: str) -> str:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    message = HumanMessage(
        content=[
            {"type": "text", "text": VISION_PROMPT},
            {"type": "image_url", "image_url": {"url": url}},
        ]
    )
    result = await llm.ainvoke([message])
    return result.content
