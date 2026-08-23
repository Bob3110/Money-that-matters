import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";
import LeanPill from "../components/LeanPill.jsx";
import { ListSkeleton } from "../components/Skeletons.jsx";

export default function TickerDetailPage() {
  const { ticker } = useParams();
  const navigate = useNavigate();
  const [card, setCard] = useState(null);
  const [news, setNews] = useState([]);
  const [insiderTx, setInsiderTx] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      const [mm, newsFeed, insidersFeed] = await Promise.all([
        api.moneyMatch(),
        api.marketNews(),
        api.insiders(),
      ]);
      if (cancelled) return;
      setCard(mm.tickers.find((t) => t.ticker === ticker) || null);
      setNews(newsFeed.items.filter((i) => i.ticker === ticker));
      setInsiderTx(insidersFeed.items.filter((i) => i.ticker === ticker));
      setLoading(false);
    })();
    return () => { cancelled = true; };
  }, [ticker]);

  if (loading) return <ListSkeleton count={4} />;

  return (
    <div className="pb-4">
      <div className="px-4 pt-4">
        <button onClick={() => navigate(-1)} className="text-[13px] text-ink-500">← Back</button>
        <div className="mt-2 flex items-center justify-between">
          <h2 className="text-[24px] font-semibold text-ink-900">{ticker}</h2>
          {card && (
            <span className={`num text-3xl font-semibold ${card.direction === "bullish" ? "text-bull" : card.direction === "bearish" ? "text-bear" : "text-ink-500"}`}>
              {card.score}
            </span>
          )}
        </div>
        {card?.strong_match && (
          <span className="mt-1 inline-flex items-center gap-1 rounded-full bg-accent-50 px-2 py-1 text-[11px] font-semibold text-accent-600">
            ⚡ Strong Match — all three sources agree
          </span>
        )}
      </div>

      <section className="mt-5 px-4">
        <h3 className="text-[13px] font-semibold uppercase tracking-wide text-ink-500">Market News</h3>
        {news.length === 0 && <p className="mt-2 text-[13px] text-ink-500">No allow-listed headlines for {ticker} right now.</p>}
        <div className="mt-2 space-y-2">
          {news.map((item, i) => (
            <a key={i} href={item.source_url} target="_blank" rel="noreferrer" className="block rounded-card bg-surface p-3 shadow-card">
              <p className="text-[13px] text-ink-900">{item.headline}</p>
              <div className="mt-1.5 flex items-center justify-between text-[11px] text-ink-500">
                <span>{item.outlet}</span>
                <LeanPill lean={item.lean} />
              </div>
            </a>
          ))}
        </div>
      </section>

      <section className="mt-5 px-4">
        <h3 className="text-[13px] font-semibold uppercase tracking-wide text-ink-500">Insider Filings</h3>
        {insiderTx.length === 0 && <p className="mt-2 text-[13px] text-ink-500">No recent Form 4 filings for {ticker}.</p>}
        <div className="mt-2 space-y-2">
          {insiderTx.map((tx, i) => (
            <a key={i} href={tx.source_url} target="_blank" rel="noreferrer" className="block rounded-card bg-surface p-3 shadow-card">
              <div className="flex items-center justify-between">
                <span className="text-[13px] text-ink-900">{tx.insider_name}</span>
                <span className={`text-[11px] font-semibold ${tx.transaction === "buy" ? "text-bull" : "text-bear"}`}>
                  {tx.transaction === "buy" ? "Buy" : "Sell"}
                </span>
              </div>
              <p className="num mt-1 text-[11px] text-ink-500">{tx.shares?.toLocaleString()} shares</p>
            </a>
          ))}
        </div>
      </section>

      <section className="mt-5 px-4">
        <h3 className="text-[13px] font-semibold uppercase tracking-wide text-ink-500">Congress</h3>
        <p className="mt-2 text-[13px] text-ink-500">
          The free House Clerk data doesn't carry a ticker per filing, so no
          per-ticker Congress data can be shown here — see the Congress tab
          for the raw filings feed.
        </p>
      </section>
    </div>
  );
}
