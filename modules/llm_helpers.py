"""Shared helpers for LLM response parsing across all pipeline stages."""

import json
import logging
import re

logger = logging.getLogger(__name__)

# Model to use across the pipeline
CLAUDE_MODEL = "claude-sonnet-4-6"


def extract_json(raw: str) -> dict:
    """Extract a JSON object from an LLM response, handling common quirks.

    Handles:
    - Clean JSON
    - JSON wrapped in ```json ... ``` or ``` ... ``` fences
    - JSON preceded/followed by commentary text
    - Nested markdown fences with language tags

    Args:
        raw: Raw text from LLM response.

    Returns:
        Parsed dict.

    Raises:
        json.JSONDecodeError: If no valid JSON object can be found.
    """
    text = raw.strip()

    # Attempt 1: Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Attempt 2: Strip markdown fences (```json\n...\n``` or ```\n...\n```)
    fence_pattern = re.compile(r"```(?:json)?\s*\n(.*?)\n\s*```", re.DOTALL)
    match = fence_pattern.search(text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Attempt 3: Find first { ... } block (greedy, outermost braces)
    brace_start = text.find("{")
    if brace_start != -1:
        # Find the matching closing brace
        depth = 0
        for i in range(brace_start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[brace_start : i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break

    # All attempts failed — log what we got and raise
    logger.error(
        "Could not extract JSON from LLM response. First 500 chars: %s",
        text[:500],
    )
    raise json.JSONDecodeError(
        "No valid JSON found in response", text, 0
    )
