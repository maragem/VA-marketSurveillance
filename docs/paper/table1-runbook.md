# Table 1 runbook — evaluation grid for the MCC paper

This is a self-contained guide for running the four evaluation configurations
(A–D) of the Marketing Compliance Checker benchmark and filling in Table 1 of
the manuscript. Follow it in order; each step states what it produces and
where the numbers land. Estimated total effort: one focused day, plus review
time.

## 0. Ground rules (read first)

1. **The gold labels are frozen.** `bench/cases.jsonl` at commit `5ad62f0`
   is the dataset of record: **52 cases** (19 tier‑1, 17 tier‑2, 16 tier‑3),
   **7 compliant controls**, **97 must-find provisions**. Do not edit labels
   while experiments are running. If a label error is discovered mid-run,
   finish the runs, fix the label in a separate commit, and re-score the
   stored raw outputs with `--rescore` (§7) — never mix labels between
   configurations.
2. **One model for the whole grid.** Every configuration that uses an LLM
   (B, C, D) must run on the same model id. Check what the target instance
   reports at `GET /api/health` before each run and write it down. As of
   August 2026 the project standard is `eu.anthropic.claude-opus-4-8`
   (Bedrock EU cross-region profile). If the team switches to
   `eu.anthropic.claude-opus-5`, the entire grid must be re-run on it —
   partial upgrades make the rows incomparable.
3. **Holdout discipline.** `bench/holdout.json` names 15 cases that must
   never influence calibration-rule writing. The rule proposer in the app
   excludes them automatically, but humans can leak too: when reviewing
   deviations to approve rules, only look at scorecard entries for the 37
   visible cases. Configuration D is *reported on the 15 held-out cases
   only*. Never move a case in or out of the holdout set.
4. **Never point the harness at the production deployment.** Benchmark runs
   are persisted by the target instance like ordinary analyses and would
   pollute the production dashboard, and configuration B requires an
   experiment flag that must never be set in production. Run everything
   against a local instance with a throwaway `DATA_DIR` (recipe in §2).

## 1. What the grid measures

Rows (configurations):

| Config | Engine | What it isolates |
|---|---|---|
| **A** | Retrieval-only (no LLM credentials) | What GraphRAG retrieval alone contributes |
| **B** | Full agentic, citation validation **disabled** | What the validation layer contributes (measured via the *invalid citations* metric) |
| **C** | Full agentic, default pipeline | The deployed system |
| **D** | C + approved calibration rules | What benchmark-distilled calibration adds, on unseen (held-out) cases |

Columns (metrics), all computed by `bench/run.py` and printed in the
scorecard:

| Scorecard field | Meaning |
|---|---|
| gold-provision recall | share of the 97 must-find provisions actually cited (found at any severity) |
| missed triage routings | gold-relevant regulations the triage never routed |
| unexpected actionable findings | ≥ medium findings outside `provisions ∪ acceptable_extra`, per case |
| false positives on controls | compliant controls flagged ≥ medium (out of 7) |
| risk calibration | cases where `overall_risk ≥ gold min_risk` |
| stability | mean pairwise Jaccard of finding sets across repeated runs (needs `--runs 3`) |
| invalid citations | findings citation-validation would have removed — 0 by construction for A/C/D, the headline number for B |
| latency | per-case wall time, reported as median/percentiles |

## 2. One-time setup

```bash
git clone https://github.com/maragem/VA-marketSurveillance
cd VA-marketSurveillance
git checkout claude/marketing-compliance-checker-nkcofd

cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd ..
```

You need a **Bedrock API key** (`AWS_BEARER_TOKEN_BEDROCK`) with model access
to the project model, and `AWS_REGION` (e.g. `eu-west-1`). Ask the supervisor
for scratch credentials — do not reuse the production key if a separate one
is available. The frontend is not needed; the harness talks straight to the
API.

**Local instance recipe** (used for every configuration; run from the repo
root, one shell per instance):

