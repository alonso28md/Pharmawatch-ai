import { useMutation } from "@tanstack/react-query";
import { motion } from "motion/react";
import { BookOpen, SearchX, Send } from "lucide-react";
import { type FormEvent, Fragment, useRef, useState } from "react";
import { useActivity } from "@/app/activityContext";
import { useI18n } from "@/app/preferencesContext";
import { ErrorNotice } from "@/components/ErrorNotice";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Field, Select, Textarea } from "@/components/ui/form";
import { Badge, Tooltip } from "@/components/ui/primitives";
import { Sheet } from "@/components/ui/sheet";
import { type AskResponse, api, call, type Schemas } from "@/lib/api/client";
import { unwrapLines } from "@/lib/utils";

type ContextChunk = Schemas["ContextChunk"];
interface Exchange {
  id: number;
  question: string;
  response: AskResponse;
}

const CITATION = /\[(C\d+(?:\s*[,;]\s*C\d+)*)\]/g;

/** Render an answer with every [Cn] citation as a button that opens the cited fragment. */
function CitedText({ text, onCite, context }: { text: string; onCite: (c: ContextChunk) => void; context: ContextChunk[] }) {
  const { t } = useI18n();
  const parts: React.ReactNode[] = [];
  let last = 0;
  for (const match of text.matchAll(CITATION)) {
    parts.push(text.slice(last, match.index));
    const labels = match[1]!.split(/\s*[,;]\s*/);
    parts.push(
      <span key={match.index} className="whitespace-nowrap">
        {labels.map((label) => {
          const chunk = context.find((c) => c.label === label);
          return chunk ? (
            <button
              key={label}
              type="button"
              onClick={() => onCite(chunk)}
              aria-label={`${t.ask.openCitation} ${label}: ${chunk.document}, ${chunk.section}`}
              className="mx-0.5 inline-flex h-6 items-center rounded-sm border border-info-line bg-info-bg px-1.5 align-baseline font-mono text-caption text-info hover:border-info"
            >
              {label}
            </button>
          ) : (
            <span key={label} className="font-mono text-caption text-ink-subtle">[{label}]</span>
          );
        })}
      </span>,
    );
    last = (match.index ?? 0) + match[0].length;
  }
  parts.push(text.slice(last));
  return (
    <div className="whitespace-pre-wrap text-body leading-[24px] text-ink">
      {parts.map((p, i) => (
        <Fragment key={i}>{p}</Fragment>
      ))}
    </div>
  );
}

