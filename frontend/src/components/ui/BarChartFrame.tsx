import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useI18n } from "@/app/preferencesContext";

export interface BarDatum {
  label: string;
  value: number;
}

/**
 * Single-series bar chart (one hue, faint horizontal grid, no legend) with the same data as
 * a table for screen readers and keyboard users (DESIGN.md §9: charts have a text twin).
 */
export function BarChartFrame({ data, title }: { data: BarDatum[]; title: string }) {
  const { t, number } = useI18n();
  if (data.length === 0) return <p className="text-small text-ink-muted">{t.operations.noData}</p>;
  return (
    <figure>
      <div className="h-48" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
            <CartesianGrid vertical={false} stroke="var(--pw-border)" />
            <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: "var(--pw-text-muted)", fontSize: 12 }} />
            <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fill: "var(--pw-text-muted)", fontSize: 12 }} />
            <Tooltip
              cursor={{ fill: "var(--pw-surface-sunken)" }}
              contentStyle={{ background: "var(--pw-surface-raised)", border: "1px solid var(--pw-border)", borderRadius: 6, color: "var(--pw-text)" }}
            />
            <Bar dataKey="value" name={t.operations.count} fill="var(--pw-accent)" radius={[3, 3, 0, 0]} maxBarSize={48} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <details className="mt-2 text-small text-ink-muted">
        <summary className="cursor-pointer select-none">{t.operations.chartTable}</summary>
        <table className="mt-2 w-full text-left">
          <caption className="sr-only">{title}</caption>
          <thead>
            <tr className="border-b border-line">
              <th scope="col" className="py-1.5 font-medium">{title}</th>
              <th scope="col" className="py-1.5 text-right font-medium">{t.operations.count}</th>
            </tr>
          </thead>
          <tbody>
            {data.map((d) => (
              <tr key={d.label} className="border-b border-line last:border-0">
                <td className="py-1.5 text-ink">{d.label}</td>
                <td className="tabular py-1.5 text-right text-ink">{number(d.value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
