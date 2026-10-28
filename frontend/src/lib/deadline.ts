/** Deadline arithmetic (dates are local calendar days). */
export const DAY_MS = 86_400_000;

export function toInputDate(date: Date): string {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

/** Whole days remaining from today until awareness + deadline (negative when overdue). */
export function daysRemaining(awareness: string, deadlineDays: number, today = new Date()): number {
  const start = new Date(`${awareness}T00:00:00`);
  const due = new Date(start.getTime() + deadlineDays * DAY_MS);
  const midnight = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((due.getTime() - midnight.getTime()) / DAY_MS);
}
