import { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api.js";
import { getWatchlist } from "../lib/watchlist.js";
import TickerCard from "../components/TickerCard.jsx";
import { ListSkeleton } from "../components/Skeletons.jsx";

export default function WatchlistPage() {
  const [tickers, setTickers] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const watched = new Set(getWatchlist());
      if (watched.size === 0) {
        setTickers([]);
        return;
      }
      const result = await api.moneyMatch();
      setTickers(result.tickers.filter((t) => watched.has(t.ticker)));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="pb-4">
      <div className="px-4 pt-4">
        <h2 className="text-[22px] font-semibold text-ink-900">Watchlist</h2>
        <p className="mt-0.5 text-[13px] text-ink-500">Saved on this device only.</p>
      </div>

      {loading && <ListSkeleton count={3} />}

      {!loading && tickers && tickers.length === 0 && (
        <div className="mx-4 mt-6 rounded-card border border-dashed border-ink-100 bg-surface px-5 py-8 text-center">
          <p className="text-sm font-medium text-ink-700">No tickers saved yet</p>
          <p className="mt-1 text-[13px] text-ink-500">
            Tap the star on any ticker to add it here.
          </p>
        </div>
      )}

      {!loading && tickers && tickers.length > 0 && (
        <div className="space-y-3 px-4 pt-4">
          {tickers.map((t) => (
            <TickerCard key={t.ticker} ticker={t} onChange={load} />
          ))}
        </div>
      )}
    </div>
  );
}
