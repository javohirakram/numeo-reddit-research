"""CLI entry point. Wires subcommands: ingest, query, stats, report."""

from __future__ import annotations

import typer
from dotenv import load_dotenv

load_dotenv()

app = typer.Typer(
    name="numeo-reddit",
    help="Reddit market-research ingestion + RAG for Numeo.",
    no_args_is_help=True,
)


@app.command()
def ingest(
    only: str | None = typer.Option(
        None,
        "--only",
        help="Ingest a single subreddit (name without the r/ prefix). Default: all from config.",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        help="Override the per-subreddit post limit from config (useful for dev).",
    ),
    skip_classify: bool = typer.Option(
        False,
        "--skip-classify",
        help="Fetch + store raw posts only, skip LLM classification and Pinecone upsert.",
    ),
) -> None:
    """Pull new posts, classify, upsert into SQLite + Pinecone."""
    from numeo_reddit.ingest import run_ingest

    run_ingest(only=only, limit_override=limit, skip_classify=skip_classify)


@app.command()
def classify(
    limit: int = typer.Option(
        10_000,
        "--limit",
        help="Max posts to classify in this run.",
    ),
    skip_pinecone: bool = typer.Option(
        False,
        "--skip-pinecone",
        help="Write to SQLite only; don't upsert to the vector index.",
    ),
) -> None:
    """Classify all unclassified posts in SQLite via Claude, then upsert to Pinecone."""
    from numeo_reddit.classify_batch import run_classify

    run_classify(limit=limit, skip_pinecone=skip_pinecone)


@app.command()
def query(
    question: str = typer.Argument(..., help="Natural-language question."),
    top_k: int = typer.Option(12, "--top-k", help="Passages to retrieve."),
) -> None:
    """RAG answer with citations back to Reddit permalinks."""
    from numeo_reddit.query import answer

    answer(question=question, top_k=top_k)


stats_app = typer.Typer(help="Structured stats over classifications.")
app.add_typer(stats_app, name="stats")


@stats_app.command("topics")
def stats_topics(
    role: str | None = typer.Option(None, "--role"),
    subreddit: str | None = typer.Option(None, "--subreddit"),
    since: str = typer.Option("30d", "--since", help="e.g. 7d, 30d, 90d, all"),
) -> None:
    """Top topics, optionally filtered by role or subreddit."""
    from numeo_reddit.stats import top_topics

    top_topics(role=role, subreddit=subreddit, since=since)


@stats_app.command("roles")
def stats_roles(
    subreddit: str | None = typer.Option(None, "--subreddit"),
    since: str = typer.Option("30d", "--since"),
) -> None:
    """Distribution of author roles across posts."""
    from numeo_reddit.stats import role_distribution

    role_distribution(subreddit=subreddit, since=since)


@stats_app.command("competitors")
def stats_competitors(
    since: str = typer.Option("90d", "--since"),
) -> None:
    """Competitor mention counts over time."""
    from numeo_reddit.stats import competitor_mentions

    competitor_mentions(since=since)


@app.command()
def report(
    out: str = typer.Option("reports/market-snapshot.md", "--out"),
    since: str = typer.Option("30d", "--since"),
) -> None:
    """Render a full market-snapshot markdown report."""
    from numeo_reddit.stats import render_report

    render_report(out_path=out, since=since)


if __name__ == "__main__":
    app()
