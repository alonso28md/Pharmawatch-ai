import { motion } from "motion/react";
import { CalendarClock } from "lucide-react";
import { useId, useState } from "react";
import { useI18n } from "@/app/preferencesContext";
import { Field, Input } from "@/components/ui/form";
import { DAY_MS, daysRemaining, toInputDate } from "@/lib/deadline";
import { cn } from "@/lib/utils";

/**
 * Countdown ring for the reporting deadline. The clock starts at the date of awareness,
 * which the user provides (default: today) - the system never invents it.
 */
export function DeadlineRing({ deadlineDays, tone }: { deadlineDays: number; tone: "serious" | "critical" }) {
  const { t, dateTime } = useI18n();
  const [today] = useState(() => toInputDate(new Date()));
  const [awareness, setAwareness] = useState(today);
  const titleId = useId();
  const remaining = daysRemaining(awareness, deadlineDays);
  const fraction = Math.max(0, Math.min(1, remaining / deadlineDays));
  const due = new Date(new Date(`${awareness}T00:00:00`).getTime() + deadlineDays * DAY_MS);
  const radius = 34;
  const circumference = 2 * Math.PI * radius;
  const status =
    remaining < 0 ? t.triage.overdue : remaining === 0 ? t.triage.dueToday : `${remaining} ${t.triage.daysLeft}`;

  return (
    <div className="flex flex-wrap items-center gap-5">
      <figure aria-labelledby={titleId} className="relative size-[88px] shrink-0">
        <svg viewBox="0 0 80 80" className="size-full -rotate-90" aria-hidden="true">
          <circle cx="40" cy="40" r={radius} fill="none" strokeWidth="6" className="stroke-surface-sunken" />
          <motion.circle
            cx="40"
            cy="40"
            r={radius}
            fill="none"
            strokeWidth="6"
            strokeLinecap="round"
            className={cn(tone === "critical" ? "stroke-critical" : "stroke-serious")}
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: circumference * (1 - fraction) }}
            transition={{ duration: 0.36, ease: [0.2, 0, 0, 1] }}
          />
        </svg>
        <figcaption className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="tabular text-title font-semibold text-ink">{deadlineDays}</span>
          <span className="text-caption text-ink-muted">{t.common.days}</span>
        </figcaption>
      </figure>
      <div className="min-w-0 flex-1 space-y-2">
        <p id={titleId} className="flex items-center gap-2 font-semibold text-ink" aria-live="polite">
          <CalendarClock className="size-4 text-ink-muted" aria-hidden="true" />
          {status}
          <span className="font-normal text-ink-muted">
            · {t.triage.dueOn} {dateTime(due).split(",")[0]}
          </span>
        </p>
        <div className="max-w-[220px]">
          <Field label={t.triage.awarenessLabel} help={t.triage.awarenessHelp}>
            {({ id, describedBy }) => (
              <Input
                id={id}
                type="date"
                value={awareness}
                max={today}
                aria-describedby={describedBy}
                onChange={(event) => event.target.value && setAwareness(event.target.value)}
              />
            )}
          </Field>
        </div>
      </div>
    </div>
  );
}
