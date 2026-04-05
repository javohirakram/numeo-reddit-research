"""Reddit fetch — uses public JSON endpoints with a browser user-agent.

No Reddit API app / OAuth required. We hit `https://www.reddit.com/r/{sub}/new.json`
directly, which returns the same data PRAW would give us for public posts and
their top comments. This keeps setup friction to zero: no client_id, no secret,
nothing to register.

Trade-offs vs PRAW:
  - No rate-limit backoff built in (we add a small sleep between calls).
  - Comment fetching needs a separate request per post.
  - Reddit could change/restrict this at any time; if it starts returning 403s,
    switch to PRAW (rewrite of this file — everything else stays the same).
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Iterator

import certifi

_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

REQUEST_DELAY_SECONDS = 3.0  # polite rate limiting — Reddit blocks aggressively
MAX_RETRIES = 4


@dataclass
class FetchedPost:
    id: str
    subreddit: str
    title: str
    body: str
    author: str | None
    author_flair: str | None
    created_utc: int
    score: int
    num_comments: int
    url: str
    permalink: str
    comments: list["FetchedComment"]

    def to_db_row(self) -> dict:
        return {
            "id": self.id,
            "subreddit": self.subreddit,
            "title": self.title,
            "body": self.body,
            "author": self.author,
            "author_flair": self.author_flair,
            "created_utc": self.created_utc,
            "score": self.score,
            "num_comments": self.num_comments,
            "url": self.url,
            "permalink": self.permalink,
        }


@dataclass
class FetchedComment:
    id: str
    post_id: str
    parent_id: str | None
    body: str
    author: str | None
    score: int
    created_utc: int

    def to_db_row(self) -> dict:
        return {
            "id": self.id,
            "post_id": self.post_id,
            "parent_id": self.parent_id,
            "body": self.body,
            "author": self.author,
            "score": self.score,
            "created_utc": self.created_utc,
        }


def _get_json(url: str, timeout: int = 20) -> dict | list:
    """GET a JSON URL with retry+backoff on transient failures and rate limits."""
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CONTEXT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (403, 429, 503):
                # rate limit — back off exponentially
                time.sleep((2 ** attempt) * 3)
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
            time.sleep((2 ** attempt) * 2)
    raise RuntimeError(f"Failed after {MAX_RETRIES} retries: {url}") from last_err


def fetch_new_posts(
    subreddit: str,
    *,
    limit: int = 50,
    comment_limit: int = 20,
    since_utc: int | None = None,
) -> Iterator[FetchedPost]:
    """Yield new posts from r/{subreddit}, newest first, up to `limit`.

    Stops early if `since_utc` is set and we hit a post older than that.
    """
    listing_url = f"https://www.reddit.com/r/{subreddit}/new.json?limit={min(limit, 100)}"
    data = _get_json(listing_url)
    children = data.get("data", {}).get("children", [])  # type: ignore[union-attr]

    yielded = 0
    for child in children:
        if yielded >= limit:
            break
        post_data = child.get("data", {})
        created = int(post_data.get("created_utc", 0))
        if since_utc is not None and created <= since_utc:
            break

        post_id = post_data.get("id")
        if not post_id:
            continue

        # Fetch comments for this post
        comments: list[FetchedComment] = []
        if comment_limit > 0:
            time.sleep(REQUEST_DELAY_SECONDS)
            try:
                comments = _fetch_comments(subreddit, post_id, comment_limit)
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
                comments = []

        yield FetchedPost(
            id=post_id,
            subreddit=subreddit,
            title=post_data.get("title", ""),
            body=post_data.get("selftext", "") or "",
            author=post_data.get("author"),
            author_flair=post_data.get("author_flair_text"),
            created_utc=created,
            score=int(post_data.get("score") or 0),
            num_comments=int(post_data.get("num_comments") or 0),
            url=post_data.get("url", ""),
            permalink=f"https://reddit.com{post_data.get('permalink', '')}",
            comments=comments,
        )
        yielded += 1
        time.sleep(REQUEST_DELAY_SECONDS)


def _fetch_comments(subreddit: str, post_id: str, limit: int) -> list[FetchedComment]:
    """Fetch top comments for a post. Reddit's /comments/{id}.json returns a list
    of two Listings: [post_listing, comment_listing]. We use the second."""
    url = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json?limit={limit}&sort=top"
    data = _get_json(url)
    if not isinstance(data, list) or len(data) < 2:
        return []

    comment_listing = data[1].get("data", {}).get("children", [])
    results: list[FetchedComment] = []
    for c in comment_listing[:limit]:
        if c.get("kind") != "t1":
            continue
        cd = c.get("data", {})
        body = cd.get("body", "")
        if not body or body in ("[deleted]", "[removed]"):
            continue
        results.append(
            FetchedComment(
                id=cd.get("id", ""),
                post_id=post_id,
                parent_id=cd.get("parent_id"),
                body=body,
                author=cd.get("author"),
                score=int(cd.get("score") or 0),
                created_utc=int(cd.get("created_utc") or 0),
            )
        )
    return results
