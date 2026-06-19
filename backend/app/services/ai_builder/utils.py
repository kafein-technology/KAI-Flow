import os
import json
import re
import logging
from typing import Dict, Any, Optional
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# ─── Singleton OpenAI Client ───────────────────────────────────

_openai_client: Optional[AsyncOpenAI] = None


def get_openai_client() -> AsyncOpenAI:
    """
    Returns a singleton AsyncOpenAI client. Initializes on first call.
    Raises ValueError if OPENAI_API_KEY is not set.
    """
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        _openai_client = AsyncOpenAI(api_key=api_key)
        logger.info("OpenAI client initialized (singleton)")
    return _openai_client


# ─── JSON Extraction ───────────────────────────────────────────

def extract_json(text: str) -> Dict[str, Any]:
    """
    Robust JSON extraction that handles markdown code blocks and raw JSON alike.
    Will fallback to attempting regex extractions or extracting substring if simple decode fails.
    """
    if not text:
        raise ValueError("Empty string provided to JSON extractor.")

    text = text.strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # RegExp approach to find JSON blocks within markdown (e.g., ```json { ... } ```)
    json_pattern = re.compile(r'```(?:json)?\s*(\{.*?\})\s*```', re.DOTALL)
    match = json_pattern.search(text)

    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Fallback: Just grab everything from the first '{' to the last '}'
    start_idx = text.find('{')
    end_idx = text.rfind('}')

    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        potential_json = text[start_idx:end_idx + 1]
        try:
            return json.loads(potential_json)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse extracted JSON fragment: {e}")
            raise ValueError(f"Extracted content is not valid JSON. Error: {str(e)}")

    raise ValueError("Could not locate any valid JSON object within the response.")
