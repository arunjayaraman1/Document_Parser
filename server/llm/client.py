"""OpenRouter LLM client initialization with instructor."""

import os
from pathlib import Path
from dotenv import load_dotenv
import instructor
from openai import OpenAI

# Load .env file explicitly
env_path = Path(__file__).parent.parent.parent / ".env"
if not env_path.exists():
    env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)


def get_instructor_client(mode=instructor.Mode.TOOLS):
    """Create an instructor-patched OpenRouter client.

    Args:
        mode: Instructor mode (TOOLS or JSON)

    Returns:
        Instructor-patched OpenAI client
    """
    # Reload env vars to make sure we get latest
    load_dotenv(override=True)

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    if not api_key:
        raise ValueError(
            "OPENROUTER_API_KEY not set in .env file. "
            "Please add your OpenRouter API key to .env"
        )

    if api_key == "sk-or-v1-your-key-here":
        raise ValueError(
            "OPENROUTER_API_KEY contains placeholder value. "
            "Please replace with your actual API key from https://openrouter.ai"
        )

    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()

    raw_client = OpenAI(
        base_url=base_url,
        api_key=api_key,
    )

    return instructor.from_openai(raw_client, mode=mode)
