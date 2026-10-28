import { CircleCheck, CircleHelp, FlaskConical, Info, TriangleAlert } from "lucide-react";
import { useI18n } from "@/app/preferencesContext";
import { ErrorNotice } from "@/components/ErrorNotice";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge, Panel, Skeleton, Tooltip } from "@/components/ui/primitives";
import type { Messages } from "@/i18n/es";
import { ApiError } from "@/lib/api/client";
import { type EvaluationLatest, useLatestEvaluation } from "@/lib/api/queries";

/** Typographic comparison operators for thresholds. */
const OPS: Record<string, string> = { ">=": "≥", "<=": "≤" };

type MetricKey = keyof Messages["evaluation"]["metrics"];
type Stat = EvaluationLatest["metric_summary"][string];

const GROUPS: Record<keyof Messages["evaluation"]["groups"], MetricKey[]> = {
  rag: [
    "retrieval_accuracy", "section_retrieval_accuracy", "answer_accuracy", "abstention_accuracy",
    "false_abstention_rate", "source_citation_rate", "answer_faithfulness", "hallucination_rate",
    "numeric_grounding_rate",
  ],
  classification: [
    "classification_accuracy", "category_accuracy", "reportability_accuracy", "deadline_accuracy",
    "recipients_accuracy", "deadline_accuracy_decided", "recipients_accuracy_decided", "provenance_accuracy",
  ],
  safety: [
    "unescalated_error_rate", "dangerous_unescalated_error_rate", "decision_rate", "escalation_rate",
    "escalation_precision", "escalation_recall", "over_escalation_rate", "review_agreement_rate",
  ],
  latency: ["rag_latency_p50_ms", "rag_latency_p95_ms", "report_latency_p50_ms", "report_latency_p95_ms"],
};

function fill(template: string, values: Record<string, string>) {
  return template.replace(/\{(\w+)\}/g, (_, k: string) => values[k] ?? "");
}

function useFormat() {
  const { number, percent } = useI18n();
  return (key: string, value: number | null | undefined) =>
    value == null ? "—" : key.endsWith("_ms") ? `${number(value / 1000, { maximumFractionDigits: 1 })} s` : percent(value, 1);
}

/** Min–max range bar on a 0–1 scale with the mean marked and the threshold as a tick. */
function RangeBar({ stat }: { stat: Stat }) {
  if (stat.min == null || stat.max == null || stat.mean == null) return null;
  const threshold = stat.threshold?.value as number | undefined;
  return (
    <div className="relative h-2 w-28 rounded-full bg-surface-sunken" aria-hidden="true">
      <span
        className="absolute inset-y-0 rounded-full bg-accent/35"
        style={{ left: `${stat.min * 100}%`, width: `${Math.max((stat.max - stat.min) * 100, 1.5)}%` }}
      />
      <span className="absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent" style={{ left: `${stat.mean * 100}%` }} />
      {threshold != null && <span className="absolute -top-1 h-4 w-px bg-ink" style={{ left: `${threshold * 100}%` }} />}
    </div>
  );
}

function Status({ stat }: { stat: Stat | undefined }) {
  const { t } = useI18n();
  if (!stat || stat.n === 0 || stat.mean == null) return <Badge tone="neutral">{t.evaluation.na}</Badge>;
  const gate = (stat.threshold as { gate?: boolean } | null)?.gate !== false;
  if (stat.meets_threshold == null) return <Badge tone="neutral">{t.evaluation.info}</Badge>;
  const badge = stat.meets_threshold ? (
    <Badge tone="ok"><CircleCheck aria-hidden="true" />{t.evaluation.pass}</Badge>
  ) : (
    <Badge tone="serious"><TriangleAlert aria-hidden="true" />{t.evaluation.fail}</Badge>
  );
  return gate ? badge : <span className="inline-flex items-center gap-1.5">{badge}<span className="text-caption text-ink-subtle">({t.evaluation.info})</span></span>;
}

