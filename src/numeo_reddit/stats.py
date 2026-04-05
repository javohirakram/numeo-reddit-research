"""Structured stats over classifications — plus a markdown report renderer."""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

from rich.console import Console
from rich.table import Table

from numeo_reddit import db

console = Console()


def _since_to_utc(since: str) -> int:
    """Convert '7d', '30d', '90d', 'all' into a cutoff UTC timestamp."""
    if since == "all":
        return 0
    if since.endswith("d"):
        days = int(since[:-1])
        return int(time.time()) - days * 86400
    raise ValueError(f"Bad --since value: {since!r}. Use Nd or 'all'.")


def _explode_json_list(rows, field: str) -> Counter:
    counter: Counter = Counter()
    for row in rows:
        raw = row[field]
        if not raw:
            continue
        try:
            values = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for v in values:
            counter[v] += 1
    return counter


# ---------- topics ----------

def top_topics(*, role: str | None, subreddit: str | None, since: str) -> None:
    cutoff = _since_to_utc(since)
    sql = """
        SELECT p.subreddit, c.topics, c.author_role
        FROM classifications c
        JOIN posts p ON p.id = c.post_id
        WHERE p.created_utc >= ?
    """
    params: list = [cutoff]
    if role:
        sql += " AND c.author_role = ?"
        params.append(role)
    if subreddit:
        sql += " AND p.subreddit = ?"
        params.append(subreddit.removeprefix("r/"))

    with db.get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    counter = _explode_json_list(rows, "topics")

    table = Table(title=f"Top topics (since {since}"
                        + (f", role={role}" if role else "")
                        + (f", sub=r/{subreddit}" if subreddit else "")
                        + f", n={len(rows)} posts)")
    table.add_column("Topic", style="cyan")
    table.add_column("Count", justify="right", style="magenta")
    for topic, count in counter.most_common(20):
        table.add_row(topic, str(count))
    console.print(table)


# ---------- roles ----------

def role_distribution(*, subreddit: str | None, since: str) -> None:
    cutoff = _since_to_utc(since)
    sql = """
        SELECT c.author_role, COUNT(*) as n
        FROM classifications c
        JOIN posts p ON p.id = c.post_id
        WHERE p.created_utc >= ?
    """
    params: list = [cutoff]
    if subreddit:
        sql += " AND p.subreddit = ?"
        params.append(subreddit.removeprefix("r/"))
    sql += " GROUP BY c.author_role ORDER BY n DESC"

    with db.get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    total = sum(r["n"] for r in rows) or 1
    table = Table(title=f"Author roles (since {since}, n={total})")
    table.add_column("Role", style="cyan")
    table.add_column("Posts", justify="right", style="magenta")
    table.add_column("Share", justify="right", style="yellow")
    for r in rows:
        pct = 100 * r["n"] / total
        table.add_row(r["author_role"] or "unknown", str(r["n"]), f"{pct:.1f}%")
    console.print(table)


# ---------- competitors ----------

def competitor_mentions(*, since: str) -> None:
    cutoff = _since_to_utc(since)
    with db.get_conn() as conn:
        rows = conn.execute(
            """
            SELECT c.competitors_mentioned
            FROM classifications c
            JOIN posts p ON p.id = c.post_id
            WHERE p.created_utc >= ?
            """,
            (cutoff,),
        ).fetchall()

    counter = _explode_json_list(rows, "competitors_mentioned")
    table = Table(title=f"Competitor mentions (since {since})")
    table.add_column("Competitor", style="cyan")
    table.add_column("Mentions", justify="right", style="magenta")
    for name, count in counter.most_common():
        table.add_row(name, str(count))
    console.print(table)


# ---------- full markdown report ----------

def render_report(*, out_path: str, since: str) -> None:
    cutoff = _since_to_utc(since)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with db.get_conn() as conn:
        total_posts = conn.execute(
            "SELECT COUNT(*) FROM posts WHERE created_utc >= ?", (cutoff,)
        ).fetchone()[0]

        classified_rows = conn.execute(
            """
            SELECT p.subreddit, p.title, p.permalink, p.created_utc,
                   c.author_role, c.topics, c.pain_points,
                   c.competitors_mentioned, c.sentiment, c.numeo_relevance
            FROM classifications c
            JOIN posts p ON p.id = c.post_id
            WHERE p.created_utc >= ?
            ORDER BY c.numeo_relevance DESC, p.score DESC
            """,
            (cutoff,),
        ).fetchall()

    topic_counter = _explode_json_list(classified_rows, "topics")
    competitor_counter = _explode_json_list(classified_rows, "competitors_mentioned")
    pain_counter = _explode_json_list(classified_rows, "pain_points")

    role_counter: Counter = Counter()
    sub_counter: Counter = Counter()
    for row in classified_rows:
        role_counter[row["author_role"] or "unknown"] += 1
        sub_counter[row["subreddit"]] += 1

    lines: list[str] = []
    lines.append(f"# Numeo Reddit market snapshot — since {since}")
    lines.append("")
    lines.append(f"_Generated {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}. "
                 f"Covers {total_posts} posts, {len(classified_rows)} classified._")
    lines.append("")

    lines.append("## Who is posting")
    lines.append("")
    lines.append("| Role | Posts | Share |")
    lines.append("|---|---:|---:|")
    total = sum(role_counter.values()) or 1
    for role, n in role_counter.most_common():
        lines.append(f"| {role} | {n} | {100*n/total:.1f}% |")
    lines.append("")

    lines.append("## Top topics")
    lines.append("")
    lines.append("| Topic | Mentions |")
    lines.append("|---|---:|")
    for topic, n in topic_counter.most_common(15):
        lines.append(f"| {topic} | {n} |")
    lines.append("")

    lines.append("## Top pain points (free-form)")
    lines.append("")
    for phrase, n in pain_counter.most_common(25):
        lines.append(f"- **({n})** {phrase}")
    lines.append("")

    lines.append("## Competitor mentions")
    lines.append("")
    lines.append("| Tool | Mentions |")
    lines.append("|---|---:|")
    for name, n in competitor_counter.most_common():
        lines.append(f"| {name} | {n} |")
    lines.append("")

    lines.append("## Subreddit coverage")
    lines.append("")
    lines.append("| Subreddit | Classified posts |")
    lines.append("|---|---:|")
    for name, n in sub_counter.most_common():
        lines.append(f"| r/{name} | {n} |")
    lines.append("")

    lines.append("## Highest-relevance posts")
    lines.append("")
    for row in classified_rows[:15]:
        lines.append(
            f"- **[{row['numeo_relevance']}/5]** "
            f"_r/{row['subreddit']} · {row['author_role']}_ — "
            f"[{row['title']}]({row['permalink']})"
        )
    lines.append("")

    out.write_text("\n".join(lines))
    console.print(f"[green]Wrote {out}[/green]")
