"""Ingest orchestrator.

Wires together: taxonomy config -> Reddit fetch -> SQLite write -> Claude
classification -> Pinecone upsert -> state update.
"""

from __future__ import annotations

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from numeo_reddit import classifier, db, embedder, reddit_client, taxonomy

console = Console()


def run_ingest(
    *,
    only: str | None = None,
    limit_override: int | None = None,
    skip_classify: bool = False,
) -> None:
    """Entry point for the `numeo-reddit ingest` command."""
    subs = taxonomy.load_subreddits()
    if only:
        name = only.removeprefix("r/").lstrip("/")
        subs = [s for s in subs if s["name"].lower() == name.lower()]
        if not subs:
            console.print(f"[red]No subreddit named {only!r} in config/subreddits.yaml[/red]")
            return

    with db.get_conn() as conn:
        for sub_cfg in subs:
            _ingest_subreddit(conn, sub_cfg, limit_override, skip_classify)


def _ingest_subreddit(conn, sub_cfg: dict, limit_override: int | None, skip_classify: bool) -> None:
    name = sub_cfg["name"]
    limit = limit_override or sub_cfg.get("limit", 50)
    comment_limit = sub_cfg.get("comment_limit", 15)

    since_utc = db.get_last_post_utc(conn, name)
    console.rule(f"[bold cyan]r/{name}[/bold cyan]")
    console.print(
        f"  limit={limit}  comment_limit={comment_limit}  "
        f"since_utc={since_utc if since_utc else '(full)'}"
    )

    new_posts = 0
    newest_utc = since_utc or 0

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as progress:
        task = progress.add_task(f"Fetching r/{name}...", total=None)

        for post in reddit_client.fetch_new_posts(
            name, limit=limit, comment_limit=comment_limit, since_utc=since_utc
        ):
            progress.update(task, description=f"r/{name}: {post.title[:60]}")

            db.upsert_post(conn, post.to_db_row())
            for c in post.comments:
                db.upsert_comment(conn, c.to_db_row())

            if not skip_classify:
                try:
                    result = classifier.classify_post(
                        title=post.title,
                        body=post.body,
                        top_comments=[c.body for c in post.comments if c.body],
                        subreddit=name,
                        author_flair=post.author_flair,
                    )
                    db.upsert_classification(
                        conn, post.id, result, classifier.classifier_model_name()
                    )

                    # Mirror into Pinecone
                    stored_post = conn.execute(
                        "SELECT * FROM posts WHERE id = ?", (post.id,)
                    ).fetchone()
                    try:
                        embedder.upsert_post(stored_post, result)
                    except Exception as e:
                        console.print(f"[yellow]  Pinecone upsert failed for {post.id}: {e}[/yellow]")
                except Exception as e:
                    console.print(f"[yellow]  Classify failed for {post.id}: {e}[/yellow]")

            new_posts += 1
            newest_utc = max(newest_utc, post.created_utc)
            conn.commit()

    if new_posts > 0:
        db.update_ingest_state(conn, name, newest_utc, new_posts)

    console.print(f"  [green]+{new_posts} new posts[/green]")
