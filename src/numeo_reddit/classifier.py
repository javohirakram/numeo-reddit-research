"""LLM classification — supports multiple providers (OpenAI, Gemini, Anthropic).

Given a post (title + body + top comments), returns a structured dict matching
the `classifications` table schema. Uses the controlled vocabulary from
`config/taxonomy.yaml` so stats stay consistent across runs.

Provider is auto-detected from the CLASSIFIER_MODEL env var:
  - gpt-*          → OpenAI (structured output via response_format)
  - gemini-*       → Google Gemini (response_schema)
  - claude-*       → Anthropic (tool_use)
"""

from __future__ import annotations

import json
import os
from typing import Any

from numeo_reddit import taxonomy

DEFAULT_MODEL = "gpt-4o-mini"


SYSTEM_PROMPT = """You are an analyst on the Numeo growth team. Numeo builds AI agents for US trucking dispatchers and small carriers: automating load board search, rate negotiation, broker check calls, and document handling.

You read Reddit posts from trucking/logistics communities and extract structured insights so the team can see what potential customers are complaining about, which tools they use, and what unmet needs exist.

Rules:
- Use ONLY the controlled vocabulary provided for `author_role` and `topics`. Never invent new values.
- For `pain_points`, use short natural phrases (5-10 words). These are free-form but should describe concrete problems, not generic complaints. Empty array if none.
- For `competitors_mentioned`, only return names from the provided list. Match case-insensitive.
- Be conservative on `author_role`: use `unknown` if the post doesn't give enough signal.
- Be honest about `numeo_relevance`: most posts will be 0-2. Only 4-5 for posts that directly describe a dispatcher/carrier workflow Numeo automates.

Controlled vocabulary for author_role: """ + ", ".join(taxonomy.roles()) + """

Controlled vocabulary for topics: """ + ", ".join(taxonomy.topics()) + """

Known competitors to look for: """ + ", ".join(taxonomy.competitors())


def _build_json_schema() -> dict[str, Any]:
    """JSON Schema for structured output (works with OpenAI and Gemini)."""
    return {
        "type": "object",
        "required": [
            "author_role", "topics", "pain_points", "competitors_mentioned",
            "sentiment", "numeo_relevance", "relevance_reason",
        ],
        "properties": {
            "author_role": {
                "type": "string",
                "enum": taxonomy.roles(),
            },
            "topics": {
                "type": "array",
                "items": {"type": "string", "enum": taxonomy.topics()},
            },
            "pain_points": {
                "type": "array",
                "items": {"type": "string"},
            },
            "competitors_mentioned": {
                "type": "array",
                "items": {"type": "string"},
            },
            "sentiment": {
                "type": "string",
                "enum": ["positive", "neutral", "negative"],
            },
            "numeo_relevance": {
                "type": "integer",
            },
            "relevance_reason": {
                "type": "string",
            },
        },
        "additionalProperties": False,
    }


def _build_user_content(
    title: str,
    body: str,
    subreddit: str,
    author_flair: str | None,
    top_comments: list[str] | None,
) -> str:
    comments_block = ""
    if top_comments:
        joined = "\n\n---\n\n".join(top_comments[:3])
        comments_block = f"\n\n## Top comments (context only)\n{joined}"

    return f"""# Reddit post from r/{subreddit}
Author flair: {author_flair or "(none)"}

## Title
{title}

## Body
{body or "(empty)"}{comments_block}"""


# ─── OpenAI ───────────────────────────────────────────────────────────

_openai_client = None

def _classify_openai(model: str, user_content: str) -> dict[str, Any]:
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI()

    response = _openai_client.chat.completions.create(
        model=model,
        temperature=0.1,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "classify_post",
                "strict": True,
                "schema": _build_json_schema(),
            },
        },
    )
    text = response.choices[0].message.content
    return json.loads(text)


# ─── Google Gemini ────────────────────────────────────────────────────

_gemini_client = None

def _classify_gemini(model: str, user_content: str) -> dict[str, Any]:
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        _gemini_client = genai.Client(api_key=api_key)

    from google.genai import types

    # Convert schema to Gemini's type format
    gemini_schema = _build_json_schema()
    response = _gemini_client.models.generate_content(
        model=model,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=gemini_schema,
            temperature=0.1,
        ),
    )
    return json.loads(response.text)


# ─── Anthropic ────────────────────────────────────────────────────────

_anthropic_client = None

def _classify_anthropic(model: str, user_content: str) -> dict[str, Any]:
    global _anthropic_client
    if _anthropic_client is None:
        from anthropic import Anthropic
        _anthropic_client = Anthropic()

    tool = {
        "name": "classify_post",
        "description": "Record a structured classification of a Reddit post.",
        "input_schema": _build_json_schema(),
    }
    response = _anthropic_client.messages.create(
        model=model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        tools=[tool],
        tool_choice={"type": "tool", "name": "classify_post"},
        messages=[{"role": "user", "content": user_content}],
    )
    for block in response.content:
        if getattr(block, "type", None) == "tool_use":
            return block.input
    raise RuntimeError(f"No tool_use block in Anthropic response")


# ─── Public API ───────────────────────────────────────────────────────

def classify_post(
    *,
    title: str,
    body: str,
    top_comments: list[str] | None = None,
    subreddit: str = "",
    author_flair: str | None = None,
) -> dict[str, Any]:
    """Classify a single post. Returns a dict matching the classifications row."""
    model = classifier_model_name()
    user_content = _build_user_content(title, body, subreddit, author_flair, top_comments)

    if model.startswith("gpt-"):
        return _classify_openai(model, user_content)
    elif model.startswith("gemini-"):
        return _classify_gemini(model, user_content)
    elif model.startswith("claude-"):
        return _classify_anthropic(model, user_content)
    else:
        # Default to OpenAI-compatible
        return _classify_openai(model, user_content)


def classifier_model_name() -> str:
    return os.environ.get("CLASSIFIER_MODEL", DEFAULT_MODEL)
