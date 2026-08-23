const KEY = "mtm.watchlist.v1";

export function getWatchlist() {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function isWatched(ticker) {
  return getWatchlist().includes(ticker);
}

export function toggleWatch(ticker) {
  const current = getWatchlist();
  const next = current.includes(ticker)
    ? current.filter((t) => t !== ticker)
    : [...current, ticker];
  localStorage.setItem(KEY, JSON.stringify(next));
  return next;
}
