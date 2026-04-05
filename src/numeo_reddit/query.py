"""RAG query command.

Flow:
  1. Send the user's question (+ optional metadata filter) to Pinecone.
  2. Pull top-k posts with their permalinks and classifications.
  3. Ask Claude to synthesize an answer with mandatory citations.
"""

from __future__ import annotations

import os
import sqlite3
from textwrap import dedent

from anthropic import Anthropic
from rich.console import Console
from rich.markdown import Markdown

from numeo_reddit import db, embedder

console = Console()

SYNTHESIS_SYSTEM = dedent(
    """
    You are a market-research analyst for the Numeo growth team. You read Reddit
    posts from US trucking/logistics communities and answer questions about what
    potential customers are saying.

    Rules:
    - Ground every claim in the provided passages. If the passages don't cover
      something, say so explicitly.
    - Cite sources inline as [#1], [#2], etc., matching the numbered passages.
    - Keep the answer scannable: short paragraphs or bullets, not a wall of text.
    - When asked about "pain points" or "themes", synthesize across posts rather
      than listing one post at a time.
    """
).strip()


def answer(*, question: str, top_k: int = 12) -> None:
    hits = embedder.search(query_text=question, top_k=top_k)
    if not hits:
        console.print("[yellow]No results found. Try a broader question or ingest more data.[/yellow]")
        return

    passages = _load_passages(hits)
    prompt = _build_prompt(question, passages)

    model = os.environ.get("SYNTHESIS_MODEL", "claude-sonnet-4-6")
    client = Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=1500,
        system=SYNTHESIS_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    answer_text = response.content[0].text

    console.print()
    console.print(Markdown(answer_text))
    console.print()
    console.rule("[dim]Sources[/dim]")
    for i, p in enumerate(passages, 1):
        console.print(f"  [#{i}] r/{p['subreddit']}  [dim]{p['permalink']}[/dim]")


def _load_passages(hits: list[dict]) -> list[dict]:
    ids = [h["id"] for h in hits]
    passages = []
    with db.get_conn() as conn:
        for post_id in ids:
            row = conn.execute(
                """
                SELECT p.id, p.subreddit, p.title, p.body, p.permalink,
                       p.score, p.num_comments, p.created_utc,
                       c.author_role, c.topics, c.pain_points,
                       c.competitors_mentioned, c.sentiment
                FROM posts p
                LEFT JOIN classifications c ON c.post_id = p.id
                WHERE p.id = ?
                """,
                (post_id,),
            ).fetchone()
            if row:
                passages.append(dict(row))
    return passages


def _build_prompt(question: str, passages: list[dict]) -> str:
    numbered = []
    for i, p in enumerate(passages, 1):
        body = (p.get("body") or "").strip()
        if len(body) > 1200:
            body = body[:1200] + "…"
        numbered.append(
            f"[#{i}] r/{p['subreddit']} — {p['title']}\n"
            f"Author role: {p.get('author_role') or 'unknown'}\n"
            f"URL: {p['permalink']}\n\n"
            f"{body}"
        )
    joined = "\n\n---\n\n".join(numbered)
    return f"""Question: {question}

Passages:

{joined}

Answer the question using ONLY these passages. Cite with [#N] inline."""
