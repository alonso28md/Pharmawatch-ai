/** Visual tone of an incident category (DESIGN.md §2 semantic roles). */
export function categoryTone(category: string | null | undefined) {
  if (category === "death" || category === "public_health_threat") return "critical" as const;
  if (category === "unanticipated_serious_deterioration" || category === "other_serious") return "serious" as const;
  if (category === "non_serious") return "ok" as const;
  return "neutral" as const;
}
