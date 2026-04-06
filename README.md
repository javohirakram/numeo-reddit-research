# Numeo Reddit Market Research

**Automated Reddit intelligence pipeline for the Numeo growth team.**

Scrapes trucking and logistics subreddits, classifies posts with AI, and surfaces pain points, competitor mentions, and product opportunities — all queryable via CLI.

## Quick stats

| Metric | Value |
|---|---|
| Posts ingested | 852 |
| Comments captured | 2,840 |
| Posts classified | 851 |
| Subreddits covered | 12 |
| Classification model | GPT-4o-mini |
| Vector index | Pinecone (`numeo-reddit`) |

## What it does

1. **Scrapes** posts + top comments from 12 trucking/logistics subreddits (delta-aware — only fetches new content on re-runs)
2. **Classifies** each post against a controlled taxonomy: author role, topics, pain points, competitor mentions, sentiment, and Numeo relevance score (0-5)
3. **Stores** structured data in SQLite for stats, and vectors in Pinecone for semantic search
4. **Answers** natural-language questions with citations back to Reddit threads
5. **Reports** aggregated stats and a markdown market snapshot

## Key findings

- **#1 topic**: dispatch workflow (100 mentions) — load assignment chaos, tab overload, broker phone tag
- **#1 competitor**: DAT (27 mentions) — universally used, universally frustrating
- **#1 pain phrase**: *"loads gone in seconds"* — appears from multiple independent authors
- **AI awareness**: near zero among actual operators — only SaaS founders mention AI dispatch tools
- **Best engagement target**: r/TruckDispatchers (8,298 members, directly on-topic)

Full analysis: [`reports/Numeo_Reddit_Market_Research_Report.pdf`](reports/Numeo_Reddit_Market_Research_Report.pdf)

## Setup

```bash
git clone https://github.com/javohirakram/numeo-reddit-research.git
cd numeo-reddit-research
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env   # fill in API keys
```

### Required credentials

