import { motion } from "motion/react";
import { BookOpen, Building2, Cpu, Factory } from "lucide-react";
import { useI18n } from "@/app/preferencesContext";
import { Badge, Panel, Tooltip } from "@/components/ui/primitives";
import type { ReportResponse } from "@/lib/api/client";
import { DeadlineRing } from "./DeadlineRing";
import { DraftEditor } from "./DraftEditor";
import { categoryTone } from "@/lib/incident";
import { CategoryBadge, EscalationNotice, type EscalationLevel } from "./status";

const RECIPIENT_ICON = { competent_authority: Building2, manufacturer: Factory } as const;

/** Full triage result. Every value shown comes from the ReportResponse. */
export function IncidentResult({ result }: { result: ReportResponse }) {
  const { t, number, percent } = useI18n();
  const level = (result.escalation_level ?? "none") as EscalationLevel;
  const blocked = level === "blocking";
  const tone = categoryTone(result.incident_category);
  const provenance = result.device_class_source ?? "none";

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.36, ease: [0.2, 0, 0, 1] }}
      className="space-y-5"
    >
      {/* The answer to the screen's question, first and largest. */}
      <section aria-labelledby="result-summary" className="rounded-lg border border-line bg-surface px-5 py-4">
        <div className="flex flex-wrap items-center gap-2">
          <CategoryBadge category={result.incident_category} />
          <Badge tone={blocked ? "escalation" : result.reportable ? (tone === "critical" ? "critical" : "serious") : "ok"}>
            {blocked ? t.triage.pending : result.reportable ? t.triage.reportable : t.triage.notReportable}
          </Badge>
          <span className="ml-auto font-mono text-caption text-ink-subtle" translate="no">
            {t.triage.incident} {result.incident_id}
          </span>
        </div>
        <h2 id="result-summary" className="mt-3 text-title-sm font-semibold text-ink">
          {t.triage.deadlineTitle}
        </h2>
        <div className="mt-3">
          {blocked ? (
            <p className="text-body text-ink-muted">{t.triage.withheld}</p>
          ) : result.reportable && result.deadline_days ? (
            <DeadlineRing deadlineDays={result.deadline_days} tone={tone === "critical" ? "critical" : "serious"} />
          ) : (
            <p className="text-body text-ink-muted">{t.triage.noDeadline}</p>
          )}
        </div>
        {!blocked && result.report_to && result.report_to.length > 0 && (
          <div className="mt-4">
            <h3 className="text-small font-semibold text-ink-muted">{t.triage.recipientsTitle}</h3>
            <ul className="mt-1.5 flex flex-wrap gap-2">
              {result.report_to.map((r) => {
                const Icon = RECIPIENT_ICON[r as keyof typeof RECIPIENT_ICON] ?? Building2;
                return (
                  <li key={r}>
                    <Badge tone="neutral">
                      <Icon aria-hidden="true" />
                      {(t.recipients as Record<string, string>)[r] ?? r}
                    </Badge>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </section>

      <EscalationNotice level={level} reason={result.escalation_reason} />

      <div className="grid gap-5 lg:grid-cols-2">
        <Panel title={t.triage.deviceTitle} headingLevel={3}>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-body">
            <dt className="text-ink-muted">{t.triage.deviceClass}</dt>
            <dd className="flex flex-wrap items-center gap-2">
              <span className="font-semibold">{result.device_class ?? t.common.none}</span>
              <Badge tone="info">
                <Cpu aria-hidden="true" />
                {(t.provenance as Record<string, string>)[provenance]}
              </Badge>
            </dd>
            <dt className="text-ink-muted">{t.triage.ruleApplied}</dt>
            <dd className="min-w-0 break-words text-small">{result.classification_rule ?? t.common.none}</dd>
          </dl>
        </Panel>

        <Panel title={t.triage.reasoningTitle} headingLevel={3}>
          <p className="text-body">{result.severity_reasoning ?? t.common.none}</p>
          {result.severity_confidence != null && (
            <p className="mt-3 text-small text-ink-muted">
              <Tooltip content={t.triage.confidenceHelp}>
                <span tabIndex={0} className="underline decoration-dotted underline-offset-2">
                  {t.triage.confidence}
                </span>
              </Tooltip>
              : <span className="tabular">{percent(result.severity_confidence, 0)}</span>
              {" · "}
              {t.triage.processingTime}: <span className="tabular">{number(result.processing_time_ms / 1000, { maximumFractionDigits: 1 })} s</span>
            </p>
          )}
        </Panel>
      </div>

      {result.rag_sources.length > 0 && (
        <Panel title={t.triage.sourcesTitle} headingLevel={3}>
          <ul className="divide-y divide-line">
            {result.rag_sources.map((s) => (
              <li key={s.chunk_id ?? `${s.document}-${s.section}`} className="py-2.5 first:pt-0 last:pb-0">
                <p className="flex items-center gap-2 text-small font-semibold text-ink">
                  <BookOpen className="size-4 shrink-0 text-ink-muted" aria-hidden="true" />
                  {s.document} · {s.section}
                </p>
                <p className="mt-1 line-clamp-3 text-small text-ink-muted">{s.text}</p>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      {result.draft_notification && (
        <Panel title={t.triage.draftTitle} headingLevel={3}>
          <DraftEditor draft={result.draft_notification} incidentId={result.incident_id} />
        </Panel>
      )}
    </motion.div>
  );
}
