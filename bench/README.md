# Compliance benchmark

A versioned gold-standard test set for the analysis engine, plus a harness that
replays it against a running instance and produces a scorecard. Run it after
any prompt tweak, knowledge-graph edit, or model change to measure the effect
instead of guessing.

## Running

```bash
# against a local instance
python bench/run.py --base-url http://localhost:8000

# against the deployed app, 3 runs per case to also measure stability
python bench/run.py --base-url https://<your-app>.up.railway.app --runs 3

# a single case while iterating
python bench/run.py --only t1-detox-tea-influencer
```

Requires only `httpx` (already in backend/requirements.txt). Scorecards are
printed and saved to `bench/results/<timestamp>.{md,json}`, together with a
`-reports.jsonl` file of the raw engine outputs.

## Evaluation configurations and the held-out split

The paper's Table 1 grid maps to harness invocations:

| Config | How to run |
|---|---|
| A retrieval-only | run against a deployment with no LLM credentials |
| B no validation | deployment with `EXPERIMENT_SKIP_CITATION_VALIDATION=1` (never production) |
| C deployed default | normal deployment, `--runs 3` |
| D C + calibration | after approving rules, `--holdout` (see below) |

The scorecard's **invalid citations** metric counts findings that citation
validation would remove (unknown ids, cross-regulation citations) — 0 by
construction for A/C/D, measured for B. **Latency** is captured per case.

`bench/holdout.json` designates 15 held-out cases that never feed
calibration-rule distillation (the lesson proposer excludes them
automatically). Report configuration D on `--holdout`; use
`--exclude-holdout` for calibration-visible runs. Do not move cases out of
the held-out set once rules have been distilled.

**Relabelling without re-running:** after correcting gold labels, score the
stored raw outputs against the new labels with
`python bench/run.py --rescore bench/results/<stamp>-reports.jsonl` —
no inference cost, results marked `-rescored`.

Note: benchmark runs are persisted by the target instance like any analysis —
prefer a scratch deployment or a local instance with a throwaway `DATA_DIR` so
benchmark reports don't pollute the production dashboard.

## Case format (`cases.jsonl`, one JSON object per line)

```jsonc
{
  "id": "t1-detox-tea-influencer",   // unique, stable — referenced in scorecards
  "tier": 1,                          // 1 real-enforcement-inspired · 2 dataset-adapted · 3 synthetic
  "source": "why this case exists / where it came from",
  "campaign": { /* exactly a CampaignSubmission payload */ },
  "gold": {
    "compliant": false,          // true = control case: any finding >= medium is a false positive
    "relevant": ["UCPD"],        // regulations triage MUST route (recall only; extra routing is fine)
    "provisions": ["ucpd-annex1-17"],      // provision node ids findings MUST cite
    "acceptable_extra": ["ucpd-art6"],     // defensible extra citations — not errors, not required
    "min_risk": "high"           // minimum acceptable overall_risk (violating cases)
  }
}
```

Provision ids must exist in `knowledge/nodes.json`. Scoring conventions:

- A gold provision counts as **found at any severity**; predicted findings
  below `medium` are advisory and never counted as errors.
- **Unexpected** = an actionable (≥ medium) finding outside
  `provisions ∪ acceptable_extra`. Listed per case, not averaged away —
  each one is either a model error or a gap in the gold labels.
- For `compliant: true` controls, `relevant` may still list regulations the
  triage should reasonably route — the assessment must then come back clean.

## Reviewing / correcting the gold labels

**The easiest way is the built-in UI: the “Benchmark” page in the app.**
It lists every case with its labels, and each case expands into an editor —
relevant-regulation checkboxes, must-find / acceptable-extra provision pickers
(populated from the knowledge graph, so ids are always valid), min-risk,
compliant-control toggle, and the campaign text itself. You can also add and
delete cases. Edits are saved to the deployment's data volume; the
**Export cases.jsonl** button downloads the corrected set — commit it over
`bench/cases.jsonl` to version it. (The harness reads the repo file, so
commit the export before scoring against the corrected labels, or point
`--cases` at the downloaded file.)

The seed labels were drafted by the system's author-model and **need human
legal review** — treat them as proposals:

1. Run the benchmark once and open the scorecard.
2. For every *unexpected* finding: if the citation is actually right, move it
   into `provisions` (must-find) or `acceptable_extra` (defensible); if wrong,
   leave it — it is a genuine precision error the engine should lose points for.
3. For every *missed* provision: confirm the provision really is engaged by the
   campaign text; if it's a stretch, demote it to `acceptable_extra` or drop it.
4. Adjust `min_risk` where the severity intuition is off.
5. Commit the edited `cases.jsonl` — the benchmark is only as good as its gold.

Keep case ids stable so scorecards remain comparable across revisions; add new
cases rather than repurposing old ids.

## Metrics

| metric | meaning | failure it catches |
|---|---|---|
| gold-provision recall | share of must-find provisions cited | violations going unexamined |
| missed triage routings | gold-relevant regulations never routed | triage filtering out real risk |
| unexpected actionable findings | citations outside the allowed set | over-flagging / hallucinated relevance |
| false positives on controls | compliant campaigns flagged ≥ medium | credibility-killing over-enforcement |
| risk calibration | overall_risk ≥ gold min_risk | correct findings, understated severity |
| stability (`--runs N`) | pairwise Jaccard of finding sets | non-deterministic verdicts |

## Manual evaluation through a chat UI (configuration E)

Where an external model is reachable only through a web interface (e.g. GPT@EC),
`make_gptec_workbook.py` produces an Excel workbook that lets assistants run the
benchmark by hand, and `score_gptec_workbook.py` scores the pasted answers with
the same code as the automated runs.

```bash
python bench/make_gptec_workbook.py                     # -> bench/gptec-evaluation.xlsx
# ... assistants paste prompts into the chat UI and paste the replies back ...
python bench/score_gptec_workbook.py bench/gptec-evaluation.xlsx
python bench/score_gptec_workbook.py bench/gptec-evaluation.xlsx --holdout
```

The workbook has one row per campaign carrying a ready-to-paste prompt that
reproduces the deployed specialists' task definition: the same closed provision
vocabulary (all 40 ids, so an id outside the list is measurable as an invalid
citation), the same severity guide and risk scale, and a strict single-JSON-object
output contract. Gold labels sit on a separate tab that assistants are told not
to consult while running. The scorer writes the usual
`scorecard.md` / `results.json` / `reports.jsonl` triple into `results/`, so the
row can be added to Table 1 via `make_table1.py` and re-scored later with
`run.py --rescore`.

**What this configuration is, and is not.** A chat UI cannot run the agentic
loop, so configuration E is a *single-call, closed-vocabulary baseline* on a
different model — not a model swap of configuration C. It varies model family
and architecture at the same time, and is reported as an external baseline
rather than as evidence that the architecture is model-agnostic. Isolating the
model variable requires API access and a per-job model override in the
Experiments runner.
