"""Reddit fetch — uses public JSON endpoints with a browser user-agent.

No Reddit API app / OAuth required. We hit `https://www.reddit.com/r/{sub}/new.json`
directly with pagination (the `after` cursor) to pull ALL available posts, not
just the first 100.

Reddit typically lets you paginate back ~1000 posts before returning empty pages.
For small subs this means the entire history; for large subs, the last few days.
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

REQUEST_DELAY_SECONDS = 3.0  # polite rate limiting
MAX_RETRIES = 5
PAGE_SIZE = 100  # Reddit max per request


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
                wait = (2 ** attempt) * 5
                time.sleep(wait)
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
            time.sleep((2 ** attempt) * 3)
    raise RuntimeError(f"Failed after {MAX_RETRIES} retries: {url}") from last_err


def fetch_new_posts(
    subreddit: str,
    *,
    limit: int = 9999,
    comment_limit: int = 10,
    since_utc: int | None = None,
) -> Iterator[FetchedPost]:
    """Yield posts from r/{subreddit}, newest first, with full pagination.

    Paginates through Reddit's `after` cursor until one of:
      - We've yielded `limit` posts
      - Reddit returns an empty page (no more posts)
      - We hit a post older than `since_utc` (delta ingest)
    """
    yielded = 0
    after_cursor: str | None = None
    page_num = 0

    while yielded < limit:
        # Build URL with pagination cursor
        url = f"https://www.reddit.com/r/{subreddit}/new.json?limit={PAGE_SIZE}"
        if after_cursor:
            url += f"&after={after_cursor}"

        try:
            data = _get_json(url)
        except RuntimeError:
            break  # can't fetch this page, stop gracefully

        listing = data.get("data", {}) if isinstance(data, dict) else {}
        children = listing.get("children", [])
        after_cursor = listing.get("after")
        page_num += 1

        if not children:
            break  # no more posts

        hit_time_boundary = False
        for child in children:
            if yielded >= limit:
                break
            post_data = child.get("data", {})
            created = int(post_data.get("created_utc", 0))

            if since_utc is not None and created <= since_utc:
                hit_time_boundary = True
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
                except (urllib.error.URLError, urllib.error.HTTPError,
                        TimeoutError, json.JSONDecodeError, RuntimeError):
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

        if hit_time_boundary:
            break

        # No more pages if after_cursor is None
        if not after_cursor:
            break

        # Delay between pages
        time.sleep(REQUEST_DELAY_SECONDS * 2)

    return


def _fetch_comments(subreddit: str, post_id: str, limit: int) -> list[FetchedComment]:
    """Fetch top comments for a post."""
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
