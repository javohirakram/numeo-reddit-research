"""LLM classification — Claude with JSON-schema-constrained tool-use output.

Given a post (title + body + top comments), returns a structured dict matching
the `classifications` table schema. Uses the controlled vocabulary from
`config/taxonomy.yaml` so stats stay consistent across runs.
"""

from __future__ import annotations

import json
import os
from typing import Any

from anthropic import Anthropic

from numeo_reddit import taxonomy

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def _build_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": [
            "author_role",
            "topics",
            "pain_points",
            "competitors_mentioned",
            "sentiment",
            "numeo_relevance",
            "relevance_reason",
        ],
        "properties": {
            "author_role": {
                "type": "string",
                "enum": taxonomy.roles(),
                "description": "Who is posting? Infer from self-description, flair, phrasing.",
            },
            "topics": {
                "type": "array",
                "items": {"type": "string", "enum": taxonomy.topics()},
                "description": "All topics this post touches. Use the controlled vocabulary only.",
            },
            "pain_points": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Short free-form phrases describing concrete pain points, max 10 words each. Empty list if none.",
            },
            "competitors_mentioned": {
                "type": "array",
                "items": {"type": "string"},
                "description": f"Any tools/services mentioned from this list (case-insensitive substring match ok): {', '.join(taxonomy.competitors())}. Return the canonical name from the list.",
            },
            "sentiment": {
                "type": "string",
                "enum": ["positive", "neutral", "negative"],
            },
            "numeo_relevance": {
                "type": "integer",
                "minimum": 0,
                "maximum": 5,
                "description": "How relevant is this post to Numeo (AI for trucking dispatchers — automates load finding, rate negotiation, check calls, doc handling)? 0 = unrelated, 5 = directly describes a pain Numeo solves.",
            },
            "relevance_reason": {
                "type": "string",
                "description": "One sentence: why this score.",
            },
        },
    }


SYSTEM_PROMPT = """You are an analyst on the Numeo growth team. Numeo builds AI agents for US trucking dispatchers and small carriers: automating load board search, rate negotiation, broker check calls, and document handling.

You read Reddit posts from trucking/logistics communities and extract structured insights so the team can see what potential customers are complaining about, which tools they use, and what unmet needs exist.

Rules:
- Use ONLY the controlled vocabulary provided in the tool schema for `author_role` and `topics`. Never invent new values.
- For `pain_points`, use short natural phrases (5-10 words). These are free-form but should describe concrete problems, not generic complaints.
- For `competitors_mentioned`, only return names from the provided list. Match case-insensitive.
- Be conservative on `author_role`: use `unknown` if the post doesn't give enough signal.
- Be honest about `numeo_relevance`: most posts will be 0-2. Only 4-5 for posts that directly describe a dispatcher/carrier workflow Numeo automates."""


def classify_post(
    *,
    title: str,
    body: str,
    top_comments: list[str] | None = None,
    subreddit: str = "",
    author_flair: str | None = None,
) -> dict[str, Any]:
    """Classify a single post. Returns a dict matching the classifications row."""
    model = os.environ.get("CLASSIFIER_MODEL", "claude-haiku-4-5-20251001")
    client = _get_client()

    comments_block = ""
    if top_comments:
        joined = "\n\n---\n\n".join(top_comments[:3])
        comments_block = f"\n\n## Top comments (context only, do not classify separately)\n{joined}"

    user_content = f"""# Reddit post from r/{subreddit}
Author flair: {author_flair or "(none)"}

## Title
{title}

## Body
{body or "(empty)"}{comments_block}

Classify this post using the `classify_post` tool. Return ONLY the tool call."""

    tool = {
        "name": "classify_post",
        "description": "Record a structured classification of a Reddit post.",
        "input_schema": _build_schema(),
    }

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        tools=[tool],
        tool_choice={"type": "tool", "name": "classify_post"},
        messages=[{"role": "user", "content": user_content}],
    )

    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "classify_post":
            return block.input  # already a dict

    raise RuntimeError(f"Classifier did not return a tool_use block. Response: {response}")


def classifier_model_name() -> str:
    return os.environ.get("CLASSIFIER_MODEL", "claude-haiku-4-5-20251001")
