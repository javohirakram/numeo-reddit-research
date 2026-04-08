"""Rebuild docs/data.json, docs/stats.json, docs/context.json from SQLite.

Run after ingest + classify to keep the GitHub Pages dashboard up to date.
"""

import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path


def main():
    conn = sqlite3.connect("data/reddit.db")
    conn.row_factory = sqlite3.Row

    posts = conn.execute("""
        SELECT p.id, p.subreddit, p.title, p.body, p.author, p.author_flair,
               p.created_utc, p.score, p.num_comments, p.permalink,
               c.author_role, c.topics, c.pain_points, c.competitors_mentioned,
               c.sentiment, c.numeo_relevance, c.relevance_reason
        FROM posts p
        LEFT JOIN classifications c ON c.post_id = p.id
        ORDER BY p.created_utc DESC
    """).fetchall()

    total_comments = conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0]

    # ── data.json (full post list for dashboard browse) ──
    data_out = []
    for p in posts:
        data_out.append({
            "id": p["id"],
            "sub": p["subreddit"],
            "title": p["title"],
            "body": (p["body"] or "")[:500],
            "author": p["author"],
            "flair": p["author_flair"],
            "ts": p["created_utc"],
            "score": p["score"],
            "comments": p["num_comments"],
            "url": p["permalink"],
            "role": p["author_role"],
            "topics": json.loads(p["topics"]) if p["topics"] else [],
            "pains": json.loads(p["pain_points"]) if p["pain_points"] else [],
            "competitors": json.loads(p["competitors_mentioned"]) if p["competitors_mentioned"] else [],
            "sentiment": p["sentiment"],
            "relevance": p["numeo_relevance"] or 0,
            "why": p["relevance_reason"],
        })

    Path("docs/data.json").write_text(json.dumps(data_out, separators=(",", ":")))
    print(f"docs/data.json: {len(data_out)} posts")

    # ── stats.json ──
    topic_counts = Counter()
    competitor_counts = Counter()
    role_counts = Counter()
    sub_counts = Counter()
    sentiment_counts = Counter()
    pain_counts = Counter()

    for p in data_out:
        sub_counts[p["sub"]] += 1
        role_counts[p["role"] or "unknown"] += 1
        sentiment_counts[p["sentiment"] or "neutral"] += 1
        for t in p["topics"]:
            topic_counts[t] += 1
        for pp in p["pains"]:
            pain_counts[pp] += 1
        for c in p["competitors"]:
            competitor_counts[c] += 1

    stats = {
        "total_posts": len(data_out),
        "total_comments": total_comments,
        "subreddits": dict(sub_counts.most_common()),
        "roles": dict(role_counts.most_common()),
        "topics": dict(topic_counts.most_common()),
        "competitors": dict(competitor_counts.most_common()),
        "sentiments": dict(sentiment_counts.most_common()),
        "top_pains": dict(pain_counts.most_common(50)),
    }
    Path("docs/stats.json").write_text(json.dumps(stats, indent=2))
    print(f"docs/stats.json: written")

    # ── context.json (rich data for AI queries) ──
    def normalize(s):
        s = s.lower().strip().rstrip(".!,;:")
        return re.sub(r"\s+", " ", s)

    pain_map = defaultdict(lambda: {"count": 0, "quotes": []})
    topic_map = defaultdict(lambda: {"count": 0, "top_posts": []})
    comp_map = defaultdict(lambda: {"count": 0, "top_posts": []})

    sorted_by_score = sorted(posts, key=lambda p: -(p["score"] or 0))

    for p in sorted_by_score:
        body_snippet = (p["body"] or "")[:300].strip()
        post_ref = {
            "title": p["title"][:80],
            "sub": p["subreddit"],
            "score": p["score"],
            "comments": p["num_comments"],
            "url": p["permalink"],
            "quote": body_snippet[:150],
            "role": p["author_role"] or "unknown",
        }

        pains = json.loads(p["pain_points"]) if p["pain_points"] else []
        for pain in pains:
            key = normalize(pain)
            if not key or len(key) < 5:
                continue
            pain_map[key]["count"] += 1
            if len(pain_map[key]["quotes"]) < 5:
                pain_map[key]["quotes"].append(post_ref)

        topics = json.loads(p["topics"]) if p["topics"] else []
        for topic in topics:
            topic_map[topic]["count"] += 1
            if len(topic_map[topic]["top_posts"]) < 5:
                topic_map[topic]["top_posts"].append(post_ref)

        comps = json.loads(p["competitors_mentioned"]) if p["competitors_mentioned"] else []
        for comp in comps:
            comp_map[comp]["count"] += 1
            if len(comp_map[comp]["top_posts"]) < 5:
                comp_map[comp]["top_posts"].append(post_ref)

    # Top engagement posts
    top_posts = []
    for p in sorted_by_score[:30]:
        body = (p["body"] or "")[:300].strip()
        if not body:
            continue
        top_posts.append({
            "title": p["title"],
            "sub": p["subreddit"],
            "score": p["score"],
            "comments": p["num_comments"],
            "url": p["permalink"],
            "role": p["author_role"] or "unknown",
            "body": body,
            "topics": json.loads(p["topics"]) if p["topics"] else [],
            "pains": json.loads(p["pain_points"]) if p["pain_points"] else [],
            "competitors": json.loads(p["competitors_mentioned"]) if p["competitors_mentioned"] else [],
            "sentiment": p["sentiment"],
            "relevance": p["numeo_relevance"] or 0,
        })

    ctx = {
        "total_posts": len(posts),
        "total_comments": total_comments,
        "subreddits": dict(sub_counts.most_common()),
        "roles": dict(role_counts.most_common()),
        "sentiments": dict(sentiment_counts.most_common()),
        "topics": [
            {"name": t, "count": d["count"], "pct": round(100 * d["count"] / len(posts), 1),
             "top_posts": d["top_posts"][:5]}
            for t, d in sorted(topic_map.items(), key=lambda x: -x[1]["count"])
        ],
        "pain_points": [
            {"pain": p, "count": d["count"], "quotes": d["quotes"][:5]}
            for p, d in sorted(pain_map.items(), key=lambda x: -x[1]["count"])
            if d["count"] >= 2
        ][:40],
        "competitors": [
            {"name": c, "count": d["count"], "top_posts": d["top_posts"][:5]}
            for c, d in sorted(comp_map.items(), key=lambda x: -x[1]["count"])
            if d["count"] >= 2
        ][:20],
        "top_posts": top_posts,
    }

    Path("docs/context.json").write_text(json.dumps(ctx, separators=(",", ":")))
    print(f"docs/context.json: {len(ctx['pain_points'])} pain points, {len(ctx['competitors'])} competitors")
    print("Done.")


if __name__ == "__main__":
    main()
