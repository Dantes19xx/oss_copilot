"""In-process MCP client bridge: lets LangGraph nodes call the project's own MCP server
tools through the real MCP protocol (Client -> MCPServer), rather than importing the
tool functions directly."""

import json
from typing import Any

from mcp import Client

from backend.mcp_server.server import mcp


class ToolCallError(RuntimeError):
    """Raised when an MCP tool call itself reports failure (result.is_error=True) —
    e.g. a GitHubError raised inside the tool. Distinct from a malformed result, so
    callers that expect specific failures (like an unmergeable PR) can catch it."""


async def call_tool(name: str, arguments: dict[str, Any]) -> Any:
    async with Client(mcp) as client:
        result = await client.call_tool(name, arguments)

    if result.is_error:
        message = result.content[0].text if result.content and result.content[0].type == "text" else str(result)
        raise ToolCallError(f"tool '{name}' failed: {message}")

    structured = result.structured_content
    if isinstance(structured, dict) and set(structured.keys()) == {"result"}:
        return structured["result"]
    if structured is not None:
        return structured

    # Bare `dict` return annotations don't get a structured-content schema; the payload
    # is still valid JSON in the first text block, so fall back to parsing it.
    if result.content and result.content[0].type == "text":
        return json.loads(result.content[0].text)
    return None
