"""CLI interface for the local LLM + MCP web research agent.

This module implements a simple interactive loop that:

- Initializes all MCP servers using :func:`init_servers`.
- Creates a local LLM client.
- Reads user queries from standard input.
- Delegates each query to :func:`run_agent_once`.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Dict

from .agent_core import run_agent_once
from .llm_client import MODEL_NAME, create_llm_client
from .mcp_servers import MCPServer, RAW_CONFIG, build_servers, init_servers


async def chat_loop(servers: Dict[str, MCPServer]) -> None:
    """Run an interactive CLI chat loop.

    This function:

    1. Creates a local LLM client.
    2. Initializes all MCP servers and collects their tools.
    3. Prints the list of available tools.
    4. Repeatedly reads user input from standard input.
    5. For each input, calls :func:`run_agent_once` and prints the answer.

    Args:
        servers: Mapping from server name to :class:`MCPServer`. The
            :attr:`MCPServer.session` field will be populated by
            :func:`init_servers` when this loop starts.
    """
    llm_client = create_llm_client()

    async with AsyncExitStack() as stack:
        tools_for_llm = await init_servers(stack, servers)

        print("=== Available MCP tools ===")
        for t in tools_for_llm:
            fn = t["function"]
            print(f"- {fn['name']}: {fn.get('description', '')}")

        while True:
            try:
                user_text = await asyncio.to_thread(input, "\nYou> ")
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                break

            if not user_text.strip():
                continue
            if user_text.strip().lower() in {"exit", "quit"}:
                print("Bye.")
                break

            answer = await run_agent_once(
                llm_client=llm_client,
                model_name=MODEL_NAME,
                user_query=user_text,
                tools_for_llm=tools_for_llm,
                servers=servers,
            )
            print("\nAssistant>")
            print(answer)


def main() -> None:
    """Entry point for the playwright-mcp-agent CLI.

    This function constructs the :class:`MCPServer` map from
    :data:`RAW_CONFIG` and then runs the chat loop.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    servers_map = build_servers(RAW_CONFIG)
    asyncio.run(chat_loop(servers_map))
