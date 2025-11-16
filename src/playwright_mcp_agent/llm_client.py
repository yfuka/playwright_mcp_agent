"""LLM client configuration for the MCP agent.

This module defines the OpenAI-compatible client used to talk to a local
LLM. By default it targets a Llama 3.1 instance exposed via Ollama, but the
environment variables documented in ``.env`` let you point to any model.
"""

import os

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


# NOTE: Defaults match the previous Ollama configuration but can be overridden
# via the environment variables defined in .env.
MODEL_NAME = os.getenv("MODEL_NAME", "llama3.1")


def create_llm_client() -> OpenAI:
    """Create an OpenAI-compatible client configured via environment variables."""

    base_url = os.getenv("BASE_URL", "http://localhost:11434/v1")
    api_key = os.getenv("API_KEY", "ollama")

    return OpenAI(
        base_url=base_url,
        api_key=api_key,
    )
