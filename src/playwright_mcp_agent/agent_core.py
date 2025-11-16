"""Core agent logic for the local LLM + MCP web research flow.

This module defines the system prompt and the main agent loop that
handles tool calling for a single user query.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from openai import OpenAI

from .mcp_servers import MCPServer, dispatch_tool_call

logger = logging.getLogger(__name__)
TOOL_LOG_PREVIEW_LIMIT = 200

SYSTEM_PROMPT = """
あなたはウェブリサーチ用のAIエージェントです。

- Playwright MCPのツールを使ってブラウザを操作することで、ユーザーの依頼に対応します。
- ユーザーには日本語で分かりやすく回答してください。
- ブラウザやタブを閉じるツール（browser_close 等）は、ユーザーから明示的に指示があった場合を除き使用しないでください。
"""


def _preview_text(text: str, limit: int = TOOL_LOG_PREVIEW_LIMIT) -> str:
    """Create a single-line preview for logging."""
    text = text.replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}...(truncated)..."


async def run_agent_once(
    llm_client: OpenAI,
    model_name: str,
    user_query: str,
    tools_for_llm: List[dict],
    servers: Dict[str, MCPServer],
) -> str:
    """Run a single-agent turn for a given user query.

    This function performs the full tool-calling loop for one user input:

    1. Initialize a message history with a system message and the
       user's question.
    2. Call the LLM with the provided tools.
    3. If the LLM returns tool calls, dispatch each call to the
       appropriate MCP server using :func:`dispatch_tool_call`.
    4. Add the tool results as ``role=\"tool\"`` messages.
    5. Repeat the LLM call until no more tool calls are present.
    6. Return the final assistant message content as the answer.

    Args:
        llm_client: OpenAI-compatible LLM client.
        model_name: Name of the model to use (for example, ``"llama3.1"``).
        user_query: User's input text for this turn.
        tools_for_llm: A list of tool definitions in OpenAI's
            function-calling format, as returned by
            :func:`playwright_mcp_agent.mcp_servers.init_servers`.
        servers: Mapping from server name to :class:`MCPServer`.

    Returns:
        str: Final assistant answer text for the given query.
    """
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_query},
    ]

    while True:
        resp = llm_client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=tools_for_llm,
            tool_choice="auto",
        )
        msg = resp.choices[0].message
        messages.append(msg.model_dump())

        tool_calls = msg.tool_calls or []
        if not tool_calls:
            return msg.content or ""

        tool_messages: List[Dict[str, Any]] = []
        for tc in tool_calls:
            tool_name = tc.function.name
            raw_args = tc.function.arguments or "{}"
            logger.info("Tool selected: %s args=%s", tool_name, raw_args)
            tool_output = await dispatch_tool_call(tc, servers)
            logger.info(
                "Tool result: %s -> %s",
                tool_name,
                _preview_text(tool_output),
            )
            tool_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.function.name,
                    "content": tool_output,
                }
            )
        messages.extend(tool_messages)
