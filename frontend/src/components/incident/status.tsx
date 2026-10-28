import { CircleCheck, Hand, Info, OctagonAlert, TriangleAlert } from "lucide-react";
import { useI18n } from "@/app/preferencesContext";
import { Badge } from "@/components/ui/primitives";
import { categoryTone } from "@/lib/incident";
import { cn } from "@/lib/utils";

export type Category =
  | "death"
  | "unanticipated_serious_deterioration"
  | "public_health_threat"
  | "other_serious"
  | "non_serious"
  | "unknown";

const TONE_ICON = { critical: OctagonAlert, serious: TriangleAlert, ok: CircleCheck, neutral: Info } as const;

/** Category with icon and text (colour is never the only carrier of meaning). */
export function CategoryBadge({ category }: { category: string | null | undefined }) {
  const { t } = useI18n();
  const tone = categoryTone(category);
  const Icon = TONE_ICON[tone];
  const label = t.category[(category ?? "unknown") as Category] ?? t.category.unknown;
  return (
    <Badge tone={tone}>
      <Icon aria-hidden="true" />
      {label}
    </Badge>
  );
}

export type EscalationLevel = "none" | "advisory" | "blocking";

export function EscalationBadge({ level }: { level: EscalationLevel }) {
  const { t } = useI18n();
  if (level === "none") return null;
  return level === "blocking" ? (
    <Badge tone="escalation">
      <Hand aria-hidden="true" />
      {t.triage.blockingTitle}
    </Badge>
  ) : (
    <Badge tone="escalation-outline">
      <Info aria-hidden="true" />
      {t.triage.advisoryTitle}
    </Badge>
  );
}

/**
 * Blocking: filled tint, left bar and a hand icon. Advisory: dashed outline and an info
 * icon. Distinguishable without colour (DESIGN.md §2).
 */
export function EscalationNotice({ level, reason }: { level: EscalationLevel; reason: string | null | undefined }) {
  const { t } = useI18n();
  if (level === "none") return null;
  const blocking = level === "blocking";
  const reasons = (reason ?? "").split(/(?<=\.)\s+(?=[A-Z])/).filter(Boolean);
  return (
    <section
      aria-labelledby="escalation-title"
      className={cn(
        "rounded-lg px-4 py-3 text-escalation",
        blocking
          ? "border border-escalation-line border-l-4 border-l-escalation bg-escalation-bg"
          : "border border-dashed border-escalation-line bg-transparent",
      )}
    >
      <div className="flex items-start gap-3">
        {blocking ? <Hand className="mt-0.5 size-5 shrink-0" aria-hidden="true" /> : <Info className="mt-0.5 size-5 shrink-0" aria-hidden="true" />}
        <div className="min-w-0">
          <h3 id="escalation-title" className="font-semibold">
            {blocking ? t.triage.blockingTitle : t.triage.advisoryTitle}
          </h3>
          <p className="mt-0.5 text-small">{blocking ? t.triage.blockingBody : t.triage.advisoryBody}</p>
          {reasons.length > 0 && (
            <>
              <p className="mt-2 text-small font-semibold">{t.triage.reasons}</p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-small text-ink">
                {reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
