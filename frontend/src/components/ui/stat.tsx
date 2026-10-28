import type { ReactNode } from "react";
import { Skeleton } from "./primitives";

/** One divided container of figures: label above value, values as type (no icon tiles). */
export function StatGroup({ children, label }: { children: ReactNode; label: string }) {
  return (
    <dl aria-label={label} className="grid grid-cols-2 divide-line rounded-lg border border-line bg-surface sm:grid-cols-4 sm:divide-x">
      {children}
    </dl>
  );
}

export function Stat({ label, value, hint, loading }: { label: string; value: ReactNode; hint?: ReactNode; loading?: boolean }) {
  return (
    <div className="border-line px-5 py-4 max-sm:border-b max-sm:odd:border-r">
      <dt className="text-small text-ink-muted">{label}</dt>
      <dd className="mt-1">
        {loading ? (
          <Skeleton className="h-7 w-20" />
        ) : (
          <span className="tabular text-title font-semibold text-ink">{value}</span>
        )}
        {hint && !loading && <span className="ml-1.5 text-small text-ink-subtle">{hint}</span>}
      </dd>
    </div>
  );
}
