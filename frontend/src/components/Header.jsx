import { useState } from "react";
import { api } from "../lib/api.js";

export default function Header({ onRefreshed }) {
  const [spinning, setSpinning] = useState(false);

  async function handleRefresh() {
    if (spinning) return;
    setSpinning(true);
    try {
      await api.refresh();
      await onRefreshed?.();
    } catch {
      // Refresh failures surface via each tab's own feed status, not here.
    } finally {
      setSpinning(false);
    }
  }

  return (
    <header className="sticky top-0 z-20 flex items-center justify-between bg-surface/90 backdrop-blur px-4 py-3 border-b border-ink-100">
      <h1 className="text-[17px] font-semibold text-ink-900 tracking-tight">
        Money that matters
      </h1>
      <button
        onClick={handleRefresh}
        aria-label="Refresh"
        className="flex h-9 w-9 items-center justify-center rounded-full border border-ink-100 text-ink-700 active:scale-95 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
      >
        <svg
          className={spinning ? "animate-spin" : ""}
          width="18" height="18" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
        >
          <path d="M21 12a9 9 0 1 1-2.64-6.36" />
          <path d="M21 4v6h-6" />
        </svg>
      </button>
    </header>
  );
}
