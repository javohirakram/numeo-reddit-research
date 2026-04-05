# First-run notes — 2026-04-05

Observations from the initial 41-post ingest across r/Truckers, r/OwnerOperators,
r/FreightBrokers, and r/Dispatchers.

## Operational findings

- **r/Dispatchers is ~50% emergency-services dispatch**, not trucking. Posts about
  sheriff interviews, 911 call protocols, and fire-service tone-dropping
  equipment are all being classified as `unknown` and should eventually be
  filtered out at the source. Consider dropping it from `config/subreddits.yaml`
  or adding a title/body keyword prefilter.
- **r/Trucking is network-policy blocked** on this IP from Reddit
  (`"Your request has been blocked due to a network policy"`). The other 4 subs
  work fine. Revisit with a different UA string or run ingest from a different
  IP (e.g. GitHub Actions runner has a cleaner reputation).
- Reddit rate limits are aggressive — the ingest client now uses 3s base delay
  + exponential backoff on 403/429.

## Product signal (what customers are actually saying)

**High-relevance themes that match Numeo's pitch directly:**

1. **Three competing SaaS founders** (Octopus, LogixAI, NextBillion.ai) are
   pitching dispatch-automation products on r/Dispatchers *using Numeo's exact
   language*: "loads posted and gone in seconds," "scattered comms across tabs
   and phones," "brokers not picking up." This validates the wedge but also
   says the competitive noise is real.

2. **Broker check-call churn is universally hated on both sides.** A broker
   post ([r/FreightBrokers #1scpt15](https://reddit.com/r/FreightBrokers/comments/1scpt15/)) openly admits brokers are
   "stuck as middleman providing instant updates that customers demand but the
   carrier can't deliver." This is exactly what Numeo Updater Agent is built
   for — and the quote can go directly on a landing page.

3. **TMS gap is concrete, not abstract.** A broker actively shopping for a new
   TMS ([r/FreightBrokers #1sbl5wm](https://reddit.com/r/FreightBrokers/comments/1sbl5wm/)) says *every* modern TMS they
   demoed fails to track basic contract metadata (signer, signed date, version)
   and they're stuck on a 20-year-old homebrewed system. High-intent buyer
   signal.

4. **Payment trust is the #1 bond with carriers.** The HUB Group thread
   ([r/FreightBrokers #1sby57e](https://reddit.com/r/FreightBrokers/comments/1sby57e/)) — $140k past due, fake
   double-brokering claims — hit 17 upvotes and 14 commiserating comments.
   Carrier-side broker-trust tooling is an open gap. See also "no Carrier411
   for brokers" in r/OwnerOperators ([#1sc8lk2](https://reddit.com/r/OwnerOperators/comments/1sc8lk2/)).

5. **Detention claim paperwork is a carrier pain Numeo could automate.** A
   carrier post asking "what actually happens on your end?" ([#1scyy3y](https://reddit.com/r/FreightBrokers/comments/1scyy3y/)) with
   19 comments — burden of proof is entirely on the carrier with full
   documentation still disappearing into a black hole.

**Dispatcher anxiety signal:** one r/Dispatchers commenter to an automation
founder said bluntly *"We don't really want our jobs to be automated, because
then we won't have jobs."* Positioning Numeo as "dispatcher superpower" vs
"dispatcher replacement" is going to matter.

**Sentiment toward existing fleet tech is negative.** Samsara was mentioned
twice — once mocking the CEO, once in a list of integrations that are painful
to export data from. A 22-year company driver went owner-op specifically to
escape "driver-facing cameras and lane-departure false alarms" ([#1scadf3](https://reddit.com/r/OwnerOperators/comments/1scadf3/)) —
the incumbent UX is resented even by paying customers.

## Next ingest priorities

- Replace r/Dispatchers with a better trucking-dispatch source (r/Trucking once
  unblocked, or scan flairs on r/Truckers and r/OwnerOperators).
- Add r/CDL, r/Truckdrivers, r/smallbusiness (filtered to trucking posts) once
  the pipeline is proven.
- Re-run weekly and diff against this baseline — especially watch for new
  HUB Group / detention / TMS complaints (those are the sharpest pain clusters).
