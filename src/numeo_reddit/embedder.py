"""Pinecone integrated-index upsert.

Uses Pinecone's integrated-inference indexes: we send raw text + metadata and
Pinecone handles the embedding. No client-side embedding step.

Run `scripts/bootstrap_pinecone.py` once to create the index before first use.

NOTE: Pinecone's SDK surface changes occasionally — if you hit an error here,
check the current docs at https://docs.pinecone.io/guides/inference/understanding-inference
and the MCP skill `pinecone:mcp`.
"""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Any

from pinecone import Pinecone

INDEX_NAME_DEFAULT = "numeo-reddit"
NAMESPACE_POSTS = "posts"

_pc: Pinecone | None = None
_index = None


def _get_index():
    global _pc, _index
    if _index is None:
        _pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
        index_name = os.environ.get("PINECONE_INDEX", INDEX_NAME_DEFAULT)
        description = _pc.describe_index(index_name)
        _index = _pc.Index(host=description.host)
    return _index


def _parse_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
        return value if isinstance(value, list) else []
    except json.JSONDecodeError:
        return []


def upsert_post(post: sqlite3.Row, classification: sqlite3.Row | dict[str, Any]) -> None:
    """Upsert a single post into the Pinecone integrated index."""
    index = _get_index()

    text = f"{post['title']}\n\n{post['body'] or ''}".strip()

    if isinstance(classification, sqlite3.Row):
        cls: dict[str, Any] = dict(classification)
    else:
        cls = classification

    record = {
        "_id": post["id"],
        "chunk_text": text,
        "subreddit": post["subreddit"],
        "permalink": post["permalink"],
        "created_utc": int(post["created_utc"]),
        "score": int(post["score"] or 0),
        "num_comments": int(post["num_comments"] or 0),
        "author_role": cls.get("author_role", "unknown"),
        "topics": _parse_json_list(cls.get("topics")) if isinstance(cls.get("topics"), str) else cls.get("topics", []),
        "competitors": _parse_json_list(cls.get("competitors_mentioned")) if isinstance(cls.get("competitors_mentioned"), str) else cls.get("competitors_mentioned", []),
        "sentiment": cls.get("sentiment", "neutral"),
        "numeo_relevance": int(cls.get("numeo_relevance", 0)),
    }

    index.upsert_records(NAMESPACE_POSTS, [record])


def search(
    *,
    query_text: str,
    top_k: int = 12,
    metadata_filter: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Semantic search with optional metadata filter. Returns list of hits."""
    index = _get_index()

    query: dict[str, Any] = {
        "inputs": {"text": query_text},
        "top_k": top_k,
    }
    if metadata_filter:
        query["filter"] = metadata_filter

    result = index.search(namespace=NAMESPACE_POSTS, query=query)

    hits = []
    for hit in result.get("result", {}).get("hits", []):
        hits.append(
            {
                "id": hit.get("_id"),
                "score": hit.get("_score"),
                "fields": hit.get("fields", {}),
            }
        )
    return hits
