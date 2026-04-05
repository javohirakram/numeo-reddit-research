"""SQLite storage — schema and CRUD for posts, comments, classifications, state.

Single-file database at `data/reddit.db`. No migrations; schema is declared in
`SCHEMA_SQL` and created idempotently on first use.
"""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

DB_PATH = Path("data/reddit.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS posts (
    id             TEXT PRIMARY KEY,
    subreddit      TEXT NOT NULL,
    title          TEXT NOT NULL,
    body           TEXT,
    author         TEXT,
    author_flair   TEXT,
    created_utc    INTEGER NOT NULL,
    score          INTEGER,
    num_comments   INTEGER,
    url            TEXT,
    permalink      TEXT,
    ingested_at    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS comments (
    id             TEXT PRIMARY KEY,
    post_id        TEXT NOT NULL REFERENCES posts(id),
    parent_id      TEXT,
    body           TEXT,
    author         TEXT,
    score          INTEGER,
    created_utc    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS classifications (
    post_id               TEXT PRIMARY KEY REFERENCES posts(id),
    author_role           TEXT,
    topics                TEXT,        -- JSON array
    pain_points           TEXT,        -- JSON array
    competitors_mentioned TEXT,        -- JSON array
    sentiment             TEXT,
    numeo_relevance       INTEGER,     -- 0-5
    relevance_reason      TEXT,
    classifier_model      TEXT,
    classified_at         INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS ingest_state (
    subreddit      TEXT PRIMARY KEY,
    last_post_utc  INTEGER,
    last_run_at    INTEGER,
    posts_seen     INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_posts_subreddit_created ON posts(subreddit, created_utc);
CREATE INDEX IF NOT EXISTS idx_classifications_role   ON classifications(author_role);
CREATE INDEX IF NOT EXISTS idx_comments_post          ON comments(post_id);
"""


@contextmanager
def get_conn(db_path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    """Open a SQLite connection, ensure schema exists, yield, and close."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(SCHEMA_SQL)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------- posts ----------

def post_exists(conn: sqlite3.Connection, post_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM posts WHERE id = ?", (post_id,)).fetchone()
    return row is not None


def upsert_post(conn: sqlite3.Connection, post: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO posts (id, subreddit, title, body, author, author_flair,
                           created_utc, score, num_comments, url, permalink, ingested_at)
        VALUES (:id, :subreddit, :title, :body, :author, :author_flair,
                :created_utc, :score, :num_comments, :url, :permalink, :ingested_at)
        ON CONFLICT(id) DO UPDATE SET
            score = excluded.score,
            num_comments = excluded.num_comments,
            body = COALESCE(excluded.body, posts.body)
        """,
        {**post, "ingested_at": int(time.time())},
    )


def upsert_comment(conn: sqlite3.Connection, comment: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO comments (id, post_id, parent_id, body, author, score, created_utc)
        VALUES (:id, :post_id, :parent_id, :body, :author, :score, :created_utc)
        ON CONFLICT(id) DO UPDATE SET
            score = excluded.score,
            body  = excluded.body
        """,
        comment,
    )


def get_comments_for_post(conn: sqlite3.Connection, post_id: str, limit: int = 10) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            "SELECT * FROM comments WHERE post_id = ? ORDER BY score DESC LIMIT ?",
            (post_id, limit),
        )
    )


def get_unclassified_posts(conn: sqlite3.Connection, limit: int = 100) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT p.* FROM posts p
            LEFT JOIN classifications c ON c.post_id = p.id
            WHERE c.post_id IS NULL
            ORDER BY p.created_utc DESC
            LIMIT ?
            """,
            (limit,),
        )
    )


# ---------- classifications ----------

def upsert_classification(conn: sqlite3.Connection, post_id: str, result: dict[str, Any], model: str) -> None:
    conn.execute(
        """
        INSERT INTO classifications
            (post_id, author_role, topics, pain_points, competitors_mentioned,
             sentiment, numeo_relevance, relevance_reason, classifier_model, classified_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(post_id) DO UPDATE SET
            author_role = excluded.author_role,
            topics = excluded.topics,
            pain_points = excluded.pain_points,
            competitors_mentioned = excluded.competitors_mentioned,
            sentiment = excluded.sentiment,
            numeo_relevance = excluded.numeo_relevance,
            relevance_reason = excluded.relevance_reason,
            classifier_model = excluded.classifier_model,
            classified_at = excluded.classified_at
        """,
        (
            post_id,
            result.get("author_role", "unknown"),
            json.dumps(result.get("topics", [])),
            json.dumps(result.get("pain_points", [])),
            json.dumps(result.get("competitors_mentioned", [])),
            result.get("sentiment", "neutral"),
            int(result.get("numeo_relevance", 0)),
            result.get("relevance_reason", ""),
            model,
            int(time.time()),
        ),
    )


# ---------- ingest state ----------

def get_last_post_utc(conn: sqlite3.Connection, subreddit: str) -> int | None:
    row = conn.execute(
        "SELECT last_post_utc FROM ingest_state WHERE subreddit = ?",
        (subreddit,),
    ).fetchone()
    return row[0] if row else None


def update_ingest_state(conn: sqlite3.Connection, subreddit: str, last_post_utc: int, posts_seen: int) -> None:
    conn.execute(
        """
        INSERT INTO ingest_state (subreddit, last_post_utc, last_run_at, posts_seen)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(subreddit) DO UPDATE SET
            last_post_utc = MAX(ingest_state.last_post_utc, excluded.last_post_utc),
            last_run_at   = excluded.last_run_at,
            posts_seen    = ingest_state.posts_seen + excluded.posts_seen
        """,
        (subreddit, last_post_utc, int(time.time()), posts_seen),
    )
