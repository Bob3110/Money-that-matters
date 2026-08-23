# Money that matters

A mobile-first dashboard that scores how strongly market news, corporate
insiders, and Congress are leaning the same direction on a stock, plus a
separate Egypt (EGX) news tab. No login.

## Status report (read this first)

This was built in a sandboxed environment whose network access is limited to
package registries (PyPI, npm, GitHub). It **cannot reach** `sec.gov`,
`reuters.com`, `cnbc.com`, `gdeltproject.org`, or the House Clerk's
disclosure site. That has a real, specific effect on what's true right now:

**What's actually verified, with passing tests, in this environment:**
- The Money Match scoring engine (`backend/app/scoring.py`) — the coverage
  multiplier, stale-source exclusion, ⚡ Strong Match logic, ranking
  tie-breaks. 75 tests pass, run in this sandbox.
- The source allow-lists (`allowlist.py`) — host-boundary matching, tested
  against spoofed domains like `notreuters.com`.
- The subject-relevance gates (`relevance.py`) and defensive date parsing
  (`dates.py`).
- The sample-data guard test, which fails the build if a fixture/mock module
  ever gets committed to `app/`.
- The frontend builds cleanly (`npm run build` succeeds) and every backend
  module, including all four fetchers and both routers, imports and boots
  without error under `TestClient`.

**What is NOT verified, because it genuinely can't be from here:**
- Whether the SEC EDGAR, RSS, House Clerk, and GDELT fetchers correctly
  parse real live responses. The code is written against the real,
  documented endpoints and shapes, but has never made a live call.
- Whether MongoDB caching/staleness behaves correctly against a real
  instance (none is running here).
- Anything about actual data volume, rate-limit behavior in practice, or
  how often each source's structure has quietly changed since these
  fetchers were written.

**No fake data was created anywhere to paper over this.** Per the app's own
honesty rules, every feed will show "waiting for first sync" until it's run
somewhere with real network access and a real Mongo instance. That's the
correct behavior, not a bug — you should see empty states, not invented
rows, the first time you run this for real.

## What to do next

1. Run this somewhere with unrestricted outbound network access (your own
   machine, a VPS, a CI runner) — see `DEPLOYMENT.md`.
2. Set a real `SEC_USER_AGENT` with your actual contact email —
   `app/config.py` ships a placeholder that will get requests blocked or
   your access revoked if left in.
3. Populate `backend/app/data/ticker_universe_seed.json` with a real S&P
   500 + Nasdaq-100 constituent list (left empty deliberately — see the
   file's neighboring `README_SEED.txt`).
4. Decide on a Congress data path (self-built scraper / Apify actor /
   Quiver Hobbyist API) — see `DEPLOYMENT.md`, and get real legal advice
   before putting the Congress tab behind anything you charge for.
5. Watch the first real fetch cycle closely and expect to patch selector/
   endpoint drift — these sources change their markup and schemas without
   notice, which is exactly why the mode system (live/stale/empty) exists.

## Structure

```
backend/
  app/
    scoring.py        Money Match formula (fully tested, no deps)
    allowlist.py       source gate — host-boundary matching
    relevance.py        subject gate — relevance filters + symbol validation
    dates.py            defensive date parsing (3 formats)
    sentiment.py        lexicon-based bullish/neutral/bearish classifier
    rate_limiter.py     one shared limiter per upstream host
    universe.py          growable US tracked-ticker set
    db.py                 Mongo access + feed mode (live/stale/empty) tracking
    fetchers/              SEC EDGAR, RSS market news, House Clerk XML, GDELT
    routers/                 FastAPI endpoints
  tests/                        75 passing tests — run with: pytest
frontend/
  src/
    pages/              the 6 tabs + ticker detail
    components/    header, bottom nav, footer, ticker card, skeletons
```

## Running locally

Backend:
```
cd backend
pip install -r requirements.txt --break-system-packages
export SEC_USER_AGENT="MoneyThatMatters/0.1 (you@yourdomain.com)"
export MONGO_URI="mongodb://localhost:27017"
uvicorn app.main:app --reload
```

Frontend:
```
cd frontend
npm install
npm run dev
```

Tests:
```
cd backend
pytest
```
