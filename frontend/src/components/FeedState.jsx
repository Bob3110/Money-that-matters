export function FeedModeTag({ mode, lastSuccessAt }) {
  if (mode === "live") {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] text-ink-500">
        <span className="h-1.5 w-1.5 rounded-full bg-bull" />
        Updated {relativeTime(lastSuccessAt)}
      </span>
    );
  }
  if (mode === "stale") {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] text-ink-500">
        <span className="h-1.5 w-1.5 rounded-full bg-[#D9A441]" />
        Showing last known data from {relativeTime(lastSuccessAt)} — source hasn't refreshed since
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-[11px] text-ink-500">
      <span className="h-1.5 w-1.5 rounded-full bg-ink-300" />
      Waiting for first sync
    </span>
  );
}

export function EmptyFeedState({ mode, sourceLabel }) {
  if (mode === "empty") {
    return (
      <div className="mx-4 mt-6 rounded-card border border-dashed border-ink-100 bg-surface px-5 py-8 text-center">
        <p className="text-sm font-medium text-ink-700">Waiting for first sync</p>
        <p className="mt-1 text-[13px] text-ink-500">
          {sourceLabel} hasn't synced yet. No data is shown until a real fetch succeeds.
        </p>
      </div>
    );
  }
  return (
    <div className="mx-4 mt-6 rounded-card border border-dashed border-ink-100 bg-surface px-5 py-8 text-center">
      <p className="text-sm font-medium text-ink-700">Nothing to show right now</p>
      <p className="mt-1 text-[13px] text-ink-500">
        {sourceLabel} is up to date but has no items matching this view.
      </p>
    </div>
  );
}

function relativeTime(iso) {
  if (!iso) return "—";
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  return `${days}d ago`;
}
