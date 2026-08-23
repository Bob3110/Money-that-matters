import { Link } from "react-router-dom";
import { useState } from "react";
import { isWatched, toggleWatch } from "../lib/watchlist.js";

const SOURCE_ICONS = {
  market_news: { label: "News", glyph: "N" },
  insiders: { label: "Insiders", glyph: "I" },
  congress: { label: "Congress", glyph: "C" },
};

export default function TickerCard({ ticker }) {
  const [watched, setWatched] = useState(isWatched(ticker.ticker));
  const isBullish = ticker.direction === "bullish";
  const isBearish = ticker.direction === "bearish";
  const scoreColor = isBullish ? "text-bull" : isBearish ? "text-bear" : "text-ink-500";

  return (
    <Link
      to={`/ticker/${ticker.ticker}`}
      className="flex items-center justify-between rounded-card bg-surface p-4 shadow-card active:scale-[0.99] transition"
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-[15px] font-semibold text-ink-900">{ticker.ticker}</span>
          {ticker.strong_match && (
            <span className="inline-flex items-center gap-0.5 rounded-full bg-accent-50 px-1.5 py-0.5 text-[10px] font-semibold text-accent-600">
              ⚡ Strong Match
            </span>
          )}
        </div>
        <div className="mt-1.5 flex items-center gap-2">
          {["market_news", "insiders", "congress"].map((key) => {
            const fired = ticker.sources_fired?.includes(key);
            const excluded = ticker.excluded_sources?.includes(key);
            return (
              <span
                key={key}
                title={
                  fired ? SOURCE_ICONS[key].label
                    : excluded ? `${SOURCE_ICONS[key].label} — excluded (stale)`
                    : `${SOURCE_ICONS[key].label} — no signal`
                }
                className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-semibold ${
                  fired
                    ? "bg-ink-900 text-white"
                    : excluded
                    ? "bg-ink-100 text-ink-300"
                    : "border border-dashed border-ink-100 text-ink-300"
                }`}
              >
                {SOURCE_ICONS[key].glyph}
              </span>
            );
          })}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <span className={`num text-2xl font-semibold ${scoreColor}`}>{ticker.score}</span>
        <button
          onClick={(e) => {
            e.preventDefault();
            setWatched(toggleWatch(ticker.ticker).includes(ticker.ticker));
          }}
          aria-label={watched ? "Remove from watchlist" : "Add to watchlist"}
          className="flex h-9 w-9 items-center justify-center text-ink-300 active:scale-95 transition"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill={watched ? "#4A90D9" : "none"} stroke={watched ? "#4A90D9" : "currentColor"} strokeWidth="1.6">
            <path d="m12 3 2.7 5.8 6.3.6-4.7 4.3 1.3 6.3L12 17l-5.6 3 1.3-6.3-4.7-4.3 6.3-.6L12 3Z" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
    </Link>
  );
}
