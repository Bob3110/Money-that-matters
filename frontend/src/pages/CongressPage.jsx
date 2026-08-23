import { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api.js";
import { ListSkeleton } from "../components/Skeletons.jsx";
import { FeedModeTag, EmptyFeedState } from "../components/FeedState.jsx";

export default function CongressPage() {
  const [feed, setFeed] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setFeed(await api.congress());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="pb-4">
      <div className="px-4 pt-4 flex items-center justify-between">
        <div>
          <h2 className="text-[22px] font-semibold text-ink-900">Congress</h2>
          <p className="mt-0.5 text-[13px] text-ink-500">House financial disclosures.</p>
        </div>
        {feed && <FeedModeTag mode={feed.mode} lastSuccessAt={feed.last_success_at} />}
      </div>

      <div className="mx-4 mt-3 rounded-card bg-ink-100/60 px-3 py-2.5 text-[12px] leading-snug text-ink-700">
        These are filings, not parsed trades — no ticker or buy/sell direction is
        available from the free source, so Congress never contributes to the Money
        Match score. Tap a row to open the original filing.
        {feed?.legal_notice && (
          <span className="mt-1.5 block text-ink-500">{feed.legal_notice}</span>
        )}
      </div>

      {loading && <ListSkeleton />}

      {!loading && feed && feed.items.length === 0 && (
        <EmptyFeedState mode={feed.mode} sourceLabel="Congress" />
      )}

      {!loading && feed && feed.items.length > 0 && (
        <div className="space-y-3 px-4 pt-4">
          {feed.items.map((d, i) => (
            <a key={i} href={d.document_url} target="_blank" rel="noreferrer" className="block rounded-card bg-surface p-4 shadow-card">
              <div className="flex items-center justify-between">
                <span className="text-[14px] font-semibold text-ink-900">{d.member_name}</span>
                <span className="num text-[12px] text-ink-500">{formatDate(d.filing_date)}</span>
              </div>
              <p className="mt-1 text-[12px] text-ink-500">{d.district ? `District ${d.district}` : "District unknown"} · Doc #{d.document_id}</p>
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
