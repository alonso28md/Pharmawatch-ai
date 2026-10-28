import { AnimatePresence, motion } from "motion/react";
import { CircleCheck, LoaderCircle } from "lucide-react";
import { useI18n } from "@/app/preferencesContext";
import type { StepEvent } from "@/lib/api/stream";

/**
 * Real progress of the agent: one row per LangGraph node event received over SSE, in the
 * order they completed. While running, a final indeterminate row shows that the next step
 * is in progress - the list never shows steps that have not actually happened.
 */
export function StepProgress({ steps, running }: { steps: StepEvent[]; running: boolean }) {
  const { t } = useI18n();
  const label = (node: string) => (t.nodes as Record<string, string>)[node] ?? node;
  return (
    <div>
      <div
        role="progressbar"
        aria-label={t.triage.progressTitle}
        aria-busy={running}
        aria-valuetext={running ? t.triage.progressWaiting : undefined}
        className="relative mb-3 h-1 overflow-hidden rounded-full bg-surface-sunken"
      >
        {running && (
          <motion.span
            className="absolute inset-y-0 w-1/3 rounded-full bg-accent"
            initial={{ x: "-100%" }}
            animate={{ x: "300%" }}
            transition={{ repeat: Infinity, duration: 1.4, ease: "easeInOut" }}
          />
        )}
        {!running && steps.length > 0 && <span className="absolute inset-0 bg-accent" />}
      </div>
      <ol className="space-y-1.5" aria-live="polite">
        <AnimatePresence initial={false}>
          {steps.map((step) => (
            <motion.li
              key={`${step.index}-${step.node}`}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
              className="flex items-center gap-2 text-small text-ink"
            >
              <CircleCheck className="size-4 shrink-0 text-ok" aria-hidden="true" />
              <span className="tabular w-5 text-ink-subtle">{step.index}</span>
              {label(step.node)}
            </motion.li>
          ))}
        </AnimatePresence>
        {running && (
          <li className="flex items-center gap-2 text-small text-ink-muted">
            <LoaderCircle className="size-4 shrink-0 animate-spin motion-reduce:animate-none" aria-hidden="true" />
            <span className="w-5" />
            {t.triage.progressWaiting}
          </li>
        )}
      </ol>
    </div>
  );
}
