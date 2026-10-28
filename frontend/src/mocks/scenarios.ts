import type { AskResponse, ReportResponse } from "@/lib/api/client";

/**
 * Mock-mode scenarios. Regulatory text is copied verbatim from data/regulations
 * (mdr_vigilance_articles.txt); triage results mirror real backend outputs observed in
 * the phase-6 live checks. Steps are the graph's real node names for each path.
 */
const ART87 = "Article 87 — Reporting of serious incidents and field safety corrective actions";
const VIG = "MDR 2017/745 (Articles 87-92, Vigilance)";

export const art87Chunks = {
  c3: {
    chunk_id: `mdr_vigilance_articles.txt::${ART87}::3`,
    document: VIG,
    section: ART87,
    text:
      "The reports referred to in the first subparagraph shall be submitted through the\nelectronic system referred to in Article 92.\n\n2. As a general rule, the period for the reporting referred to in paragraph 1\nshall take account of the severity of the serious incident.\n\n3. Manufacturers shall report any serious incident as referred to in point (a) of\nparagraph 1 immediately after they have established the causal relationship\nbetween that incident and their device or that such causal relationship is\nreasonably possible and not later than 15 days after they become aware of the\nincident.",
  },
  c4: {
    chunk_id: `mdr_vigilance_articles.txt::${ART87}::4`,
    document: VIG,
    section: ART87,
    text:
      "4. Notwithstanding paragraph 3, in the event of a serious public health threat\nthe report referred to in paragraph 1 shall be provided immediately, and not\nlater than 2 days after the manufacturer becomes aware of that threat.\n\n5. Notwithstanding paragraph 3, in the event of death or an unanticipated serious\ndeterioration in a person's state of health the report shall be provided\nimmediately after the manufacturer has established or as soon as it suspects a\ncausal relationship between the device and the serious incident but not later\nthan 10 days after the date on which the manufacturer becomes aware of the\nserious incident.\n\n6. Where necessary to ensure timely reporting, the manufacturer may submit an\ninitial report that is incomplete followed up by a complete report.",
  },
};

const ragSources = [
  { ...art87Chunks.c4, text: art87Chunks.c4.text.slice(0, 400), relevance_score: null },
  { ...art87Chunks.c3, text: art87Chunks.c3.text.slice(0, 400), relevance_score: null },
];

const PATH_DECIDED = ["extract_info", "classify_device", "assess_severity", "gate", "determine_reporting", "generate_report", "finalize"];
const PATH_BLOCKED = ["extract_info", "classify_device", "assess_severity", "gate", "escalate", "finalize"];

export interface TriageScenario {
  steps: string[];
  result: Omit<ReportResponse, "incident_id" | "processing_time_ms">;
}