function ExchangeView({ exchange, onCite }: { exchange: Exchange; onCite: (c: ContextChunk) => void }) {
  const { t, number } = useI18n();
  const { response } = exchange;
  const cited = response.context.filter((c) => response.cited_labels.includes(c.label));
  const notCited = response.context.filter((c) => !response.cited_labels.includes(c.label));
  return (
    <motion.article
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="rounded-lg border border-line bg-surface"
    >
      <header className="border-b border-line px-5 py-3">
        <p className="text-caption font-semibold text-ink-muted">{t.ask.question}</p>
        <p className="mt-0.5 text-body text-ink">{exchange.question}</p>
      </header>
      <div className="space-y-4 px-5 py-4">
        {response.answered_from_context ? (
          <CitedText text={response.answer} context={response.context} onCite={onCite} />
        ) : (
          <div className="rounded-md border border-info-line bg-info-bg px-4 py-3 text-info">
            <p className="flex items-center gap-2 font-semibold">
              <SearchX className="size-4" aria-hidden="true" />
              {t.ask.abstainTitle}
            </p>
            <p className="mt-1 text-small">{t.ask.abstainBody}</p>
            <p className="mt-3 whitespace-pre-wrap text-small text-ink">{response.answer}</p>
          </div>
        )}

        {cited.length > 0 && (
          <div>
            <h3 className="text-small font-semibold text-ink-muted">{t.ask.citationsTitle}</h3>
            <ul className="mt-2 flex flex-wrap gap-2">
              {cited.map((c) => (
                <li key={c.label}>
                  <button
                    type="button"
                    onClick={() => onCite(c)}
                    className="inline-flex min-h-8 items-center gap-2 rounded-md border border-line px-2.5 py-1 text-left text-small text-ink hover:bg-surface-sunken"
                  >
                    <span className="font-mono text-caption text-info">{c.label}</span>
                    <span className="min-w-0">{c.document} · {c.section}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {notCited.length > 0 && (
          <details className="text-small text-ink-muted">
            <summary className="cursor-pointer select-none">
              {t.ask.retrievedTitle} ({notCited.length})
            </summary>
            <ul className="mt-2 space-y-1">
              {notCited.map((c) => (
                <li key={c.label}>
                  <button type="button" onClick={() => onCite(c)} className="text-left underline-offset-2 hover:underline">
                    <span className="font-mono text-caption">{c.label}</span> {c.document} · {c.section}
                  </button>
                </li>
              ))}
            </ul>
          </details>
        )}
        <p className="text-caption text-ink-subtle">
          <Tooltip content={t.ask.retrievalScoreHelp}>
            <span tabIndex={0} className="underline decoration-dotted underline-offset-2">
              {t.ask.retrievalScore}
            </span>
          </Tooltip>
          : <span className="tabular">{number(response.retrieval_score, { maximumFractionDigits: 2 })}</span>
          {" · "}
          <span className="tabular">{number(response.processing_time_ms / 1000, { maximumFractionDigits: 1 })} s</span>
        </p>
      </div>
    </motion.article>
  );
}

export function AskPage() {
  const { t } = useI18n();
  const { report } = useActivity();
  const [question, setQuestion] = useState("");
  const [language, setLanguage] = useState<"" | "es" | "en">("");
  const [touched, setTouched] = useState(false);
  const [history, setHistory] = useState<Exchange[]>([]);
  const [open, setOpen] = useState<ContextChunk | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const nextId = useRef(1);

  const mutation = useMutation({
    mutationFn: (q: string) => call(() => api.POST("/ask", { body: { question: q, language: language || null } })),
    onMutate: () => report("processing"),
    onSuccess: (response, q) => {
      setHistory((h) => [{ id: nextId.current++, question: q, response }, ...h]);
      setQuestion("");
      setTouched(false);
      report("ok");
    },
    onError: () => report("error"),
  });

  const invalid = question.trim().length < 10;
  function submit(event: FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (invalid) {
      inputRef.current?.focus();
      return;
    }
    mutation.mutate(question.trim());
  }

  return (
    <>
      <PageHeader title={t.pages.ask.title} subtitle={t.pages.ask.subtitle} />
      <form noValidate onSubmit={submit} className="rounded-lg border border-line bg-surface px-5 py-4">
        <div className="grid gap-4 md:grid-cols-[1fr_200px]">
          <Field label={t.ask.formLabel} error={touched && invalid ? t.ask.tooShort : null}>
            {({ id, describedBy, invalid: isInvalid }) => (
              <Textarea
                ref={inputRef}
                id={id}
                name="question"
                autoComplete="off"
                rows={3}
                className="min-h-24"
                maxLength={4000}
                placeholder={t.ask.placeholder}
                value={question}
                aria-invalid={isInvalid}
                aria-describedby={describedBy}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit(e);
                }}
              />
            )}
          </Field>
          <Field label={t.ask.languageLabel}>
            {({ id }) => (
              <Select id={id} value={language} onChange={(e) => setLanguage(e.target.value as "" | "es" | "en")}>
                <option value="">{t.ask.languageAuto}</option>
                <option value="es">Español</option>
                <option value="en">English</option>
              </Select>
            )}
          </Field>
        </div>
        <Button type="submit" className="mt-4" loading={mutation.isPending} loadingLabel={t.ask.sending}>
          <Send aria-hidden="true" />
          {t.ask.send}
        </Button>
      </form>

      <section aria-label={t.ask.answer} aria-live="polite" aria-busy={mutation.isPending} className="mt-6 space-y-4">
        {mutation.isError && <ErrorNotice error={mutation.error} onRetry={() => mutation.mutate(question.trim())} />}
        {history.length === 0 && !mutation.isPending && !mutation.isError && (
          <div className="rounded-lg border border-dashed border-line px-5 py-8 text-center">
            <BookOpen className="mx-auto size-5 text-ink-subtle" aria-hidden="true" />
            <p className="mt-2 font-semibold text-ink">{t.ask.emptyTitle}</p>
            <p className="mt-1 text-small text-ink-muted">{t.ask.emptyBody}</p>
          </div>
        )}
        {history.map((exchange) => (
          <ExchangeView key={exchange.id} exchange={exchange} onCite={setOpen} />
        ))}
      </section>

      <Sheet
        open={open !== null}
        onOpenChange={(o) => !o && setOpen(null)}
        title={open ? `${t.ask.panelTitle} ${open.label}` : t.ask.panelTitle}
        description={open ? `${open.document} · ${open.section}` : undefined}
        closeLabel={t.common.close}
      >
        {open && (
          <>
            <Badge tone="info" className="font-mono">
              {open.chunk_id}
            </Badge>
            <mark className="mt-4 block rounded-md border-l-4 border-l-accent bg-info-bg px-4 py-3 text-body leading-[24px] whitespace-pre-wrap text-ink">
              {unwrapLines(open.text)}
            </mark>
          </>
        )}
      </Sheet>
    </>
  );
}
