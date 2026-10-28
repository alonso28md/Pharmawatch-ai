import { RotateCcw } from "lucide-react";
import { type FormEvent, useRef, useState } from "react";
import { type ActivityState, useActivity } from "@/app/activityContext";
import { useI18n } from "@/app/preferencesContext";
import { ErrorNotice } from "@/components/ErrorNotice";
import { IncidentResult } from "@/components/incident/IncidentResult";
import { StepProgress } from "@/components/incident/StepProgress";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { Panel } from "@/components/ui/primitives";
import type { ReportResponse } from "@/lib/api/client";
import { type ReportRequest, type StepEvent, streamReport } from "@/lib/api/stream";

const MIN = 20;
const MAX = 4000;
const CLASSES = ["I", "IIa", "IIb", "III"] as const;

/** Which background state a real result corresponds to (DESIGN.md §7). */
function activityFor(result: ReportResponse): ActivityState {
  if (result.escalation_level === "blocking") return "escalated";
  return result.reportable ? "serious" : "ok";
}

export function TriagePage() {
  const { t } = useI18n();
  const { report } = useActivity();
  const [description, setDescription] = useState("");
  const [deviceName, setDeviceName] = useState("");
  const [deviceClass, setDeviceClass] = useState("");
  const [touched, setTouched] = useState(false);
  const [steps, setSteps] = useState<StepEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<ReportResponse | null>(null);
  const [error, setError] = useState<unknown>(null);
  const abortRef = useRef<AbortController | null>(null);
  const descriptionRef = useRef<HTMLTextAreaElement>(null);

  const length = description.trim().length;
  const validation = length < MIN ? t.triage.tooShort : description.length > MAX ? t.triage.tooLong : null;

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    setTouched(true);
    if (validation) {
      descriptionRef.current?.focus();
      return;
    }
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setSteps([]);
    setResult(null);
    setError(null);
    setRunning(true);
    report("processing");
    try {
      const response = await streamReport(
        {
          description,
          device_name: deviceName.trim() || null,
          device_class: (deviceClass || null) as ReportRequest["device_class"],
        },
        (step) => setSteps((current) => [...current, step]),
        controller.signal,
      );
      setResult(response);
      report(activityFor(response));
    } catch (e) {
      if (controller.signal.aborted) return;
      setError(e);
      report("error");
    } finally {
      if (abortRef.current === controller) setRunning(false);
    }
  }

  function reset() {
    abortRef.current?.abort();
    setDescription("");
    setDeviceName("");
    setDeviceClass("");
    setTouched(false);
    setSteps([]);
    setResult(null);
    setError(null);
    setRunning(false);
    report("idle");
    descriptionRef.current?.focus();
  }

  return (
    <>
      <PageHeader
        title={t.pages.triage.title}
        subtitle={t.pages.triage.subtitle}
        actions={
          (result !== null || error !== null) && (
            <Button variant="secondary" onClick={reset}>
              <RotateCcw aria-hidden="true" />
              {t.triage.reset}
            </Button>
          )
        }
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <div className="space-y-6">
          <Panel title={t.triage.formTitle}>
            <form noValidate onSubmit={submit} className="space-y-4">
              <Field
                label={t.triage.descriptionLabel}
                help={t.triage.descriptionHelp}
                error={touched ? validation : null}
                counter={`${description.length} / ${MAX}`}
              >
                {({ id, describedBy, invalid }) => (
                  <Textarea
                    ref={descriptionRef}
                    id={id}
                    name="description"
                    autoComplete="off"
                    spellCheck
                    rows={7}
                    maxLength={MAX}
                    placeholder={t.triage.placeholder}
                    value={description}
                    aria-invalid={invalid}
                    aria-describedby={describedBy}
                    onChange={(e) => setDescription(e.target.value)}
                    onBlur={() => setTouched(true)}
                  />
                )}
              </Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label={t.triage.deviceNameLabel}>
                  {({ id }) => (
                    <Input
                      id={id}
                      name="device_name"
                      autoComplete="off"
                      maxLength={200}
                      placeholder={t.triage.deviceNamePlaceholder}
                      value={deviceName}
                      onChange={(e) => setDeviceName(e.target.value)}
                    />
                  )}
                </Field>
                <Field label={t.triage.deviceClassLabel}>
                  {({ id }) => (
                    <Select id={id} name="device_class" value={deviceClass} onChange={(e) => setDeviceClass(e.target.value)}>
                      <option value="">{t.triage.deviceClassNone}</option>
                      {CLASSES.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
              </div>
              <Button type="submit" loading={running} loadingLabel={t.triage.submitting}>
                {t.triage.submit}
              </Button>
            </form>
          </Panel>

          {(running || steps.length > 0) && (
            <Panel title={t.triage.progressTitle} description={t.triage.progressHelp}>
              <StepProgress steps={steps} running={running} />
            </Panel>
          )}
        </div>

        <section aria-labelledby="triage-result" aria-live="polite" aria-busy={running}>
          <h2 id="triage-result" className="sr-only">
            {t.triage.resultTitle}
          </h2>
          {error ? <ErrorNotice error={error} onRetry={() => submit()} /> : null}
          {result && <IncidentResult result={result} />}
        </section>
      </div>
    </>
  );
}
