"""Batch classification runner.

Pulls unclassified posts from SQLite, classifies each via Claude, writes
the result, and upserts to Pinecone. Designed to be re-runnable: posts that
already have a classification row are skipped.
"""

from __future__ import annotations

import os
import sqlite3
import time

from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn

from numeo_reddit import classifier, db, embedder

console = Console()

# Default pacing: Gemini 2.5 Flash-Lite free tier allows 15 RPM → 4s interval.
# Override with CLASSIFY_INTERVAL_SEC env var (e.g. "0.5" for paid tier).
DEFAULT_INTERVAL_SEC = float(os.environ.get("CLASSIFY_INTERVAL_SEC", "0.3"))
MAX_RETRIES = 5


def run_classify(*, limit: int | None = None, skip_pinecone: bool = False) -> None:
    """Classify all unclassified posts in SQLite."""
    with db.get_conn() as conn:
        unclassified = db.get_unclassified_posts(conn, limit=limit or 10_000)
        total = len(unclassified)
        console.print(f"[cyan]Found {total} unclassified posts[/cyan]")
        if total == 0:
            return

        classified = 0
        pinecone_ok = 0
        pinecone_fail = 0

        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Classifying", total=total)

            for post in unclassified:
                top_comments = _load_top_comments(conn, post["id"], limit=3)
                result = _classify_with_retries(
                    post["id"],
                    title=post["title"],
                    body=post["body"] or "",
                    top_comments=top_comments,
                    subreddit=post["subreddit"],
                    author_flair=post["author_flair"],
                )
                if result is None:
                    progress.update(task, advance=1)
                    continue

                db.upsert_classification(conn, post["id"], result, classifier.classifier_model_name())
                classified += 1

                if not skip_pinecone:
                    try:
                        stored = conn.execute(
                            "SELECT * FROM posts WHERE id = ?", (post["id"],)
                        ).fetchone()
                        embedder.upsert_post(stored, result)
                        pinecone_ok += 1
                    except Exception as e:
                        console.print(f"[yellow]pinecone failed for {post['id']}: {e}[/yellow]")
                        pinecone_fail += 1

                conn.commit()
                progress.update(task, advance=1)
                # Pace to stay under the configured rate limit
                time.sleep(DEFAULT_INTERVAL_SEC)

        console.print(
            f"[green]classified {classified}/{total} · "
            f"pinecone ok={pinecone_ok} fail={pinecone_fail}[/green]"
        )


def _classify_with_retries(
    post_id: str,
    **kwargs,
) -> dict | None:
    """Call classifier with exponential backoff on rate-limit (429) errors."""
    for attempt in range(MAX_RETRIES):
        try:
            return classifier.classify_post(**kwargs)
        except Exception as e:
            msg = str(e)
            is_rate_limit = "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower()
            if not is_rate_limit or attempt == MAX_RETRIES - 1:
                console.print(f"[yellow]classify failed for {post_id}: {msg[:200]}[/yellow]")
                return None
            wait = 30 * (2 ** attempt)  # 30s, 60s, 120s, 240s
            console.print(f"[dim]rate limited on {post_id}, sleeping {wait}s[/dim]")
            time.sleep(wait)
    return None


def _load_top_comments(conn: sqlite3.Connection, post_id: str, limit: int) -> list[str]:
    rows = conn.execute(
        "SELECT body FROM comments WHERE post_id = ? ORDER BY score DESC LIMIT ?",
        (post_id, limit),
    ).fetchall()
    return [r["body"] for r in rows if r["body"]]
