"""Re-fetch ALL comments for posts from the last 2 years.

Replaces the shallow top-10 comment scrape with a deep fetch (limit=500).
Reddit typically returns all top-level comments plus nested replies up to
a depth limit. This catches competitor mentions and pain points buried
in reply chains.
"""

import json
import sqlite3
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

import certifi

CTX = ssl.create_default_context(cafile=certifi.where())
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
DELAY = 2.5
MAX_RETRIES = 5


def _get_json(url):
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=20, context=CTX) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (403, 429, 503):
                time.sleep((2 ** attempt) * 5)
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            time.sleep((2 ** attempt) * 3)
    return None


def extract_comments(data, post_id, depth=0):
    """Recursively extract all comments from Reddit's nested JSON structure."""
    comments = []
    if not isinstance(data, dict):
        return comments

    children = data.get("data", {}).get("children", [])
    for child in children:
        if child.get("kind") != "t1":
            continue
        cd = child.get("data", {})
        body = cd.get("body", "")
        if not body or body in ("[deleted]", "[removed]"):
            continue

        comments.append({
            "id": cd.get("id", ""),
            "post_id": post_id,
            "parent_id": cd.get("parent_id"),
            "body": body,
            "author": cd.get("author"),
            "score": int(cd.get("score") or 0),
            "created_utc": int(cd.get("created_utc") or 0),
        })

        # Recurse into replies
        replies = cd.get("replies")
        if replies and isinstance(replies, dict):
            comments.extend(extract_comments(replies, post_id, depth + 1))

    return comments


def main():
    conn = sqlite3.connect("data/reddit.db")
    conn.row_factory = sqlite3.Row

    cutoff = int(time.time()) - (2 * 365 * 86400)  # 2 years ago
    posts = conn.execute(
        "SELECT id, subreddit FROM posts WHERE created_utc >= ? ORDER BY created_utc DESC",
        (cutoff,),
    ).fetchall()

    print(f"Deep-scraping comments for {len(posts)} posts (last 2 years)...")
    print(f"Current comment count: {conn.execute('SELECT COUNT(*) FROM comments').fetchone()[0]}")

    total_new = 0
    total_updated = 0
    errors = 0

    for i, post in enumerate(posts):
        url = f"https://www.reddit.com/r/{post['subreddit']}/comments/{post['id']}.json?limit=500&depth=10&sort=top"

        data = _get_json(url)
        if not data or not isinstance(data, list) or len(data) < 2:
            errors += 1
            time.sleep(DELAY)
            continue

        # Extract all comments recursively
        comments = extract_comments(data[1], post["id"])

        # Upsert each comment
        for c in comments:
            existing = conn.execute("SELECT 1 FROM comments WHERE id = ?", (c["id"],)).fetchone()
            if existing:
                conn.execute(
                    "UPDATE comments SET body = ?, score = ? WHERE id = ?",
                    (c["body"], c["score"], c["id"]),
                )
                total_updated += 1
            else:
                conn.execute(
                    "INSERT INTO comments (id, post_id, parent_id, body, author, score, created_utc) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (c["id"], c["post_id"], c["parent_id"], c["body"], c["author"], c["score"], c["created_utc"]),
                )
                total_new += 1

        conn.commit()

        if (i + 1) % 50 == 0:
            total = conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
            print(f"  [{i+1}/{len(posts)}] +{total_new} new, {total_updated} updated, {errors} errors, {total} total comments")

        time.sleep(DELAY)

    total = conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
    print(f"\nDone: +{total_new} new comments, {total_updated} updated, {errors} errors")
    print(f"Total comments now: {total}")
    conn.close()


if __name__ == "__main__":
    main()
