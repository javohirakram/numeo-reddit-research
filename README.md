# numeo-reddit-research

Reddit market-research ingestion + RAG system for the Numeo growth team.

Scrapes trucking/logistics subreddits on a schedule, uses Claude to classify every
post by author role (owner-operator, dispatcher, carrier owner, freight broker…),
topic, pain points, and competitor mentions, then stores the results in SQLite
(for stats) and Pinecone (for semantic search).

You can query it in natural language:

```bash
numeo-reddit query "what are owner-operators saying about load boards lately?"
```

Or ask for structured stats:

```bash
numeo-reddit stats topics --role owner_operator --since 30d
numeo-reddit stats competitors --since 90d
numeo-reddit report --out reports/market-snapshot.md
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env   # fill in credentials
```

### Credentials you need

- **Reddit API** — create a "script" app at https://www.reddit.com/prefs/apps
  (name: numeo-research, type: script). Copy the client ID (under the app name)
  and secret into `.env`.
- **Anthropic API** — https://console.anthropic.com/ → API keys.
- **Pinecone API** — https://app.pinecone.io/ → API keys. Then run
  `python scripts/bootstrap_pinecone.py` once to create the `numeo-reddit`
  integrated index.

## Commands

| Command | Purpose |
|---|---|
| `numeo-reddit ingest` | Pull new posts from every subreddit in `config/subreddits.yaml`, classify, and upsert into SQLite + Pinecone. Delta-aware. |
| `numeo-reddit ingest --only r/Truckers --limit 20` | Ingest a single subreddit (handy for dev). |
| `numeo-reddit query "..."` | RAG answer with citations back to Reddit permalinks. |
| `numeo-reddit stats topics \| roles \| competitors` | Aggregated stats over classifications. |
| `numeo-reddit report` | Render a full market-snapshot markdown. |

## Scheduling

A GitHub Actions workflow at `.github/workflows/ingest.yml` runs `numeo-reddit ingest`
daily at 09:00 UTC and commits the updated `data/reddit.db` back to the repo.

## Architecture

- **Ingestion** — `praw` pulls posts + top comments. `ingest_state` table tracks the
  newest `created_utc` per subreddit so re-runs only touch new content.
- **Classification** — Claude Haiku 4.5 with a JSON-schema-constrained prompt.
  Controlled vocabulary lives in `config/taxonomy.yaml` so stats stay stable
  across runs.
- **Structured store** — SQLite at `data/reddit.db`. Tables: `posts`, `comments`,
  `classifications`, `ingest_state`.
- **Vector store** — Pinecone integrated index (`numeo-reddit`). One record per
  post with metadata mirroring classification fields, so RAG queries can filter
  by role/topic/timeframe before semantic ranking.
- **Query** — hybrid retrieval (metadata filter + vector search) → Claude
  synthesis with mandatory permalink citations.

See `/Users/javohirakramov/.claude/plans/sorted-jingling-zebra.md` for the full
design doc.
