"""PRAW wrapper — fetch new posts and top comments from a subreddit.

Uses read-only app credentials (script app, no user login). Rate-limit friendly:
PRAW handles backoff automatically.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterator

import praw
from praw.models import Submission


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


def _client() -> praw.Reddit:
    """Build a read-only PRAW client from env vars."""
    return praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=os.environ.get("REDDIT_USER_AGENT", "numeo-research/0.1"),
        check_for_async=False,
    )


def fetch_new_posts(
    subreddit: str,
    *,
    limit: int = 50,
    comment_limit: int = 20,
    since_utc: int | None = None,
) -> Iterator[FetchedPost]:
    """Yield new posts from r/{subreddit}, newest first, up to `limit`.

    If `since_utc` is given, stop early once we see a post older than that
    timestamp (delta ingest).
    """
    reddit = _client()
    reddit.read_only = True
    sub = reddit.subreddit(subreddit)

    for submission in sub.new(limit=limit):
        if since_utc is not None and int(submission.created_utc) <= since_utc:
            # PRAW .new() returns newest first, so once we hit an older post,
            # everything after is older too.
            break
        yield _hydrate_submission(submission, subreddit, comment_limit)


def _hydrate_submission(submission: Submission, subreddit: str, comment_limit: int) -> FetchedPost:
    submission.comment_sort = "top"
    submission.comments.replace_more(limit=0)
    top_comments = submission.comments[:comment_limit]

    comments = [
        FetchedComment(
            id=c.id,
            post_id=submission.id,
            parent_id=str(c.parent_id) if c.parent_id else None,
            body=c.body or "",
            author=str(c.author) if c.author else None,
            score=int(c.score or 0),
            created_utc=int(c.created_utc),
        )
        for c in top_comments
    ]

    return FetchedPost(
        id=submission.id,
        subreddit=subreddit,
        title=submission.title,
        body=submission.selftext or "",
        author=str(submission.author) if submission.author else None,
        author_flair=submission.author_flair_text,
        created_utc=int(submission.created_utc),
        score=int(submission.score or 0),
        num_comments=int(submission.num_comments or 0),
        url=submission.url,
        permalink=f"https://reddit.com{submission.permalink}",
        comments=comments,
    )
