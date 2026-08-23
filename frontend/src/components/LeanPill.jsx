export default function LeanPill({ lean }) {
  const styles = {
    bullish: "bg-bull/10 text-bull",
    bearish: "bg-bear/10 text-bear",
    neutral: "bg-ink-100 text-ink-500",
  };
  const label = { bullish: "Bullish", bearish: "Bearish", neutral: "Neutral" };
  return (
    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${styles[lean] || styles.neutral}`}>
      {label[lean] || "Neutral"}
    </span>
  );
}
