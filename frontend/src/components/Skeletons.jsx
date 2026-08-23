export function CardSkeleton() {
  return (
    <div className="rounded-card bg-surface p-4 shadow-card">
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <div className="skeleton h-4 w-16 rounded" />
          <div className="skeleton h-3 w-28 rounded" />
        </div>
        <div className="skeleton h-9 w-14 rounded" />
      </div>
    </div>
  );
}

export function ListSkeleton({ count = 6 }) {
  return (
    <div className="space-y-3 px-4 pt-4">
      {Array.from({ length: count }).map((_, i) => (
        <CardSkeleton key={i} />
      ))}
    </div>
  );
}