| Key | Where to get it | Used for |
|---|---|---|
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com/api-keys) | Post classification (GPT-4o-mini) |
| `PINECONE_API_KEY` | [app.pinecone.io](https://app.pinecone.io/) | Semantic search index |
| `GOOGLE_API_KEY` *(optional)* | [aistudio.google.com](https://aistudio.google.com/app/apikey) | Alternative classifier (Gemini Flash) |

Reddit data is fetched from public JSON endpoints — **no Reddit API app required**.

## Usage

```bash
# Ingest new posts from all configured subreddits
numeo-reddit ingest

# Ingest a single subreddit (useful for testing)
numeo-reddit ingest --only r/Truckers --limit 20

# Classify all unclassified posts
numeo-reddit classify

# Ask a natural-language question (RAG with citations)
numeo-reddit query "what are owner-operators saying about load boards?"

# View topic / role / competitor stats
numeo-reddit stats topics --since 30d
numeo-reddit stats roles --subreddit OwnerOperators
numeo-reddit stats competitors --since 90d

# Generate a full markdown report
numeo-reddit report --out reports/market-snapshot.md
```

## Architecture

```
Reddit (public JSON)
  |
  v
[reddit_client.py] -- fetch posts + comments, delta-aware
  |
  v
[db.py] -- SQLite: posts, comments, classifications, ingest_state
  |
  v
[classifier.py] -- GPT-4o-mini / Gemini / Claude (auto-detected)
  |                 Structured output against controlled taxonomy
  v
[embedder.py] -- Pinecone integrated index (auto-embeds text)
  |
  v
[query.py] -- Semantic search + LLM synthesis with citations
[stats.py] -- SQL aggregation + markdown report generation
```

### Key design decisions

- **Two-store pattern**: SQLite for structured stats ("what % of posts are about X?"), Pinecone for semantic search ("what are people saying about X?"). Neither replaces the other.
- **Controlled taxonomy** ([`config/taxonomy.yaml`](config/taxonomy.yaml)): 8 roles, 16 topics, 17+ competitors. Keeps stats consistent across runs — the LLM can only pick from this vocabulary.
- **Delta ingestion**: `ingest_state` table tracks `last_post_utc` per subreddit. Re-runs only touch new content.
- **Multi-provider classifier**: supports OpenAI, Google Gemini, and Anthropic. Swap by changing one env var.
- **No Reddit API app needed**: uses public `.json` endpoints with a browser user-agent. Simpler setup, works on GitHub Actions runners.

## Subreddits covered

| Subreddit | Posts | Audience | Signal quality |
|---|---:|---|---|
| r/FreightBrokers | 100 | Freight brokers | High |
| r/OwnerOperators | 100 | Owner-operators, small fleets | High |
| r/TruckDispatchers | 100 | Truck dispatchers | High |
| r/Truckers | 100 | Drivers (company + O/O) | Medium |
| r/HotShotTrucking | 80 | Hot shot drivers | Medium |
| r/HotshotStartup | 80 | New hot shot operators | Medium |
| r/TruckingStartups | 80 | New carriers | High |
| r/logistics | 60 | Logistics professionals | Low |
| r/supplychain | 60 | Supply chain professionals | Low |
| r/smallbusiness | 40 | Small business owners | Low |
| r/SaaS | 40 | SaaS founders | Low |

Configured in [`config/subreddits.yaml`](config/subreddits.yaml). Add or remove subs there.

## Reports

| File | Description |
|---|---|
| [`Numeo_Reddit_Market_Research_Report.pdf`](reports/Numeo_Reddit_Market_Research_Report.pdf) | Full research report with all findings, stats, and post index |
| [`market-snapshot.md`](reports/market-snapshot.md) | Auto-generated stats dashboard (regenerated with `numeo-reddit report`) |
| [`first-run-notes.md`](reports/first-run-notes.md) | Detailed findings with actionable growth recommendations |

## Scheduling (GitHub Actions)

A daily cron workflow at [`.github/workflows/ingest.yml`](.github/workflows/ingest.yml) runs:

1. `numeo-reddit ingest` — fetch new posts
2. `numeo-reddit classify` — classify new posts
3. `numeo-reddit report` — regenerate market snapshot
4. Commits updated `data/reddit.db` + `reports/` back to the repo

Add your API keys as GitHub repo secrets to enable: `OPENAI_API_KEY`, `PINECONE_API_KEY`, `REDDIT_USER_AGENT`.

## Project structure

```
numeo-reddit-research/
├── config/
│   ├── subreddits.yaml          # which subs to scrape + limits
│   └── taxonomy.yaml            # controlled vocab: roles, topics, competitors
├── src/numeo_reddit/
│   ├── cli.py                   # typer CLI entry points
│   ├── reddit_client.py         # fetch via public JSON (no API app needed)
│   ├── db.py                    # SQLite schema + CRUD
│   ├── classifier.py            # multi-provider LLM classification
│   ├── classify_batch.py        # batch runner with rate limiting
│   ├── embedder.py              # Pinecone upsert + search
│   ├── ingest.py                # orchestrator: fetch -> db -> classify -> pinecone
│   ├── query.py                 # RAG answer with citations
│   ├── stats.py                 # SQL stats + markdown report
│   └── taxonomy.py              # loads config/taxonomy.yaml
├── scripts/
│   └── bootstrap_pinecone.py    # one-time: create Pinecone index
├── data/
│   └── reddit.db                # SQLite database (852 posts, 2840 comments)
├── reports/
│   ├── Numeo_Reddit_Market_Research_Report.pdf
│   ├── market-snapshot.md
│   └── first-run-notes.md
├── .github/workflows/
│   └── ingest.yml               # daily scheduled ingest
├── .env.example
├── .gitignore
└── pyproject.toml
```

## License

Proprietary — Numeo internal use.
