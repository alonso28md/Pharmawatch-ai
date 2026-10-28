import { ArrowLeft, ChevronLeft, ChevronRight, Info } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useI18n } from "@/app/preferencesContext";
import { ErrorNotice } from "@/components/ErrorNotice";
import { IncidentResult } from "@/components/incident/IncidentResult";
import { IncidentTable } from "@/components/incident/IncidentTable";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/form";
import { Panel, Skeleton } from "@/components/ui/primitives";
import { ApiError } from "@/lib/api/client";
import { type ReportFilters, useReport, useReports } from "@/lib/api/queries";

const PAGE_SIZE = 10;

function ReadOnlyNote() {
  const { t } = useI18n();
  return (
    <p className="mb-4 flex items-center gap-2 text-small text-ink-muted">
      <Info className="size-4 shrink-0" aria-hidden="true" />
      {t.review.readOnly}
    </p>
  );
}

/** Escalated incidents; filters and page live in the URL so views can be linked and reloaded. */
export function ReviewPage() {
  const { t, number } = useI18n();
  const [params, setParams] = useSearchParams();
  const escalation = (params.get("escalation") ?? "escalated") as NonNullable<ReportFilters["escalation"]>;
  const severity = (params.get("severity") || undefined) as ReportFilters["severity"];
  const dateFrom = params.get("from") ?? "";
  const dateTo = params.get("to") ?? "";
  const page = Math.max(1, Number(params.get("page") ?? 1) || 1);

  const query = useReports({
    escalation,
    severity,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  });
  const total = query.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function update(changes: Record<string, string>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    if (!("page" in changes)) next.delete("page");
    setParams(next, { replace: true });
  }

  return (
    <>
      <PageHeader title={t.pages.review.title} subtitle={t.pages.review.subtitle} />
      <ReadOnlyNote />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[260px_minmax(0,1fr)]">
        <Panel title={t.review.filtersTitle} className="h-fit">
          <div className="space-y-4">
            <Field label={t.review.escalationLabel}>
              {({ id }) => (
                <Select id={id} value={escalation} onChange={(e) => update({ escalation: e.target.value === "escalated" ? "" : e.target.value })}>
                  <option value="escalated">{t.review.escalationAll}</option>
                  <option value="blocking">{t.review.escalationBlocking}</option>
                  <option value="advisory">{t.review.escalationAdvisory}</option>
                </Select>
              )}
            </Field>
            <Field label={t.review.severityLabel}>
              {({ id }) => (
                <Select id={id} value={severity ?? ""} onChange={(e) => update({ severity: e.target.value })}>
                  <option value="">{t.review.severityAll}</option>
                  <option value="serious">{t.review.severitySerious}</option>
                  <option value="non-serious">{t.review.severityNonSerious}</option>
                </Select>
              )}
            </Field>
            <Field label={t.review.fromLabel}>
              {({ id }) => <Input id={id} type="date" value={dateFrom} onChange={(e) => update({ from: e.target.value })} />}
            </Field>
            <Field label={t.review.toLabel}>
              {({ id }) => <Input id={id} type="date" value={dateTo} onChange={(e) => update({ to: e.target.value })} />}
            </Field>
            <Button variant="ghost" size="sm" onClick={() => setParams(new URLSearchParams(), { replace: true })}>
              {t.review.clear}
            </Button>
          </div>
        </Panel>

        <Panel
          title={t.pages.review.title}
          description={query.data ? `${number(total)} ${t.review.results}` : undefined}
          aria-busy={query.isFetching}
        >
          {query.isPending ? (
            <div className="space-y-3">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-6 w-full" />)}</div>
          ) : query.isError ? (
            <ErrorNotice error={query.error} onRetry={() => query.refetch()} />
          ) : query.data.items.length === 0 ? (
            <p className="py-6 text-center text-body text-ink-muted">{t.review.empty}</p>
          ) : (
            <>
              <IncidentTable items={query.data.items} caption={t.pages.review.title} />
              <nav aria-label={t.review.page} className="mt-4 flex items-center justify-between gap-3">
                <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => update({ page: String(page - 1) })}>
                  <ChevronLeft aria-hidden="true" />
                  {t.review.previous}
                </Button>
                <span className="tabular text-small text-ink-muted">
                  {t.review.page} {page} {t.review.of} {pages}
                </span>
                <Button variant="secondary" size="sm" disabled={page >= pages} onClick={() => update({ page: String(page + 1) })}>
                  {t.review.next}
                  <ChevronRight aria-hidden="true" />
                </Button>
              </nav>
            </>
          )}
        </Panel>
      </div>
    </>
  );
}

export function ReviewDetailPage() {
  const { t } = useI18n();
  const { incidentId = "" } = useParams();
  const query = useReport(incidentId);
  const notFound = query.error instanceof ApiError && (query.error.status === 404 || query.error.status === 422);
  return (
    <>
      <div className="mb-4">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/review">
            <ArrowLeft aria-hidden="true" />
            {t.review.backToQueue}
          </Link>
        </Button>
      </div>
      <PageHeader title={`${t.triage.incident} ${incidentId}`} subtitle={t.pages.review.subtitle} />
      <ReadOnlyNote />
      {query.isPending ? (
        <Skeleton className="h-64 w-full" />
      ) : notFound ? (
        <p className="text-body text-ink-muted">{t.review.notFound}</p>
      ) : query.isError ? (
        <ErrorNotice error={query.error} onRetry={() => query.refetch()} />
      ) : (
        <IncidentResult result={query.data} />
      )}
    </>
  );
}
