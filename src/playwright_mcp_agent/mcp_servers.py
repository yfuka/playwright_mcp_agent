"""MCP server management for Playwright and Chrome DevTools.

This module defines:

- :class:`MCPServer` dataclass for tracking each MCP server.
- :data:`RAW_CONFIG` for server commands and arguments.
- :func:`build_servers` to materialize :class:`MCPServer` objects.
- :func:`init_servers` to spawn all MCP servers and collect their tools.
- :func:`dispatch_tool_call` to route LLM tool calls to the right server.
"""

from __future__ import annotations

import json
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

TOOL_SEPARATOR = "__"


@dataclass
class MCPServer:
    """Metadata and session holder for a single MCP server.

    Attributes:
        name: Logical server name (for example, ``"playwright"`` or
            ``"chromedev"``).
        command: Executable used to start the MCP server (for example,
            ``"npx"``).
        args: List of command-line arguments passed to :attr:`command`.
        env: Optional mapping of environment variables to inject when
            starting the server process.
        session: Active :class:`mcp.ClientSession` instance. This is
            populated by :func:`init_servers`.
    """

    name: str
    command: str
    args: List[str]
    env: Optional[Dict[str, str]] = None
    session: Optional[ClientSession] = None


# Official config examples for Playwright MCP and Chrome DevTools MCP use
# "npx @playwright/mcp@latest" and "npx -y chrome-devtools-mcp@latest"
# respectively. 
RAW_CONFIG: Dict[str, dict] = {
    "playwright": {
        "command": "npx",
        "args": [
            "@playwright/mcp@latest",
            "--output-dir=./playwright-artifacts",
            "--save-trace",
            "--save-session"
            # "--save-video", # ビデオ録画を有効にするオプション（エラーになるためコメントアウト）
            # "--isolated", # プロファイルをメモリ上だけに保存し、ディスクに残さない             
        ],
    },
}


def build_servers(raw: Dict[str, dict]) -> Dict[str, MCPServer]:
    """Build :class:`MCPServer` instances from a raw configuration map.

    Args:
        raw: A mapping from a logical server name to a configuration
            dictionary. Each configuration must contain at least
            ``"command"`` and ``"args"`` keys.

    Returns:
        Dict[str, MCPServer]: A mapping from server name to an
        instantiated :class:`MCPServer`.
    """
    servers: Dict[str, MCPServer] = {}
    for name, cfg in raw.items():
        servers[name] = MCPServer(
            name=name,
            command=cfg["command"],
            args=cfg.get("args", []),
            env=cfg.get("env"),
        )
    return servers


def mcp_tool_to_openai_tool(tool: types.Tool, server_name: str) -> dict:
    """Convert an MCP :class:`Tool` to an OpenAI tools entry.

    The returned dictionary can be passed to the OpenAI
    ``chat.completions.create(..., tools=[...])`` call.

    The tool name is made unique by prefixing it with the MCP server name
    and a separator (for example, ``\"playwright__navigate\"``).

    Args:
        tool: Tool definition from an MCP server.
        server_name: Logical name of the server exposing the tool.

    Returns:
        dict: A single tools entry in the OpenAI function-calling format.
    """
    unique_name = f"{server_name}{TOOL_SEPARATOR}{tool.name}"
    return {
        "type": "function",
        "function": {
            "name": unique_name,
            "description": tool.description or "",
            "parameters": tool.inputSchema
            or {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    }


async def init_servers(
    stack: AsyncExitStack,
    servers: Dict[str, MCPServer],
) -> List[dict]:
    """Initialize all MCP servers and collect their tools.

    This function performs the following steps for each MCP server:

    1. Start the MCP server process using :mod:`mcp.client.stdio`.
    2. Create and store a :class:`ClientSession` on the
       :class:`MCPServer`.
    3. Run the MCP initialization handshake.
    4. Query the server for its tools via :meth:`ClientSession.list_tools`.
    5. Convert each MCP tool into an OpenAI tools entry using
       :func:`mcp_tool_to_openai_tool`.

    Args:
        stack: An :class:`AsyncExitStack` used to manage the lifetime of
            all spawned processes and sessions.
        servers: Mapping from logical server name to :class:`MCPServer`.

    Returns:
        List[dict]: List of tools in the OpenAI function-calling format
        suitable for the ``tools`` argument of
        ``chat.completions.create()``.
    """
    openai_tools: List[dict] = []

    for server in servers.values():
        read_stream, write_stream = await stack.enter_async_context(
            stdio_client(
                StdioServerParameters(
                    command=server.command,
                    args=server.args,
                    env=server.env,
                )
            )
        )

        server.session = await stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await server.session.initialize()

        tools_result = await server.session.list_tools()
        for mcp_tool in tools_result.tools:
            openai_tools.append(mcp_tool_to_openai_tool(mcp_tool, server.name))

    return openai_tools


def call_result_to_text(result: types.CallToolResult) -> str:
    """Convert an :class:`CallToolResult` into a plain text string.

    Text content is concatenated in order. Non-text content is stringified
    using :func:`str`.

    Args:
        result: The MCP tool call result.

    Returns:
        str: A human-readable text representation of the result.
    """
    if not result.content:
        return "Tool returned no content."

    parts: List[str] = []
    for c in result.content:
        if isinstance(c, types.TextContent):
            parts.append(c.text)
        else:
            parts.append(str(c))
    return "\n".join(parts)


async def dispatch_tool_call(
    tool_call: Any,
    servers: Dict[str, MCPServer],
) -> str:
    """Dispatch a single tool call from the LLM to the correct MCP server.

    The tool call must come from the OpenAI function-calling API and is
    expected to have a function name in the form
    ``\"serverName__toolName\"``.

    Args:
        tool_call: A tool call object from
            ``response.choices[0].message.tool_calls``.
        servers: Mapping from logical server name to :class:`MCPServer`.

    Returns:
        str: The text representation of the MCP tool result, which can
        be injected back into the LLM as the content of a ``tool``
        message.
    """
    raw_name: str = tool_call.function.name
    args_str: str = tool_call.function.arguments or "{}"

    try:
        args = json.loads(args_str)
    except json.JSONDecodeError:
        args = {}

    try:
        server_name, mcp_tool_name = raw_name.split(TOOL_SEPARATOR, 1)
    except ValueError:
        return f"Tool name '{raw_name}' does not match the expected format."

    server = servers.get(server_name)
    if server is None or server.session is None:
        return f"MCP server '{server_name}' session not found."

    try:
        result = await server.session.call_tool(
            name=mcp_tool_name,
            arguments=args,
        )
    except Exception as exc:  # noqa: BLE001
        return f"Error while executing MCP tool '{raw_name}': {exc!r}"

    text = call_result_to_text(result)
    if len(text) > 8000:
        text = text[:8000] + "\n...(output truncated)..."
    return text