export const triageScenarios: Record<"serious" | "death" | "nonSerious" | "unknown", TriageScenario> = {
  serious: {
    steps: PATH_DECIDED,
    result: {
      severity: "serious",
      severity_confidence: 0.93,
      severity_reasoning:
        "The over-infusion directly led to a major bleed requiring ICU admission, a serious deterioration of health that was not anticipated (MDR Art. 2(65)(b); Art. 87(5)).",
      incident_category: "unanticipated_serious_deterioration",
      reportable: true,
      report_to: ["competent_authority", "manufacturer"],
      deadline_days: 10,
      deadline_rule: "death_or_unanticipated_serious_deterioration",
      device_class: "IIb",
      device_class_source: "rule",
      classification_rule:
        "Rule 12 (potentially hazardous administration): Rule 12: active devices administering medicinal products are class IIa unless done in a potentially hazardous manner (class IIb).",
      escalated_to_human: false,
      escalation_level: "none",
      escalation_reason: null,
      rag_sources: ragSources,
      draft_notification: {
        incident_date: null,
        reporter_type: "healthcare_professional",
        device_identification: "Volumetric infusion pump (heparin)",
        event_description: "A software fault caused the pump to over-infuse heparin; the patient had a major bleed.",
        patient_outcome: "Major bleed; admitted to the ICU",
        corrective_action: "Pending investigation",
      },
    },
  },
  death: {
    steps: PATH_DECIDED,
    result: {
      severity: "serious",
      severity_confidence: 0.97,
      severity_reasoning:
        "The ventilator stopped without an alarm and the patient died, which meets MDR Art. 2(65)(a); Art. 87(5) applies.",
      incident_category: "death",
      reportable: true,
      report_to: ["competent_authority", "manufacturer"],
      deadline_days: 10,
      deadline_rule: "death_or_unanticipated_serious_deterioration",
      device_class: "IIb",
      device_class_source: "extracted",
      classification_rule: "Stated in the incident description",
      escalated_to_human: true,
      escalation_level: "advisory",
      escalation_reason:
        "Death or life-threatening outcome detected: flagged for immediate specialist review in addition to the automated determination.",
      rag_sources: ragSources,
      draft_notification: {
        incident_date: null,
        reporter_type: "healthcare_professional",
        device_identification: "ICU ventilator (class IIb)",
        event_description: "The ventilator stopped delivering breaths without triggering its alarm during overnight use.",
        patient_outcome: "Respiratory arrest; the patient died",
        corrective_action: "Pending investigation",
      },
    },
  },
  nonSerious: {
    steps: PATH_DECIDED,
    result: {
      severity: "non-serious",
      severity_confidence: 0.95,
      severity_reasoning:
        "A smudged batch number with all other label information correct could not plausibly lead to any Art. 2(65) outcome.",
      incident_category: "non_serious",
      reportable: false,
      report_to: [],
      deadline_days: null,
      deadline_rule: null,
      device_class: null,
      device_class_source: null,
      classification_rule: "No Annex VIII classification keyword matched the device name/type.",
      escalated_to_human: true,
      escalation_level: "advisory",
      escalation_reason:
        "The device's MDR class could not be determined (not stated and no Annex VIII rule matched); the reporting deadline does not depend on it, but the class needs manual review.",
      rag_sources: ragSources,
      draft_notification: null,
    },
  },
  unknown: {
    steps: PATH_BLOCKED,
    result: {
      severity: null,
      severity_confidence: 0.4,
      severity_reasoning: "The report does not say what happened to the patient.",
      incident_category: "unknown",
      reportable: null,
      report_to: null,
      deadline_days: null,
      deadline_rule: null,
      device_class: null,
      device_class_source: null,
      classification_rule: "No Annex VIII classification keyword matched the device name/type.",
      escalated_to_human: true,
      escalation_level: "blocking",
      escalation_reason:
        "The patient outcome is unknown or not documented; requesting more information instead of guessing. The incident category could not be determined. Severity assessment confidence is below 0.7; recommend review by a vigilance specialist.",
      rag_sources: ragSources,
      draft_notification: null,
    },
  },
};

/** Deterministic scenario choice from the description text (mock mode only). */
export function pickScenario(description: string): keyof typeof triageScenarios {
  const d = description.toLowerCase();
  if (/(unknown|unsure|not documented|desconoc|no consta|no se sabe|sin más detalles)/.test(d)) return "unknown";
  if (/(died|death|dead|falleci|muri)/.test(d)) return "death";
  if (/(no harm|no patient|not affected|sin daño|ningún paciente|no afect)/.test(d)) return "nonSerious";
  return "serious";
}

export function askAnswer(question: string): Omit<AskResponse, "processing_time_ms"> {
  const spanish = /[¿áéíóúñ]|\b(plazo|qué|cuál|cuántos|notificar)\b/i.test(question);
  const outOfScope = /(paracetamol|ibuprofen|dosis|dose|precio|price)/i.test(question);
  const context = [
    { label: "C1", ...art87Chunks.c4 },
    { label: "C2", ...art87Chunks.c3 },
  ];
  const sources = context.map((c) => ({ document: c.document, section: c.section, text: c.text.slice(0, 400), relevance_score: 0.79, chunk_id: c.chunk_id }));
  if (outOfScope) {
    return {
      answer: spanish
        ? "El contexto proporcionado no contiene información sobre esta cuestión, así que no puedo responderla a partir de él."
        : "The provided context does not contain information on this question, so I cannot answer it from it.",
      sources, retrieval_score: 0.6184, context, cited_labels: [], answered_from_context: false,
    };
  }
  return {
    answer: spanish
      ? "Según el artículo 87 del MDR, los plazos dependen del tipo de incidente grave:\n\n- Muerte o deterioro grave no anticipado: no más tarde de 10 días desde que el fabricante tiene conocimiento [C1].\n- Amenaza grave para la salud pública: no más tarde de 2 días [C1].\n- Cualquier otro incidente grave: no más tarde de 15 días [C2]."
      : "Under MDR Article 87, the deadline depends on the type of serious incident:\n\n- Death or unanticipated serious deterioration: no later than 10 days after the manufacturer becomes aware [C1].\n- Serious public health threat: no later than 2 days [C1].\n- Any other serious incident: no later than 15 days [C2].",
    sources, retrieval_score: 0.7818, context, cited_labels: ["C1", "C2"], answered_from_context: true,
  };
}
