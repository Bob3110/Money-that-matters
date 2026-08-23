const BASE = import.meta.env.VITE_API_BASE || "/api";

async function getJson(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    throw new Error(`Request to ${path} failed with ${res.status}`);
  }
  return res.json();
}

export const api = {
  moneyMatch: () => getJson("/money-match"),
  marketNews: () => getJson("/market-news"),
  insiders: (buysOnly = false) => getJson(`/insiders${buysOnly ? "?buys_only=true" : ""}`),
  congress: () => getJson("/congress"),
  egyptNews: () => getJson("/egypt-news"),
  refresh: async () => {
    const res = await fetch(`${BASE.replace(/\/api$/, "")}/api/refresh`, { method: "POST" });
    if (!res.ok) throw new Error("Refresh failed");
    return res.json();
  },
};
