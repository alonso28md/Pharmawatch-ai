import { Check, Copy, FileJson, FileText } from "lucide-react";
import { useState } from "react";
import { useI18n } from "@/app/preferencesContext";
import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/form";

const FIELDS = [
  "incident_date",
  "reporter_type",
  "device_identification",
  "event_description",
  "patient_outcome",
  "corrective_action",
] as const;
type DraftField = (typeof FIELDS)[number];
type Draft = Record<DraftField, string>;

function download(filename: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** Editable notification draft with copy and JSON / plain-text export. */
export function DraftEditor({ draft, incidentId }: { draft: Record<string, unknown>; incidentId: string }) {
  const { t } = useI18n();
  const [values, setValues] = useState<Draft>(
    () => Object.fromEntries(FIELDS.map((f) => [f, draft[f] == null ? "" : String(draft[f])])) as Draft,
  );
  const [copied, setCopied] = useState(false);
  const asText = () =>
    FIELDS.map((f) => `${t.triage.draftFields[f]}: ${values[f] || t.common.none}`).join("\n");

  return (
    <div className="space-y-4">
      <p className="text-small text-ink-muted">{t.triage.draftHelp}</p>
      <div className="grid gap-4 sm:grid-cols-2">
        {FIELDS.map((field) => {
          const multiline = field === "event_description" || field === "patient_outcome";
          return (
            <div key={field} className={multiline ? "sm:col-span-2" : undefined}>
              <Field label={t.triage.draftFields[field]}>
                {({ id }) =>
                  multiline ? (
                    <Textarea
                      id={id}
                      name={field}
                      autoComplete="off"
                      className="min-h-20"
                      value={values[field]}
                      onChange={(e) => setValues((v) => ({ ...v, [field]: e.target.value }))}
                    />
                  ) : (
                    <Input
                      id={id}
                      name={field}
                      autoComplete="off"
                      value={values[field]}
                      onChange={(e) => setValues((v) => ({ ...v, [field]: e.target.value }))}
                    />
                  )
                }
              </Field>
            </div>
          );
        })}
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="secondary"
          onClick={async () => {
            await navigator.clipboard.writeText(asText());
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1500);
          }}
        >
          {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
          {copied ? t.common.copied : t.triage.copyDraft}
        </Button>
        <Button size="sm" variant="secondary" onClick={() => download(`${incidentId}.json`, JSON.stringify(values, null, 2), "application/json")}>
          <FileJson aria-hidden="true" />
          {t.triage.exportJson}
        </Button>
        <Button size="sm" variant="secondary" onClick={() => download(`${incidentId}.txt`, asText(), "text/plain")}>
          <FileText aria-hidden="true" />
          {t.triage.exportText}
        </Button>
      </div>
      <span role="status" className="sr-only">
        {copied ? t.common.copied : ""}
      </span>
    </div>
  );
}