```bash
export DATA_DIR=$(mktemp -d)          # throwaway storage, fresh per config
export AWS_BEARER_TOKEN_BEDROCK=...   # omit entirely for config A
export AWS_REGION=eu-west-1
export ANTHROPIC_MODEL=eu.anthropic.claude-opus-4-8
cd backend
python -m uvicorn app.main:app --port 8000
```

Sanity checks before every run:

```bash
curl -s http://localhost:8000/api/health          # provider + model as expected?
curl -s http://localhost:8000/api/calibration     # rules as required by the config (see below)!
```

**Controlling calibration.** The engine loads calibration rules from
`$DATA_DIR/calibration.json`; if that file does not exist it is seeded from
`knowledge/calibration.json` (which contains 2 seed rules). Because A/B/C
must run *without* calibration, blank the working copy **after creating
`DATA_DIR` and before starting the server**:

```bash
echo '{"GLOBAL":[],"AI_ACT":[],"GDPR":[],"DSA":[],"UCPD":[]}' > "$DATA_DIR/calibration.json"
```

For D you do the opposite — install the full approved rule set (§6).
`GET /api/calibration` must show empty sections for A/B/C and the approved
set for D. Record this check in your lab notes for each run.

## 3. Configuration A — retrieval-only

Start the local instance **without any LLM credentials** (no
`AWS_BEARER_TOKEN_BEDROCK`, no `ANTHROPIC_API_KEY`), calibration blanked.
`/api/health` must report the heuristic/retrieval-only mode.

```bash
python bench/run.py --base-url http://localhost:8000 --runs 3
```

This costs nothing (no LLM calls) and is fast. Stability will be ~1.0 by
construction (the heuristic is deterministic); report it anyway for a
complete row.

## 4. Configuration C — deployed default

Fresh `DATA_DIR`, credentials set, calibration blanked.

```bash
# main row: full 52-case set, 3 repetitions for stability
python bench/run.py --base-url http://localhost:8000 --runs 3

# ALSO capture C restricted to the held-out cases — this is the baseline
# against which D is compared (same 15 cases, same protocol):
python bench/run.py --base-url http://localhost:8000 --runs 3 --holdout
```

Run C before B so you have the reference numbers early. Practical notes:

- 52 cases × 3 runs = 156 analyses. With the default `--concurrency 3` and
  multi-minute agentic analyses, budget **2–4 hours** and monitor the first
  few cases for timeouts (per-case timeout is 600 s; raise with `--timeout`
  if the model is slow).
- Watch Bedrock rate limits; if you see throttling errors in the backend
  log, drop to `--concurrency 2`.

## 5. Configuration B — no citation validation (ablation)

Fresh `DATA_DIR`, calibration blanked, credentials set, **plus**:

```bash
export EXPERIMENT_SKIP_CITATION_VALIDATION=1
```

Restart the backend with this flag (it is read at analysis time; the
accepted-event engine label becomes `agentic-unvalidated` — seeing that
label in the harness output confirms the flag took effect). Then:

```bash
python bench/run.py --base-url http://localhost:8000 --runs 3
```

The *invalid citations* metric in this scorecard is the paper's measurement
of what the validation layer removes (hallucinated node ids and
cross-regulation citations). Never set this flag on any shared or production
instance.

## 6. Configuration D — C + calibration, on the holdout

**6.1 Assemble the approved rule set.** The rules approved during benchmark
review live in the *deployment's* working copy, not yet in the repository.
On the deployed app: Benchmark page → calibration panel → **Export** (or
`GET /api/calibration/export`). Commit the downloaded file over
`knowledge/calibration.json` so the exact rule set used for D is versioned
with the results. Two invariants to verify on the export:

- every rule is a general legal principle — no benchmark case ids, brand
  names, or campaign facts (this keeps the benchmark an honest measurement);
- every rule's origin traces to review of *visible* cases (the app's
  proposer enforces this; hand-written rules need a human check).

If additional rules are wanted, propose them **only** from visible-case
deviations: run `--exclude-holdout`, review, use the app's "propose rules"
(it excludes holdout automatically), approve selectively.

