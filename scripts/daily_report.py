"""Generate a daily report of new posts ingested in the last 24 hours.

Outputs reports/daily/YYYY-MM-DD.md with stats on new posts, top topics,
notable pain points, competitor mentions, and highest-engagement posts.
"""

import json
import sqlite3
import time
from collections import Counter
from pathlib import Path


def main():
    conn = sqlite3.connect("data/reddit.db")
    conn.row_factory = sqlite3.Row

    cutoff = int(time.time()) - 86400  # last 24 hours
    today = time.strftime("%Y-%m-%d", time.gmtime())

    new_posts = conn.execute("""
        SELECT p.*, c.author_role, c.topics, c.pain_points,
               c.competitors_mentioned, c.sentiment, c.numeo_relevance, c.relevance_reason
        FROM posts p
        LEFT JOIN classifications c ON c.post_id = p.id
        WHERE p.ingested_at >= ?
        ORDER BY p.score DESC
    """, (cutoff,)).fetchall()

    total_all = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]

    if not new_posts:
        print("No new posts in the last 24 hours.")
        return

    # Stats
    topic_counts = Counter()
    pain_counts = Counter()
    comp_counts = Counter()
    sub_counts = Counter()

    for p in new_posts:
        sub_counts[p["subreddit"]] += 1
        for t in json.loads(p["topics"]) if p["topics"] else []:
            topic_counts[t] += 1
        for pp in json.loads(p["pain_points"]) if p["pain_points"] else []:
            pain_counts[pp] += 1
        for c in json.loads(p["competitors_mentioned"]) if p["competitors_mentioned"] else []:
            comp_counts[c] += 1

    high_rel = [p for p in new_posts if (p["numeo_relevance"] or 0) >= 3]

    # Build report
    lines = []
    lines.append(f"# Daily Reddit Research Report — {today}")
    lines.append(f"\n**New posts ingested:** {len(new_posts)} (total in database: {total_all})")
    lines.append("")

    lines.append("## New posts by subreddit")
    lines.append("| Subreddit | New posts |")
    lines.append("|---|---:|")
    for sub, count in sub_counts.most_common():
        lines.append(f"| r/{sub} | {count} |")
    lines.append("")

    if topic_counts:
        lines.append("## Topics in today's posts")
        lines.append("| Topic | Count |")
        lines.append("|---|---:|")
        for t, c in topic_counts.most_common(10):
            lines.append(f"| {t.replace('_', ' ')} | {c} |")
        lines.append("")

    if pain_counts:
        lines.append("## Pain points mentioned today")
        for pp, c in pain_counts.most_common(10):
            lines.append(f"- **({c})** {pp}")
        lines.append("")

    if comp_counts:
        lines.append("## Competitor mentions today")
        for comp, c in comp_counts.most_common(10):
            lines.append(f"- **{comp}**: {c}")
        lines.append("")

    if high_rel:
        lines.append(f"## High-relevance posts today ({len(high_rel)} posts, score >= 3)")
        for p in high_rel[:10]:
            lines.append(f"\n### [{p['title'][:80]}]({p['permalink']})")
            lines.append(f"r/{p['subreddit']} · {p['score']} pts · {p['num_comments']} comments · Relevance: {p['numeo_relevance']}/5")
            if p["relevance_reason"]:
                lines.append(f"_{p['relevance_reason']}_")
            body = (p["body"] or "").strip()[:300]
            if body:
                lines.append(f"\n> {body}")
        lines.append("")

    # Top engagement posts regardless of relevance
    lines.append("## Top engagement posts today")
    for p in new_posts[:5]:
        lines.append(f"- [{p['title'][:70]}]({p['permalink']}) — r/{p['subreddit']} · {p['score']} pts · {p['num_comments']} comments")
    lines.append("")

    lines.append(f"\n---\n*Generated {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}*")

    out_dir = Path("reports/daily")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{today}.md"
    out_path.write_text("\n".join(lines))
    print(f"Daily report: {out_path} ({len(new_posts)} new posts)")


if __name__ == "__main__":
    main()
