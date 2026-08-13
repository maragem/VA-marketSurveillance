**Table 1.** Evaluation of the four configurations on the gold benchmark (52 campaigns, 97 must-find provisions, 7 compliant controls; three runs per campaign). Configurations C (holdout) and D are evaluated on the 15 held-out campaigns (2 controls, 26 must-find provisions) excluded from calibration-rule distillation; D is therefore compared against the C (holdout) row, not the full set. Arrows mark the desirable direction. Provision recall counts must-find provisions cited at any severity; unexpected findings are actionable (≥ medium) citations outside the must-find and defensible-extra sets; stability is the mean pairwise Jaccard of finding sets across the three runs; invalid citations are those the validation layer removes (unknown identifiers or cross-regulation citations), zero by construction in A, C and D.

| Configuration | n | Provision recall ↑ | Unexpected findings ↓ (per case) | Control FP ↓ | Risk calibration ↑ | Stability ↑ | Invalid citations ↓ | Latency (s) |
|---|---|---|---|---|---|---|---|---|
| A — retrieval only (no LLM) | 52 | 0.515 | 303 (5.83) | 7/7 | 34/52 | 1.000 | 0 | <1 |
| B — agentic, no citation validation | 52 | 1.000 | 154 (2.96) | 1/7 | 51/52 | 0.756 | 1 | 58.6 |
| C — agentic, deployed default | 52 | 0.979 | 162 (3.12) | 1/7 | 51/52 | 0.745 | 0 | 54.7 |
| C — deployed default (holdout) | 15 | 1.000 | 44 (2.93) | 0/2 | 15/15 | 0.745 | 0 | 58.6 |
| D — deployed default + calibration (holdout) | 15 | 1.000 | 5 (0.33) | 0/2 | 15/15 | 0.833 | 0 | 52.5 |

Provenance:

- **A — retrieval only (no LLM)** — job `A-20260808-114736`, engine `heuristic`, model `n/a (no LLM)`, case set `bb48530e65e048b9`
- **B — agentic, no citation validation** — job `B-20260808-114752`, engine `agentic-unvalidated`, model `eu.anthropic.claude-opus-4-8`, case set `bb48530e65e048b9`
- **C — agentic, deployed default** — job `C-full-20260813-071439`, engine `agentic`, model `eu.anthropic.claude-opus-4-8`, case set `bb48530e65e048b9`
- **C — deployed default (holdout)** — job `C-holdout-20260813-083740`, engine `agentic`, model `eu.anthropic.claude-opus-4-8`, case set `54ff841181b4621b`
- **D — deployed default + calibration (holdout)** — job `D-20260813-091230`, engine `agentic`, model `eu.anthropic.claude-opus-4-8`, case set `54ff841181b4621b`
