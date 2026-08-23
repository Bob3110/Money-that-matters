# Deployment guide

**Do not deploy this live without your explicit review of each item below.**
Nothing here has been published; this documents the steps and open
decisions.

## 1. Hosting

- **Frontend**: static build (`npm run build` → `frontend/dist`). Any static
  host works (Vercel, Netlify, Cloudflare Pages, S3+CloudFront).
- **Backend**: FastAPI app needs a real process host with outbound network
  access to `sec.gov`, `www.reuters.com`, `www.cnbc.com`,
  `disclosures-clerk.house.gov`, and `api.gdeltproject.org` (Fly.io,
  Render, a small VPS, ECS/Cloud Run all work). It needs a scheduler
  (cron, Celery beat, or a platform's native scheduled jobs) to run the
  four fetchers on an interval, independent of the manual Refresh button.
- **MongoDB**: Atlas free/shared tier is enough to start. Set `MONGO_URI`
  and `MONGO_DB_NAME` as backend env vars.

## 2. CORS

`backend/app/main.py` currently allows `*` — a development default only.
Before going live, lock `allow_origins` to the exact deployed frontend
origin(s).

## 3. SEC EDGAR User-Agent

**This is a hard requirement, not a nice-to-have.** SEC EDGAR requires a
descriptive `User-Agent` with a real, working contact address, and will
block or throttle generic/placeholder ones. Set:

```
SEC_USER_AGENT="Money that matters/1.0 (real-contact@yourdomain.com)"
```

`app/config.py` ships a placeholder (`REPLACE_WITH_REAL_CONTACT_EMAIL...`)
specifically so a deploy can't silently go live with a bogus one — the app
will work in dev with the placeholder, but you must override it in
production.

## 4. Congress data — pick one path before building further

The community S3 mirrors that used to give ticker-level Congress trade data
(house-stock-watcher, senate-stock-watcher) return `AccessDenied` as of the
last check (Aug 2026) and appear withdrawn. The only remaining free path is
the House Clerk's official XML index, which gives **filings, not parsed
trades** — no ticker, no buy/sell, no dollar amount, because that detail
lives inside per-filing PDFs with content-extraction disabled. This app
deliberately does not scrape those PDFs.

Three real paths forward, in increasing cost and decreasing build time:

1. **Self-built XML scraper against the official index** — free, most
   control, most build time. What's implemented in
   `backend/app/fetchers/congress.py` today.
2. **Apify's Congress disclosure scraper actor** — pay-per-use, already
   parses PTR filings into clean rows. Fastest way to ticker-level data
   without a subscription.
3. **Quiver Quantitative's Hobbyist API ($30/mo)** — bundles Congress
   Trading with a Trump-specific trades dataset and a real REST API, but
   is restricted to non-commercial use.

**Legal note, not optional:** the Senate Ethics Committee holds that it is
unlawful to obtain or use a Financial Disclosure Report for any commercial
purpose other than by news and communications media for public
dissemination. This is surfaced in the app's Congress tab
(`frontend/src/pages/CongressPage.jsx` + the `legal_notice` field returned
by `/api/congress`), but get real legal advice before monetizing this tab
regardless of which data path you choose.

Senate coverage is out of scope entirely — the Senate eFD portal blocks
non-browser access, and there's no free path around that.

## 5. Ticker universe seed

`backend/app/data/ticker_universe_seed.json` ships empty on purpose — no
fabricated placeholder list. Populate it with a real, sourced S&P 500 +
Nasdaq-100 constituent list (e.g. pulled from a maintained public dataset)
before first run, and refresh it periodically as index membership changes.

## 6. Rate limits to respect

- SEC EDGAR: descriptive User-Agent required (see #3), 10 requests/second.
  Enforced per-host in `app/rate_limiter.py`, shared across the Insiders and
  Market-News-8-K fetchers since they both hit `sec.gov`/`data.sec.gov`.
- GDELT: roughly one request per 5 seconds.
- Finnhub (if added for Market News headline pulls): free tier is
  personal/non-commercial use only — budget for their paid tier before
  shipping anything monetized on top of it.
- Mubasher: no public API/RSS. Their terms of use don't visibly address
  automated pulls — check directly before scraping them in a commercial
  product. Kept as a manual/semi-automated input in this build.

## 7. Before you flip it live

- [ ] CORS locked to real frontend origin
- [ ] Real `SEC_USER_AGENT` set
- [ ] Congress data path chosen, and legal sign-off obtained if monetizing
- [ ] Ticker universe seed populated with real, sourced data
- [ ] Scheduler configured for the four fetchers (not just the manual
      Refresh button)
- [ ] Mongo instance provisioned and `MONGO_URI` set
- [ ] Ran the app against real traffic long enough to confirm feed modes
      (live/stale/empty) behave as expected and no source's schema has
      drifted since these fetchers were written
