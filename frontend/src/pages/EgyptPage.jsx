import { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api.js";
import { ListSkeleton } from "../components/Skeletons.jsx";
import { FeedModeTag, EmptyFeedState } from "../components/FeedState.jsx";
import LeanPill from "../components/LeanPill.jsx";

export default function EgyptPage() {
  const [feed, setFeed] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setFeed(await api.egyptNews());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="pb-4">
      <div className="px-4 pt-4 flex items-center justify-between">
        <div>
          <h2 className="text-[22px] font-semibold text-ink-900">Egypt</h2>
          <p className="mt-0.5 text-[13px] text-ink-500">EGX-relevant news. Separate from Money Match.</p>
        </div>
        {feed && <FeedModeTag mode={feed.mode} lastSuccessAt={feed.last_success_at} />}
      </div>

      {loading && <ListSkeleton />}

      {!loading && feed && feed.items.length === 0 && (
        <EmptyFeedState mode={feed.mode} sourceLabel="Egypt News" />
      )}

      {!loading && feed && feed.items.length > 0 && (
        <div className="space-y-3 px-4 pt-4">
          {feed.items.map((item, i) => (
            <a key={i} href={item.source_url} target="_blank" rel="noreferrer" className="block rounded-card bg-surface p-4 shadow-card">
              <div className="flex items-center justify-between text-[11px] text-ink-500">
                <span className="font-medium text-ink-700">{item.outlet}</span>
                <span className="num">{formatDate(item.published_at)}</span>
              </div>
              <p dir="auto" className="mt-1.5 text-[14px] leading-snug text-ink-900">{item.headline}</p>
              <div className="mt-2 flex items-center justify-between">
                <span className="num text-[12px] font-semibold text-ink-700">{item.ticker || "Market-wide"}</span>
                <LeanPill lean={item.lean} />
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
