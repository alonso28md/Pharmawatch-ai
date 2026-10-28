import { Link } from "react-router-dom";
import { useI18n } from "@/app/preferencesContext";
import type { IncidentSummary } from "@/lib/api/queries";
import { CategoryBadge, EscalationBadge, type EscalationLevel } from "./status";

/** Incidents table: rules not stripes, tabular numbers, dash for missing values. */
export function IncidentTable({ items, caption }: { items: IncidentSummary[]; caption: string }) {
  const { t, dateTime } = useI18n();
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-body">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-line text-small text-ink-muted">
            <th scope="col" className="py-2 pr-4 font-medium">{t.review.columns.incident}</th>
            <th scope="col" className="py-2 pr-4 font-medium">{t.review.columns.date}</th>
            <th scope="col" className="py-2 pr-4 font-medium">{t.review.columns.category}</th>
            <th scope="col" className="py-2 pr-4 font-medium">{t.review.columns.escalation}</th>
            <th scope="col" className="py-2 text-right font-medium">{t.review.columns.deadline}</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.incident_id} className="border-b border-line last:border-0">
              <td className="py-2.5 pr-4">
                <Link
                  to={`/review/${item.incident_id}`}
                  className="font-mono text-small whitespace-nowrap text-accent underline-offset-2 hover:underline"
                  translate="no"
                >
                  {item.incident_id}
                </Link>
              </td>
              <td className="tabular py-2.5 pr-4 text-small whitespace-nowrap text-ink-muted">{dateTime(item.created_at)}</td>
              <td className="py-2.5 pr-4">
                <CategoryBadge category={item.incident_category} />
              </td>
              <td className="py-2.5 pr-4">
                {item.escalation_level === "none" ? (
                  <span className="text-ink-subtle">{t.common.none}</span>
                ) : (
                  <EscalationBadge level={item.escalation_level as EscalationLevel} />
                )}
              </td>
              <td className="tabular py-2.5 text-right whitespace-nowrap">
                {item.deadline_days != null ? `${item.deadline_days} ${t.common.days}` : <span className="text-ink-subtle">{t.common.none}</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
