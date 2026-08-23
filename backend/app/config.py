from __future__ import annotations

import os

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "money_that_matters")

# SEC EDGAR requires a descriptive User-Agent with a real contact address.
# DO NOT ship to production with the placeholder below -- see
# DEPLOYMENT.md. This is deliberately left un-fillable by the app itself
# so a real deploy can't accidentally ship a bogus contact.
SEC_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT",
    "MoneyThatMatters/0.1 (REPLACE_WITH_REAL_CONTACT_EMAIL_BEFORE_DEPLOY)",
)

# Congress data source strategy. See DEPLOYMENT.md for the tradeoffs between
# the three paths (self-built XML scraper / Apify actor / Quiver Hobbyist).
CONGRESS_SOURCE = os.environ.get("CONGRESS_SOURCE", "house_clerk_xml")
APIFY_TOKEN = os.environ.get("APIFY_TOKEN")  # required only if CONGRESS_SOURCE == "apify"
QUIVER_API_KEY = os.environ.get("QUIVER_API_KEY")  # required only if CONGRESS_SOURCE == "quiver"

USE_LLM_SENTIMENT = os.environ.get("USE_LLM_SENTIMENT", "").lower() in ("1", "true", "yes")

STALE_AFTER_HOURS = 24

# Baseline ticker universe: S&P 500 + Nasdaq-100 constituents should be
# loaded here at startup from a static list (not embedded verbatim in this
# file to avoid an instantly-stale hardcoded index membership list -- load
# from data/sp500_nasdaq100.json, refreshed periodically, not shipped as
# fabricated placeholder data). This module only defines *where* it comes
# from; see app/universe.py for the growable tracked-set logic.
TICKER_UNIVERSE_SEED_PATH = os.environ.get(
    "TICKER_UNIVERSE_SEED_PATH",
    os.path.join(os.path.dirname(__file__), "data", "ticker_universe_seed.json"),
)
