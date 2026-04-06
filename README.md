# Numeo Reddit Market Research

> Automated Reddit intelligence pipeline for the US trucking and logistics industry.
> Built for the [Numeo AI](https://numeo.ai) growth team.

**[View Live Dashboard](https://javohirakram.github.io/numeo-reddit-research/)**

---

## Dataset Overview

| Metric | Count |
|---|---:|
| Total posts | 6,247 |
| Total comments | 24,462 |
| Posts classified | 6,247 (100%) |
| Subreddits covered | 9 |
| Classification model | GPT-4o-mini |
| Vector index | Pinecone (numeo-reddit) |

### Subreddit Coverage

| Tier | Subreddit | Posts | Audience |
|---|---|---:|---|
| 1 | r/OwnerOperators | 999 | Owner-operators and small fleet owners (1-10 trucks) |
| 1 | r/HotShotTrucking | 998 | Hot shot drivers and small fleet owners |
| 1 | r/FreightBrokers | 969 | Freight brokers (counter-perspective) |
| 1 | r/TruckDispatchers | 602 | Truck dispatchers (independent + in-house) |
| 1 | r/HotshotStartup | 111 | New hot shot operators |
| 1 | r/TruckingStartups | 98 | New carriers launching authority |
| 2 | r/CDLTruckDrivers | 991 | CDL drivers (new and experienced) |
| 2 | r/Truckers | 990 | Drivers (company + owner-operators) |
| 2 | r/Truckdrivers | 489 | Truck drivers, CDL career discussions |

**Tier 1** = Direct ICP (dispatchers, O/Os, small carriers, brokers).
**Tier 2** = High-volume driver communities (noisier, but volume compensates).

---

## Key Findings

### Top Topics (what people talk about most)

| Topic | Mentions |
|---|---:|
| Market conditions | 756 |
| Dispatch workflow | 550 |
| Authority & compliance | 516 |
| Broker trust & scams | 427 |
| Load board frustration | 274 |
| Driver recruiting & retention | 265 |
| Rate negotiation | 246 |

### Competitor Landscape (taxonomy-filtered)

| Competitor | Mentions | Category |
|---|---:|---|
| DAT | 213 | Load board |
| Truckstop | 81 | Load board |
| Trucker Path | 35 | Load board/app |
| Motive | 29 | ELD/Fleet management |
| Sylectus | 26 | Legacy TMS |
| Samsara | 24 | ELD/Fleet management |
| Uber Freight | 17 | Digital brokerage |
| TruckSmarter | 10 | AI competitor |
| Cinesis | 4 | AI competitor |
| Datatruck | 0 | AI competitor (closest threat) |
| DispatchMVP | 0 | AI competitor |

**Key insight**: AI-dispatch competitors have near-zero organic mindshare. Datatruck ($12M Series A, 100K daily users) and DispatchMVP have zero Reddit mentions. Market awareness of AI dispatch tools is essentially zero among actual operators.

### Growth-Actionable Insights

1. **"Loads gone in seconds"** appears from multiple independent authors -- use verbatim in ad copy
2. **Broker check-call churn is hated on both sides** -- Updater Agent positioning validated
3. **DAT is universally used but universally frustrating** -- position alongside, not against
4. **AI awareness is near zero** -- education-first GTM, not "switch from X"
5. **r/TruckDispatchers** (8,300 members) is the ideal community for authentic engagement

---

## Web Dashboard

**Live at**: [javohirakram.github.io/numeo-reddit-research](https://javohirakram.github.io/numeo-reddit-research/)

Features:
- **Dashboard** -- stats cards, topic/competitor/pain point bar charts
- **Browse Posts** -- filterable/searchable table of all 6,247 posts with classification data
- **AI Query** -- semantic search via Pinecone + OpenAI synthesis with citations
- **Settings** -- configure API keys, trigger new scrapes via GitHub Actions

---

## CLI Usage

```bash
git clone https://github.com/javohirakram/numeo-reddit-research.git
cd numeo-reddit-research
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env   # fill in API keys
```

### Commands

```bash
# Scrape new posts (delta-aware, paginated)
numeo-reddit ingest

# Classify unclassified posts
numeo-reddit classify

# Semantic query with citations
numeo-reddit query "what do dispatchers hate about check calls?"

# Stats
numeo-reddit stats topics --since 30d
numeo-reddit stats roles --subreddit OwnerOperators
numeo-reddit stats competitors --since 90d

# Generate markdown report
numeo-reddit report --out reports/market-snapshot.md
```

### Required Credentials

| Key | Source | Used for |
|---|---|---|
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com/api-keys) | Classification (GPT-4o-mini) |
| `PINECONE_API_KEY` | [app.pinecone.io](https://app.pinecone.io/) | Semantic search |
| `GOOGLE_API_KEY` *(optional)* | [aistudio.google.com](https://aistudio.google.com/app/apikey) | Alternative classifier (Gemini) |

No Reddit API app required -- posts are fetched via public JSON endpoints.

---

## Architecture

```
Reddit (public JSON, paginated)
  |
  v
[reddit_client.py] -- fetch posts + comments with pagination + retry/backoff
  |
  v
[db.py] -- SQLite: posts, comments, classifications, ingest_state
  |
  v
[classifier.py] -- GPT-4o-mini / Gemini / Claude (auto-detected from model name)
  |                 Structured JSON output against controlled taxonomy
  v
[embedder.py] -- Pinecone integrated index (auto-embeds text)
  |
  v
[query.py] -- Semantic search + LLM synthesis with citations
[stats.py] -- SQL aggregation + markdown report generation
```

### Design Decisions

- **Two-store pattern**: SQLite for structured stats, Pinecone for semantic search
- **Controlled taxonomy** (`config/taxonomy.yaml`): 8 roles, 18 topics, 25+ competitors -- keeps stats consistent across runs
- **Paginated ingestion**: follows Reddit's `after` cursor past the 100-post cap, typically pulling 500-1000 posts per sub
- **Delta-aware**: `ingest_state` table tracks `last_post_utc` per subreddit
- **Multi-provider classifier**: supports OpenAI, Google Gemini, and Anthropic -- swap via `CLASSIFIER_MODEL` env var
- **No Reddit API app needed**: uses public `.json` endpoints with browser user-agent

---

## Reports

| File | Description |
|---|---|
| [Numeo_Reddit_Market_Research_Report.html](reports/Numeo_Reddit_Market_Research_Report.html) | Full research report (styled HTML, print to PDF) |
| [comprehensive-research-report.md](reports/comprehensive-research-report.md) | Same content as markdown |
| [market-snapshot.md](reports/market-snapshot.md) | Auto-generated stats dashboard |
| [first-run-notes.md](reports/first-run-notes.md) | Detailed findings with growth recommendations |

---

## Project Structure

```
numeo-reddit-research/
├── config/
│   ├── subreddits.yaml          # 9 validated subreddits with tier labels
│   └── taxonomy.yaml            # 8 roles, 18 topics, 25+ competitors
├── src/numeo_reddit/
│   ├── cli.py                   # typer CLI (ingest, classify, query, stats, report)
│   ├── reddit_client.py         # paginated fetch via public JSON + retry/backoff
│   ├── db.py                    # SQLite schema + CRUD
│   ├── classifier.py            # multi-provider LLM classification
│   ├── classify_batch.py        # batch runner with rate limiting + retry
│   ├── embedder.py              # Pinecone upsert + search
│   ├── ingest.py                # orchestrator: fetch -> db -> classify -> pinecone
│   ├── query.py                 # RAG with citations
│   ├── stats.py                 # SQL stats + markdown report
│   └── taxonomy.py              # loads controlled vocabulary
├── scripts/
│   └── bootstrap_pinecone.py    # one-time index creation
├── data/
│   └── reddit.db                # SQLite (6,247 posts, 24,462 comments)
├── docs/
│   ├── index.html               # GitHub Pages web dashboard
│   ├── data.json                # exported dataset for the dashboard
│   └── stats.json               # pre-computed stats
├── reports/                     # generated research reports
├── .github/workflows/
│   └── ingest.yml               # daily scheduled ingest + classify
├── .env.example
├── .gitignore
└── pyproject.toml
```

---

## Scheduling

A daily GitHub Actions workflow (`.github/workflows/ingest.yml`) runs:

1. `numeo-reddit ingest` -- fetch new posts
2. `numeo-reddit classify` -- classify via GPT-4o-mini
3. `numeo-reddit report` -- regenerate market snapshot
4. Commits updated `data/reddit.db` + `reports/` back to the repo

Add API keys as GitHub repo secrets: `OPENAI_API_KEY`, `PINECONE_API_KEY`.

---

## Taxonomy

The classification taxonomy is defined in `config/taxonomy.yaml` and includes:

**Roles**: owner_operator, company_driver, carrier_owner, dispatcher, freight_broker, shipper, logistics_tech, unknown

**Topics** (18): load_board_frustration, rate_negotiation, broker_trust_and_scams, dispatch_workflow, check_calls_and_updates, tms_and_software, market_conditions, fuel_costs, factoring_and_cashflow, insurance_and_claims, authority_and_compliance, eld_and_hos, safety_and_inspections, driver_recruiting_and_retention, maintenance_and_repairs, detention_and_dwell, backhaul_and_deadhead, document_and_paperwork

**Competitors** (25+): Datatruck, TruckSmarter, Cinesis, DispatchMVP, PCS Cortex, DAT, Truckstop, 123Loadboard, Uber Freight, Trucker Path, Parade, Samsara, Motive, Geotab, Omnitracs, HappyRobot, Vooma, FleetWorks, McLeod, TruckingOffice, ProTransport, Axon, Sylectus

---

*Built by the Numeo AI growth team. April 2026.*
