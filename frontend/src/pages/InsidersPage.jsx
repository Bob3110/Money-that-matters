import { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api.js";
import { ListSkeleton } from "../components/Skeletons.jsx";
import { FeedModeTag, EmptyFeedState } from "../components/FeedState.jsx";

export default function InsidersPage() {
  const [feed, setFeed] = useState(null);
  const [loading, setLoading] = useState(true);
  const [buysOnly, setBuysOnly] = useState(false);

  const load = useCallback(async (buys) => {
    setLoading(true);
    try {
      setFeed(await api.insiders(buys));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(buysOnly); }, [buysOnly, load]);

  return (
    <div className="pb-4">
      <div className="px-4 pt-4 flex items-center justify-between">
        <div>
          <h2 className="text-[22px] font-semibold text-ink-900">Insiders</h2>
          <p className="mt-0.5 text-[13px] text-ink-500">SEC Form 4 filings.</p>
        </div>
        {feed && <FeedModeTag mode={feed.mode} lastSuccessAt={feed.last_success_at} />}
      </div>

      <div className="px-4 pt-3">
        <button
          onClick={() => setBuysOnly((v) => !v)}
          className={`rounded-full border px-3 py-1.5 text-[12px] font-medium transition ${
            buysOnly ? "border-accent-500 bg-accent-50 text-accent-600" : "border-ink-100 text-ink-700"
          }`}
        >
          Buys only
        </button>
      </div>

      {loading && <ListSkeleton />}

      {!loading && feed && feed.items.length === 0 && (
        <EmptyFeedState mode={feed.mode} sourceLabel="Insiders" />
      )}

      {!loading && feed && feed.items.length > 0 && (
        <div className="space-y-3 px-4 pt-4">
          {feed.items.map((tx, i) => (
            <a key={i} href={tx.source_url} target="_blank" rel="noreferrer" className="block rounded-card bg-surface p-4 shadow-card">
              <div className="flex items-center justify-between">
                <span className="text-[15px] font-semibold text-ink-900">{tx.ticker}</span>
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${tx.transaction === "buy" ? "bg-bull/10 text-bull" : "bg-bear/10 text-bear"}`}>
                  {tx.transaction === "buy" ? "Buy" : "Sell"}
                </span>
              </div>
              <p className="mt-1 text-[13px] text-ink-700">{tx.insider_name} · {tx.insider_role}</p>
              <div className="mt-2 flex items-center justify-between text-[12px] text-ink-500">
                <span className="num">{tx.shares?.toLocaleString()} sh{tx.value_usd ? ` · $${Math.round(tx.value_usd).toLocaleString()}` : ""}</span>
                <span className="num">{formatDate(tx.filed_at)}</span>
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

function formatDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
