# Open questions

Decisions that need a vigilance specialist, a product decision or more measurement. Nothing on
this page has been resolved; items marked *proposed* have not been applied or measured.

## 1. Regulatory interpretation (`REGULATORY-REVIEW`)

These points are marked `REGULATORY-REVIEW` in the code or data because the indexed corpus does
not settle them.

| Where | Question |
|---|---|
| `src/agent/regulatory.py` — category triggers | What makes a deterioration "unanticipated" (10 days) rather than an anticipated one that falls under "other serious incident" (15 days)? The model decides and must flag doubt, which escalates. |
| `src/agent/regulatory.py` — non-serious incidents | Non-serious incidents may still feed Article 88 trend reporting. That is a manufacturer-side statistical process and is not determined per incident. |
| `src/agent/regulatory.py` — recipients | The `report_to` lists come verbatim from `data/classification_rules.json`. Who notifies whom — healthcare centre or manufacturer, under Article 87 and the Spanish AEMPS procedure — needs confirmation. |
| `data/classification_rules.json` — infusion pumps | Classified IIb under Rule 12 (potentially hazardous administration of medicinal products) based on an explanatory example in the corpus file, not on the literal Annex VIII text. |
| `data/classification_rules.json` — electrosurgical units | Classified IIb under Rule 9 (potentially hazardous energy exchange), same caveat. |

**Scope.** The system targets the reporting obligations for serious incidents with medical
devices under Regulation (EU) 2017/745 (mainly the manufacturer's obligations in Article 87),
with the Spanish AEMPS guidance as national context. It does not cover medicinal products
(drug pharmacovigilance) or in vitro diagnostic devices (Regulation (EU) 2017/746).

**Corpus.** MDCG guidance documents are not indexed. Note that MDCG 2020-7 is the *PMCF plan
template* and does not cover vigilance; the MDCG vigilance guidance is MDCG 2023-3 (Questions
and Answers on vigilance terms and concepts). Adding it would require checking its licence and
re-running the evaluation.

## 2. Dataset labels pending expert review

All 152 cases of `golden_dataset_v2.json` carry `label_source: draft-ai`. Six borderline cases
are flagged `needs_expert_review` and excluded from every metric:

| Case | Split | Open question |
|---|---|---|
| `v2_cls_083` | dev | v1 labelled this 15 days; whether anaphylaxis is an anticipated (documented) risk decides 10 vs 15. |
| `v2_cls_084` | test | v1 labelled this 15 days; corpus Art. 87(5) suggests 10 for an unanticipated serious deterioration. |
| `v2_cls_085` | test | Whether a superficial burn with minor treatment is a "serious deterioration" is a clinical judgement. |
| `v2_cls_086` | dev | Expected side-effect subject to trend reporting vs. reportable serious incident. |
| `v2_cls_087` | test | Two cases: public health threat (2 days) vs. other serious incident (15 days). |
| `v2_cls_088` | dev | Non-serious vs. temporary serious deterioration of health. |

Needed: a vigilance specialist reviews every label (starting with these six), and the
`label_source` field records who validated each case.

## 3. Thresholds

`config/eval_thresholds.json` holds **proposed** thresholds. They need to be agreed with the
intended users, in particular the trade-off between `over_escalation_rate` and
`unescalated_error_rate`.

## 4. Over-escalation (*proposed*, not applied)

In the stored v2 run, 37 of the 111 decidable classification runs (15 distinct cases) were
blocked. Counting the reasons attached to those blocked runs (a run can have several):

| Reason | Blocked runs |
|---|---|
| Doubt between two categories with different obligations | 27 |
| Model-reported confidence below 0.7 | 16 |
| Patient outcome unknown or not documented | 12 |
| Device could not be identified from the description | 5 |
| Contradictory severity signals (keyword cross-check) | 5 |

Candidate changes, each to be measured on `dev` before touching `test`:

1. **Keyword signal.** Make the auxiliary keyword cross-check less trigger-happy (e.g. treat an
   ICU mention as a signal only when it describes an admission; do not count a bare "dead"
   that may refer to the device rather than the patient). An offline simulation on the stored
   outputs reduced blocked runs from 37 to 32 with no missed escalation; it has not been
   implemented.
2. **Device name.** Ask the extraction step to return the device "as named" in the text instead
   of `null` when the type is clear but the brand is not.
3. **Unknown outcome for public health threats.** A public health threat is a population-level
   risk, so an unknown outcome for one patient may not need to block it. This touches the
   B-03 rule (unknown outcome always escalates) and needs a regulatory decision first.

Category doubt is the largest cause and is working as designed: two categories with different
deadlines should not be settled by the model alone.

## 5. Product and engineering

| Item | Status |
|---|---|
| Escalation reasons as stable codes | The backend returns `escalation_reason` as free English text. The web interface shows it as original server text in both languages. Needed: a list of reason codes in the API (e.g. `outcome_unknown`, `category_doubt`, `low_confidence`) so the interface can translate them. |
| Human review workflow | The review queue is read-only. Approve / correct / submit, with an audit trail and user identity, is not designed. |
| Reviewer ablation | The reviewer node is implemented and unit-tested but its effect is unmeasured. Run `python scripts/run_evaluation.py --dataset v2 --split test --categories classification --reviewer` (costs money) and compare with the stored baseline. |
| Abstention heuristic | The API's `answered_from_context` is simply "the answer cites at least one fragment"; the evaluation decides abstention with the judge model. They can disagree (e.g. an answer that abstains but cites a fragment). |
| Python version | `pyproject.toml` says `>=3.11`, but `requirements.lock` was resolved on 3.14 and some pins no longer support 3.11. Only 3.14 is tested. |
| Docker | The image (including the new web-interface build stage) has not been built in this environment. |
| Deployment | No hosted deployment exists. |
