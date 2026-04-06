# Full-dataset findings — 2026-04-05

852 posts, 2,840 comments, 851 classified across 12 subreddits.

## Dataset summary

| Subreddit | Posts | Timespan of posts |
|---|---:|---|
| r/Truckers | 100 | ~2 days |
| r/OwnerOperators | 100 | ~22 days |
| r/TruckDispatchers | 100 | ~194 days (low activity) |
| r/FreightBrokers | 100 | ~12 days |
| r/TruckingStartups | 80 | ~326 days (very low activity) |
| r/HotshotStartup | 80 | ~313 days |
| r/HotShotTrucking | 80 | ~46 days |
| r/logistics | 60 | ~15 days |
| r/supplychain | 60 | ~13 days |
| r/smallbusiness | 40 | ~1 day (very high volume, low signal) |
| r/SaaS | 40 | ~0.3 days (very high volume, low signal) |
| r/Dispatchers | 12 | legacy from initial run, ~50% 911 dispatch |

## Key findings

### 1. Topic distribution confirms Numeo's positioning

The top 5 topics by volume across all posts:

1. **dispatch_workflow (100 mentions)** — largest bucket. Confirms dispatching
   is the most-discussed operational pain. Posts span: manual load assignment,
   juggling tabs/phones, driver communication breakdowns, scheduling chaos.

2. **market_conditions (83)** — rate environment, freight volume swings, tariff
   impact. Not directly Numeo-addressable but drives the urgency behind load
   optimization ("every dollar per mile matters more when rates are down").

3. **authority_and_compliance (70)** — heavy in startup-focused subs. New OOs
   asking about MC authority, insurance requirements, FMCSA rules. Shows the
   barrier-to-entry pain Numeo Lite could help with.

4. **broker_trust_and_scams (51)** — payment delays, double-brokering, unfair
   Carrier411 flags, detention claim black holes. Both carriers AND brokers
   post about this. Signal for Numeo's document verification + transparency
   positioning.

5. **rate_negotiation (46)** — lowball offers, DAT rate benchmarking, "what's
   a fair rate for this lane?" Directly Numeo Spot territory.

### 2. Competitor landscape

**DAT dominates mindshare (27 mentions)** — it's the default reference point
for rates and load searching. Truckstop is distant second (12). Both are
mentioned almost exclusively as "the thing I use but am frustrated with."

**Samsara + Motive (7 each)** — mentioned in fleet management / ELD context,
often negatively (driver-facing cameras, false alarms, data export pain).
These are the incumbents Numeo could position *against* for the smaller carrier
segment that hates corporate surveillance tools.

**Uber Freight (5)** — mentioned as a cautionary tale ("they came in with VC
money, undercut rates, then pulled back") and as a competitor to traditional
brokerage.

Notable: **no mentions of Numeo itself** or direct AI-dispatch competitors
(Octopus, LogixAI) outside of their own self-promotion posts. Market awareness
of AI dispatch tools is near zero among actual truckers/OOs.

### 3. Pain points — the sharpest ones for Numeo

**High-frequency pain points (aggregated):**

| Pain cluster | Occurrences | Numeo product fit |
|---|---:|---|
| Insurance costs / requirements confusion | 12+ | Numeo Lite (onboarding guidance) |
| Finding and booking quality loads fast | 6+ | Numeo Spot |
| Broker payment delays / non-payment | 6+ | Numeo One (doc verification + tracking) |
| Compliance / authority setup overwhelm | 4+ | Numeo Lite |
| Double-brokering / scam concerns | 4+ | Numeo One (verification) |
| Broker check-call interruptions | 4 | Updater Agent |
| TMS missing features / integration pain | 3+ | Numeo One |
| Load board frustration (gone in seconds) | 3+ | Numeo Spot |

### 4. Classification quality notes

GPT-4o-mini classified **83.7% of posts as `unknown` role** — overly conservative
vs the hand-classified first batch (where "unknown" was ~10%). The model is
reluctant to infer author_role when the post doesn't explicitly say "I'm a
driver" or "I'm a broker." This is fine for topic/pain extraction but makes
the role-distribution chart unreliable. To fix:

- **Option A**: Tune the system prompt to be more aggressive about role inference
  from subreddit context (e.g., "If the post is in r/OwnerOperators and
  discusses personal trucking expenses, default to owner_operator").
- **Option B**: Re-classify with Claude Sonnet or GPT-4o (not mini) which
  handle nuanced inference better.
- **Option C**: Post-process: default `unknown` posts in r/OwnerOperators to
  `owner_operator`, in r/FreightBrokers to `freight_broker`, etc.

GPT-4o-mini also **hallucinated competitor names** not in the taxonomy (Swift,
Progressive, FedEx, etc. — these are carriers/insurers, not software competitors).
The taxonomy enum wasn't strictly enforced in the OpenAI JSON schema path.
Fix: add a post-classification filter that strips any competitor name not in
`taxonomy.competitors()`.

### 5. Subreddit quality ranking

**High signal for Numeo:**
- r/FreightBrokers — highest pain-point density, lots of TMS/rate/trust discussion
- r/OwnerOperators — core ICP, rate/fuel/compliance/load discussions
- r/TruckDispatchers — directly about dispatch workflow, low volume but high relevance
- r/TruckingStartups — new authority setup pain, ideal for Numeo Lite messaging

**Medium signal:**
- r/Truckers — huge volume but mostly driver lifestyle/photo posts, lower business pain
- r/HotShotTrucking — niche but active, similar to OwnerOperators
- r/HotshotStartup — startup-heavy, authority/insurance questions

**Low signal (consider dropping):**
- r/logistics / r/supplychain — too broad, mostly enterprise/warehouse/3PL topics
- r/smallbusiness / r/SaaS — overwhelmingly non-trucking; <5% relevance
- r/Dispatchers — 50% emergency-services dispatch (already noted in first run)

### 6. Actionable takeaways for growth

1. **Content play**: The phrase "loads gone in seconds" appears across multiple
   subs from multiple authors. It's the truest pain statement in the data.
   Use it in ad copy, landing pages, and cold outreach verbatim.

2. **Broker trust is a two-sided wedge**: Carriers hate broker payment delays.
   Brokers hate being the middleman for status updates. Numeo's Updater Agent
   solves the broker side; a payment-tracking feature would close the carrier
   side. Both sides are vocal on Reddit.

3. **DAT is the elephant in the room**: Everyone uses it, nobody loves it.
   "Better than DAT" is a dangerous positioning (they have deep moats), but
   "works alongside DAT to get you better rates" could land.

4. **AI awareness is near zero among actual operators**: Only SaaS founders
   pitch AI tools on these subs. Real truckers/dispatchers don't know AI-dispatch
   exists. This means education-first GTM, not "switch from X to us."

5. **r/TruckDispatchers is the perfect community for Numeo engagement** — small
   (8k members), directly on-topic, and currently underserved by AI tools.
   Authentic participation (not ads) here would build awareness in the exact
   right audience.

## Next steps

- Fix role classification (see quality notes above) — prompt tuning or model upgrade
- Filter hallucinated competitor names via taxonomy enforcement
- Add keyword prefilter for r/smallbusiness and r/SaaS (only ingest posts that
  mention "trucking", "dispatch", "freight", "carrier", "load board" etc.)
- Schedule daily ingest once Reddit API app is set up (or keep using the
  JSON endpoint approach — works on GitHub Actions runners)
- Re-run monthly to track topic trends over time
