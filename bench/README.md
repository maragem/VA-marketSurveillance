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
printed and saved to `bench/results/<timestamp>.{md,json}`.

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
