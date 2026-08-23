import { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api.js";
import TickerCard from "../components/TickerCard.jsx";
import { ListSkeleton } from "../components/Skeletons.jsx";
import { EmptyFeedState } from "../components/FeedState.jsx";

export default function MoneyMatchPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.moneyMatch();
      setData(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="pb-4">
      <div className="px-4 pt-4">
        <h2 className="text-[22px] font-semibold text-ink-900">Money Match</h2>
        <p className="mt-0.5 text-[13px] text-ink-500">
          Where news, insiders, and Congress agree.
        </p>
        {data?.feed_status?.congress !== "live" && data && (
          <p className="mt-2 rounded-card bg-accent-50 px-3 py-2 text-[12px] leading-snug text-accent-600">
            {data.feed_status.congress_note}
          </p>
        )}
      </div>

      {loading && <ListSkeleton />}

      {!loading && error && (
        <div className="mx-4 mt-6 rounded-card border border-dashed border-ink-100 bg-surface px-5 py-8 text-center">
          <p className="text-sm font-medium text-ink-700">Couldn't load scores</p>
          <p className="mt-1 text-[13px] text-ink-500">{error}</p>
        </div>
      )}

      {!loading && !error && data && data.tickers.length === 0 && (
        <EmptyFeedState mode="empty" sourceLabel="Money Match" />
      )}

      {!loading && !error && data && data.tickers.length > 0 && (
        <div className="space-y-3 px-4 pt-4">
          {data.tickers.map((t) => (
            <TickerCard key={t.ticker} ticker={t} />
          ))}
        </div>
      )}
    </div>
  );
}
