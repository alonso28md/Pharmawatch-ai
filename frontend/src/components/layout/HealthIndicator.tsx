import { CircleAlert, CircleCheck, CircleDashed, CircleOff } from "lucide-react";
import { useI18n } from "@/app/preferencesContext";
import { Tooltip } from "@/components/ui/primitives";
import { useHealth } from "@/lib/api/queries";
import { cn } from "@/lib/utils";

/** Compact system status from GET /health (icon + text, never colour alone). */
export function HealthIndicator() {
  const { t, number } = useI18n();
  const { data, isPending, isError } = useHealth();

  const status = isPending ? "checking" : isError ? "unreachable" : data?.status ?? "unreachable";
  const Icon = { checking: CircleDashed, healthy: CircleCheck, degraded: CircleAlert, unreachable: CircleOff }[status];
  const tone = {
    checking: "text-ink-subtle",
    healthy: "text-ok",
    degraded: "text-serious",
    unreachable: "text-critical",
  }[status];

  const detail = data ? (
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
      <dt className="text-ink-muted">{t.health.vectorstore}</dt>
      <dd className="tabular">
        {data.vectorstore === "connected" ? t.health.connected : t.health.unavailable} ·{" "}
        {number(data.vectorstore_documents)} {t.health.documents}
      </dd>
      <dt className="text-ink-muted">{t.health.database}</dt>
      <dd>{data.database === "connected" ? t.health.connected : t.health.unavailable}</dd>
      <dt className="text-ink-muted">{t.health.model}</dt>
      <dd className="font-mono text-caption" translate="no">
        {data.model}
      </dd>
    </dl>
  ) : (
    t.health[status as "checking" | "unreachable"]
  );

  return (
    <Tooltip content={detail}>
      <button
        type="button"
        className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-small text-ink-muted hover:bg-surface-sunken"
        aria-label={`${t.health.label}: ${t.health[status]}`}
      >
        <Icon className={cn("size-4 shrink-0", tone)} aria-hidden="true" />
        <span>{t.health[status]}</span>
        {data && (
          <span className="ml-auto font-mono text-caption text-ink-subtle" translate="no">
            v{data.version}
          </span>
        )}
      </button>
    </Tooltip>
  );
}