**6.2 Run.** Fresh `DATA_DIR`; this time let the store seed from the
committed `knowledge/calibration.json` (i.e. do **not** blank the working
copy — just don't create one). Confirm `GET /api/calibration` shows the full
approved set. Then:

```bash
python bench/run.py --base-url http://localhost:8000 --runs 3 --holdout
```

**D is compared against C-on-holdout from §4** — same 15 cases, so the delta
is attributable to calibration alone and the cases were never seen by the
rule-writing process. Quote the full-set C row and the holdout C/D pair
separately in the paper; do not mix them.

## 7. Collecting and reporting the results

Every run writes three files under `bench/results/`:

- `<stamp>.md` — human-readable scorecard (the numbers for Table 1),
- `<stamp>.json` — machine-readable aggregate + per-case detail,
- `<stamp>-reports.jsonl` — raw engine outputs.

**Commit all of them** immediately after each run, with a commit message
naming the configuration, model id, flags, and git commit of the code — e.g.
`bench: config C, 52x3, eu.anthropic.claude-opus-4-8, code 5ad62f0`. The raw
reports are what make the paper auditable and allow relabelling without
re-inference:

```bash
python bench/run.py --rescore bench/results/<stamp>-reports.jsonl
```

re-scores stored outputs against the current labels at zero cost (results
are marked `-rescored`).

Keep a simple run log (date, config, model from `/api/health`, calibration
state, flags, result stamp). Table 1 is then a transcription exercise:
one row per configuration from the corresponding scorecard, with D (and its
C baseline) taken from the holdout runs.

## 8. Recommended order and time budget

| Step | What | Wall time | LLM cost |
|---|---|---|---|
| 1 | Setup + config A | ~1 h | none |
| 2 | Config C (full + holdout) | 3–5 h | ~200 analyses |
| 3 | Config B | 2–4 h | ~156 analyses |
| 4 | Calibration export/commit | ~30 min | none |
| 5 | Config D (holdout) | ~1 h | ~45 analyses |
| 6 | Rescores, commit results, fill table | ~1 h | none |

If anything forces a re-run (label fix, model change, flag mistake), re-run
the *whole affected configuration*, not individual cases — partial mixes are
not reportable.

## 9. Optional but strongly recommended: second annotator

The gold labels were drafted with model assistance and reviewed by one
domain expert. Reviewer confidence in Table 1 rises substantially with an
inter-annotator check:

1. A second annotator independently labels all 52 cases (or at minimum a
   stratified 20-case sample) using `bench/README.md`'s label semantics:
   `compliant`, `relevant`, must-find `provisions`, `acceptable_extra`,
   `min_risk`. The app's Benchmark page pointed at a scratch instance is the
   easiest tool.
2. Report agreement: percentage agreement + Cohen's κ on the `compliant`
   flag; per-provision precision/recall of annotator 2 against annotator 1
   (treating `acceptable_extra` as agreement-neutral); agreement on
   `min_risk` within one level.
3. Adjudicate disagreements together, fix labels in one commit, and
   `--rescore` the stored raw outputs — no re-inference needed.

## 10. Troubleshooting

- **`/api/health` shows the wrong model or provider** — the env vars in that
  shell are stale; `ANTHROPIC_API_KEY` beats Bedrock when both are set.
- **403 Marketplace/model-access error from Bedrock** — the model isn't
  enabled for the AWS account in that region; an account admin must enable
  it under Bedrock → Model access.
- **Throttling / timeouts** — lower `--concurrency`, raise `--timeout`;
  re-run the configuration cleanly once settings are stable.
- **A case hangs or errors repeatedly** — check the backend log; a single
  failed case invalidates the run (the scorecard denominators assume all 52),
  so fix the cause and re-run the configuration.
- **Scorecard shows unexpected calibration effects in A/B/C** — you forgot
  to blank `$DATA_DIR/calibration.json`; the `GET /api/calibration` check in
  §2 exists precisely for this.
