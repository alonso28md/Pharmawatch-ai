import { ArrowRight, ClipboardList, MessageSquareText, Stethoscope } from "lucide-react";
import { Link } from "react-router-dom";
import { useI18n } from "@/app/preferencesContext";
import { ErrorNotice } from "@/components/ErrorNotice";
import { IncidentTable } from "@/components/incident/IncidentTable";
import { PageHeader } from "@/components/layout/PageHeader";
import { Panel, Skeleton } from "@/components/ui/primitives";
import { Stat, StatGroup } from "@/components/ui/stat";
import { useHealth, useMetrics, useReports } from "@/lib/api/queries";

const QUICK = [
  { to: "/triage", key: "quickTriage", icon: Stethoscope },
  { to: "/ask", key: "quickAsk", icon: MessageSquareText },
  { to: "/review", key: "quickReview", icon: ClipboardList },
] as const;

export function DashboardPage() {
  const { t, number, percent } = useI18n();
  const metrics = useMetrics();
  const recent = useReports({ limit: 5 });
  const health = useHealth();
  const m = metrics.data;
  const ms = (v: number) => `${number(v / 1000, { maximumFractionDigits: 1 })} s`;

  return (
    <>
      <PageHeader title={t.pages.dashboard.title} subtitle={t.pages.dashboard.subtitle} />
      <div className="space-y-6">
        <section aria-labelledby="activity-title">
          <h2 id="activity-title" className="mb-3 text-title-sm font-semibold text-ink">
            {t.dashboard.activityTitle}
          </h2>
          {metrics.isError ? (
            <ErrorNotice error={metrics.error} onRetry={() => metrics.refetch()} />
          ) : (
            <StatGroup label={t.dashboard.activityTitle}>
              <Stat label={t.dashboard.requests24h} loading={metrics.isPending} value={m ? number(m.queries_last_24h) : null} />
              <Stat
                label={t.dashboard.latencyP50}
                loading={metrics.isPending}
                value={m && m.latency_samples ? ms(m.p50_latency_ms) : t.common.none}
                hint={m && m.latency_samples ? `p95 ${ms(m.p95_latency_ms)}` : undefined}
              />
              <Stat label={t.dashboard.escalationRate} loading={metrics.isPending} value={m ? percent(m.escalation_rate, 0) : null} />
              <Stat label={t.dashboard.errorRate} loading={metrics.isPending} value={m ? percent(m.error_rate, 1) : null} />
            </StatGroup>
          )}
          {m && m.total_queries === 0 && <p className="mt-2 text-small text-ink-muted">{t.dashboard.noTraffic}</p>}
        </section>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <Panel
            title={t.dashboard.recentTitle}
            actions={
              <Link to="/review" className="text-small text-accent underline-offset-2 hover:underline">
                {t.common.viewAll}
              </Link>
            }
          >
            {recent.isPending ? (
              <div className="space-y-3">
                {[0, 1, 2].map((i) => <Skeleton key={i} className="h-6 w-full" />)}
              </div>
            ) : recent.isError ? (
              <ErrorNotice error={recent.error} onRetry={() => recent.refetch()} />
            ) : recent.data.items.length === 0 ? (
              <p className="text-body text-ink-muted">{t.dashboard.noIncidents}</p>
            ) : (
              <IncidentTable items={recent.data.items} caption={t.dashboard.recentTitle} />
            )}
          </Panel>

          <div className="space-y-6">
            <Panel title={t.dashboard.healthTitle}>
              {health.data ? (
                <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-body">
                  <dt className="text-ink-muted">{t.health.label}</dt>
                  <dd className="font-semibold">{t.health[health.data.status]}</dd>
                  <dt className="text-ink-muted">{t.health.vectorstore}</dt>
                  <dd className="tabular">
                    {health.data.vectorstore === "connected" ? t.health.connected : t.health.unavailable} · {number(health.data.vectorstore_documents)}{" "}
                    {t.health.documents}
                  </dd>
                  <dt className="text-ink-muted">{t.health.database}</dt>
                  <dd>{health.data.database === "connected" ? t.health.connected : t.health.unavailable}</dd>
                  <dt className="text-ink-muted">{t.health.model}</dt>
                  <dd className="font-mono text-small" translate="no">{health.data.model}</dd>
                  <dt className="text-ink-muted">{t.dashboard.uptime}</dt>
                  <dd className="tabular">{number(health.data.uptime_seconds / 3600, { maximumFractionDigits: 1 })}{" "}h</dd>
                </dl>
              ) : health.isError ? (
                <p className="text-body text-critical">{t.health.unreachable}</p>
              ) : (
                <Skeleton className="h-24 w-full" />
              )}
            </Panel>

            <Panel title={t.dashboard.quickTitle}>
              <ul className="-my-1 divide-y divide-line">
                {QUICK.map(({ to, key, icon: Icon }) => (
                  <li key={to}>
                    <Link to={to} className="group flex min-h-11 items-center gap-3 py-2 text-body text-ink hover:text-accent">
                      <Icon className="size-4 text-ink-muted group-hover:text-accent" aria-hidden="true" />
                      {t.dashboard[key]}
                      <ArrowRight
                        className="ml-auto size-4 text-ink-subtle transition-transform duration-[140ms] group-hover:translate-x-0.5"
                        aria-hidden="true"
                      />
                    </Link>
                  </li>
                ))}
              </ul>
            </Panel>
          </div>
        </div>
      </div>
    </>
  );
}