function MetricTable({ title, keys, data }: { title: string; keys: MetricKey[]; data: EvaluationLatest }) {
  const { t } = useI18n();
  const format = useFormat();
  return (
    <Panel title={title} headingLevel={3}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-body">
          <caption className="sr-only">{title}</caption>
          <thead>
            <tr className="border-b border-line text-small text-ink-muted">
              <th scope="col" className="py-2 pr-4 font-medium">{t.evaluation.columns.metric}</th>
              <th scope="col" className="py-2 pr-4 text-right font-medium">{t.evaluation.columns.mean}</th>
              <th scope="col" className="py-2 pr-4 font-medium">{t.evaluation.columns.range}</th>
              <th scope="col" className="py-2 pr-4 font-medium">{t.evaluation.columns.threshold}</th>
              <th scope="col" className="py-2 font-medium">{t.evaluation.columns.status}</th>
            </tr>
          </thead>
          <tbody>
            {keys.map((key) => {
              const stat = data.metric_summary[key];
              const threshold = stat?.threshold as { op: string; value: number } | null | undefined;
              return (
                <tr key={key} className="border-b border-line last:border-0">
                  <th scope="row" className="py-2.5 pr-4 font-normal">
                    <span className="flex items-center gap-1.5">
                      <span className="font-mono text-small text-ink" translate="no">{key}</span>
                      <Tooltip content={<><span className="font-semibold">{t.evaluation.howComputed}: </span>{t.evaluation.metrics[key]}</>}>
                        <button type="button" className="rounded-sm text-ink-subtle hover:text-ink" aria-label={`${t.evaluation.howComputed}: ${t.evaluation.metrics[key]}`}>
                          <CircleHelp className="size-4" aria-hidden="true" />
                        </button>
                      </Tooltip>
                    </span>
                  </th>
                  <td className="tabular py-2.5 pr-4 text-right font-semibold">{format(key, stat?.mean)}</td>
                  <td className="py-2.5 pr-4">
                    <span className="flex items-center gap-3">
                      {!key.endsWith("_ms") && stat && <RangeBar stat={stat} />}
                      <span className="tabular text-small text-ink-muted whitespace-nowrap">
                        {stat?.min != null ? `${format(key, stat.min)}–${format(key, stat.max)}` : "—"}
                      </span>
                    </span>
                  </td>
                  <td className="tabular py-2.5 pr-4 text-small whitespace-nowrap text-ink-muted">
                    {threshold ? `${OPS[threshold.op] ?? threshold.op} ${format(key, threshold.value)}` : "—"}
                  </td>
                  <td className="py-2.5">
                    <Status stat={stat} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

export function EvaluationPage() {
  const { t, number, dateTime } = useI18n();
  const query = useLatestEvaluation();
  const data = query.data;
  const meta = (data?.metadata ?? {}) as Record<string, unknown>;
  const usage = meta.usage as Record<string, { calls: number; input_tokens: number; output_tokens: number }> | undefined;
  const summary = (data?.summary ?? {}) as { total_cases?: number; passed?: number; flaky_cases?: string[] };
  const cases = meta.cases as { rag?: number; classification?: number } | undefined;
  const excluded = (meta.excluded_pending_expert_review as string[] | undefined) ?? [];

  return (
    <>
      <PageHeader title={t.pages.evaluation.title} subtitle={t.pages.evaluation.subtitle} />
      <div className="mb-5 flex flex-wrap gap-2">
        <Badge tone="info"><Info aria-hidden="true" />{t.evaluation.draftLabels}</Badge>
        <Badge tone="info"><Info aria-hidden="true" />{t.evaluation.proposedThresholds}</Badge>
      </div>

      {query.isPending ? (
        <Skeleton className="h-72 w-full" />
      ) : query.error instanceof ApiError && query.error.status === 404 ? (
        <p className="text-body text-ink-muted">{t.evaluation.none}</p>
      ) : query.isError ? (
        <ErrorNotice error={query.error} onRetry={() => query.refetch()} />
      ) : data ? (
        <div className="space-y-6">
          <Panel title={t.evaluation.provenanceTitle}>
            <dl className="grid gap-x-8 gap-y-2 text-body sm:grid-cols-2 lg:grid-cols-3">
              {[
                [t.evaluation.file, <span key="v" className="font-mono text-small break-all" translate="no">{data.file}</span>],
                [t.evaluation.date, data.timestamp ? dateTime(data.timestamp) : "—"],
                [t.evaluation.model, <span key="v" className="font-mono text-small" translate="no">{String(meta.model ?? "—")}</span>],
                [t.evaluation.judge, <span key="v" className="font-mono text-small" translate="no">{String(meta.judge_model ?? "—")}</span>],
                [t.evaluation.commit, <span key="v" className="font-mono text-small" translate="no">{String(meta.git_commit ?? "—")}</span>],
                [t.evaluation.split, `${String(meta.split ?? "—")} · ${String(meta.dataset ?? "")} v${String(meta.dataset_version ?? "")}`],
                [t.evaluation.repetitions, String(meta.repetitions ?? "—")],
                [
                  t.evaluation.cases,
                  cases ? (
                    <>
                      {number((cases.rag ?? 0) + (cases.classification ?? 0))}{" "}
                      <span className="text-small text-ink-muted">({fill(t.evaluation.casesLine, { rag: number(cases.rag ?? 0), classification: number(cases.classification ?? 0) })})</span>
                    </>
                  ) : "—",
                ],
                [t.evaluation.excluded, number(excluded.length)],
                [t.evaluation.passedAll, summary.total_cases ? `${summary.passed} / ${summary.total_cases}` : "—"],
                [t.evaluation.flaky, number(summary.flaky_cases?.length ?? 0)],
                [
                  t.evaluation.usage,
                  usage ? (
                    <ul key="v" className="text-small">
                      {Object.entries(usage).map(([role, u]) => (
                        <li key={role}>
                          <span className="font-mono" translate="no">{role}</span>:{" "}
                          {fill(t.evaluation.usageLine, { calls: number(u.calls), input: number(u.input_tokens), output: number(u.output_tokens) })}
                        </li>
                      ))}
                    </ul>
                  ) : "—",
                ],
              ].map(([label, value], i) => (
                <div key={i} className="min-w-0">
                  <dt className="text-small text-ink-muted">{label}</dt>
                  <dd className="min-w-0">{value}</dd>
                </div>
              ))}
            </dl>
            {data.source === "snapshot" && (
              <p className="mt-3 flex items-center gap-2 text-small text-ink-muted">
                <Info className="size-4 shrink-0" aria-hidden="true" />
                {t.evaluation.snapshot}
              </p>
            )}
            {data.rescored && (
              <p className="mt-3 flex items-center gap-2 text-small text-ink-muted">
                <FlaskConical className="size-4" aria-hidden="true" />
                {t.evaluation.rescored}
              </p>
            )}
          </Panel>

          {(Object.keys(GROUPS) as (keyof typeof GROUPS)[]).map((group) => (
            <MetricTable key={group} title={t.evaluation.groups[group]} keys={GROUPS[group]} data={data} />
          ))}

          {data.failed_cases.length > 0 && (
            <Panel title={`${t.evaluation.failedTitle} (${data.failed_cases.length})`}>
              <details>
                <summary className="cursor-pointer text-small text-ink-muted select-none">{t.common.details}</summary>
                <ul className="mt-3 divide-y divide-line">
                  {data.failed_cases.map((c) => (
                    <li key={String(c.case_id)} className="py-2 text-small">
                      <span className="font-mono text-ink" translate="no">{String(c.case_id)}</span>
                      <span className="text-ink-muted"> — {String(c.reason)}</span>
                    </li>
                  ))}
                </ul>
              </details>
            </Panel>
          )}
        </div>
      ) : null}
    </>
  );
}
