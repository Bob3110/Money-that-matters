import { NavLink } from "react-router-dom";

const TABS = [
  { to: "/", label: "Match", icon: HomeIcon },
  { to: "/news", label: "News", icon: NewsIcon },
  { to: "/insiders", label: "Insiders", icon: InsidersIcon },
  { to: "/congress", label: "Congress", icon: CongressIcon },
  { to: "/egypt", label: "Egypt", icon: EgyptIcon },
  { to: "/watchlist", label: "Watchlist", icon: StarIcon },
];

export default function BottomNav() {
  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-20 grid grid-cols-6 border-t border-ink-100 bg-surface/95 backdrop-blur"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      {TABS.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          end={to === "/"}
          className={({ isActive }) =>
            `flex flex-col items-center justify-center gap-1 py-2.5 min-h-[56px] text-[10.5px] font-medium transition-colors ${
              isActive ? "text-accent-500" : "text-ink-500"
            }`
          }
        >
          {({ isActive }) => (
            <>
              <Icon active={isActive} />
              <span>{label}</span>
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}

function HomeIcon({ active }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={active ? 2.4 : 2}>
      <path d="M13 2 3 14h7l-1 8 11-14h-7l1-6Z" strokeLinejoin="round" />
    </svg>
  );
}
function NewsIcon({ active }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={active ? 2.4 : 2}>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M7 8h10M7 12h10M7 16h6" strokeLinecap="round" />
    </svg>
  );
}
function InsidersIcon({ active }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={active ? 2.4 : 2}>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7" strokeLinecap="round" />
    </svg>
  );
}
function CongressIcon({ active }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={active ? 2.4 : 2}>
      <path d="M4 21h16M6 21V10M18 21V10M12 3 4 8h16L12 3Z" strokeLinejoin="round" />
    </svg>
  );
}
function EgyptIcon({ active }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={active ? 2.4 : 2}>
      <path d="M3 18 12 4l9 14" strokeLinejoin="round" />
      <path d="M7 18v-5M12 18v-8M17 18v-5" />
    </svg>
  );
}
function StarIcon({ active }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill={active ? "currentColor" : "none"} stroke="currentColor" strokeWidth={active ? 1.5 : 2}>
      <path d="m12 3 2.7 5.8 6.3.6-4.7 4.3 1.3 6.3L12 17l-5.6 3 1.3-6.3-4.7-4.3 6.3-.6L12 3Z" strokeLinejoin="round" />
    </svg>
  );
}
