import { useId, useState } from "react";
import { useI18n } from "@/app/preferencesContext";
import { ErrorNotice } from "@/components/ErrorNotice";
import { PageHeader } from "@/components/layout/PageHeader";
import { BarChartFrame } from "@/components/ui/BarChartFrame";
import { Panel, Skeleton } from "@/components/ui/primitives";
import { Stat, StatGroup } from "@/components/ui/stat";
import { useMetrics } from "@/lib/api/queries";

const CLASS_ORDER = ["I", "IIa", "IIb", "III"];

export function OperationsPage() {
  const { t, number, percent } = useI18n();
  const [includeDemo, setIncludeDemo] = useState(false);
  const toggleId = useId();
  const query = useMetrics(includeDemo);
  const m = query.data;
  const ms = (v: number) => `${number(v / 1000, { maximumFractionDigits: 2 })} s`;

  const severityLabel: Record<string, string> = {
    serious: t.operations.serious,
    "non-serious": t.operations.nonSerious,
    escalated: t.operations.escalated,
  };
  const outcomes = m
    ? Object.entries(m.classification_distribution).map(([key, value]) => ({ label: severityLabel[key] ?? key, value }))
    : [];
  const classes = m
    ? Object.entries(m.top_device_classes)
        .sort(([a], [b]) => CLASS_ORDER.indexOf(a) - CLASS_ORDER.indexOf(b))
        .map(([label, value]) => ({ label, value }))
    : [];

  return (
    <>
      <PageHeader
        title={t.pages.operations.title}
        subtitle={t.pages.operations.subtitle}
        actions={
          <label htmlFor={toggleId} className="flex min-h-11 cursor-pointer items-center gap-2 text-body text-ink">
            <input
              id={toggleId}
              type="checkbox"
              className="size-4 accent-[var(--pw-accent)]"
              checked={includeDemo}
              onChange={(e) => setIncludeDemo(e.target.checked)}
            />
            {t.operations.includeDemo}
          </label>
        }
      />
      {query.isError ? (
        <ErrorNotice error={query.error} onRetry={() => query.refetch()} />
      ) : (
        <div className="space-y-6" aria-busy={query.isFetching}>
          <section aria-labelledby="latency-title">
            <h2 id="latency-title" className="mb-3 text-title-sm font-semibold text-ink">
              {t.operations.latencyTitle}
            </h2>
            <StatGroup label={t.operations.latencyTitle}>
              <Stat label={t.dashboard.latencyP50} loading={query.isPending} value={m?.latency_samples ? ms(m.p50_latency_ms) : t.common.none} />
              <Stat label={t.dashboard.latencyP95} loading={query.isPending} value={m?.latency_samples ? ms(m.p95_latency_ms) : t.common.none} />
              <Stat label={t.operations.avg} loading={query.isPending} value={m?.latency_samples ? ms(m.avg_latency_ms) : t.common.none} />
              <Stat label={t.operations.samples} loading={query.isPending} value={m ? number(m.latency_samples) : null} />
            </StatGroup>
          </section>

          <section aria-labelledby="errors-title">
            <h2 id="errors-title" className="mb-3 text-title-sm font-semibold text-ink">
              {t.operations.errorsTitle}
            </h2>
            <StatGroup label={t.operations.errorsTitle}>
              <Stat label={t.operations.server} loading={query.isPending} value={m ? percent(m.error_rate, 1) : null} />
              <Stat label={t.operations.client} loading={query.isPending} value={m ? percent(m.client_error_rate, 1) : null} />
              <Stat label={t.operations.escalated} loading={query.isPending} value={m ? percent(m.escalation_rate, 0) : null} />
              <Stat label={t.operations.blocking} loading={query.isPending} value={m ? percent(m.blocking_escalation_rate, 0) : null} />
            </StatGroup>
          </section>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Panel title={t.operations.outcomesTitle} headingLevel={2}>
              {query.isPending ? <Skeleton className="h-48 w-full" /> : <BarChartFrame data={outcomes} title={t.operations.outcomesTitle} />}
            </Panel>
            <Panel title={t.operations.classesTitle} headingLevel={2}>
              {query.isPending ? <Skeleton className="h-48 w-full" /> : <BarChartFrame data={classes} title={t.operations.classesTitle} />}
            </Panel>
          </div>
        </div>
      )}
    </>
  );
}
