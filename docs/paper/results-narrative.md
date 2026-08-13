# Results narrative for §3.2 (draft for the manuscript)

Supersedes the earlier §3.2 text: those figures came from a July run against a
pre-freeze label set and a different case count. Everything below is generated
from the five committed result artifacts in `bench/results/`; Table 1 itself is
produced by `python bench/make_table1.py`.

---

## Experimental protocol (for §3.1 or the start of §3.2)

All configurations were evaluated on the same frozen gold set of 52 campaigns
(19 tier 1, 17 tier 2, 16 tier 3), comprising 97 must-find provisions and 7
compliant control campaigns, with three independent runs per campaign. All
language-model configurations used Claude Opus 4.8 served through the Amazon
Bedrock European cross-region inference profile
(`eu.anthropic.claude-opus-4-8`); configuration A uses no language model at
all. Runs were executed server-side by the deployed instance itself, which
checkpoints each completed analysis to persistent storage, so a configuration
is evaluated as a single indivisible unit rather than assembled from partial
client sessions.

Fifteen of the 52 campaigns (including 2 controls and 26 must-find provisions)
were designated a held-out split before any calibration rule was written, and
were excluded by construction from the rule-distillation procedure.
Configuration D is reported on this split, and is compared against
configuration C restricted to the same 15 campaigns — the two runs differ only
in whether the approved calibration rules were injected into the specialist
agents' prompts.

Scoring conventions: a must-find provision counts as found if cited at any
severity; unexpected findings are actionable citations (severity ≥ medium)
outside the union of must-find and defensible-extra provisions; a control
campaign counts as a false positive if any actionable finding is returned or
the overall risk reaches medium; stability is the mean pairwise Jaccard
similarity of the three runs' finding sets. Per-campaign metrics other than
stability are computed from the first run, with the remaining runs used for the
stability measure.

## Table 1

See `docs/paper/table1.md` (regenerate with `python bench/make_table1.py`).

## 3.2.1 The reasoning layer, not retrieval, produces usable assessments

Configuration A isolates the GraphRAG retrieval layer. It locates roughly half
of the required provisions (recall 0.515) but is unusable as a screening
instrument: it returns 303 unexpected actionable findings (5.8 per campaign)
and flags **all seven** compliant control campaigns. Its perfect stability
(1.000) simply reflects determinism, not quality. Retrieval establishes which
provisions are topically related to a campaign; deciding whether a provision is
actually engaged — and by this addressee, on these facts — is what the agentic
layer contributes. Adding it (configuration C) roughly doubles recall, halves
the over-flagging rate, and takes control false positives from 7/7 to 1/7.

## 3.2.2 The deployed configuration

Configuration C recovers 95 of 97 must-find provisions (0.979) with complete
triage recall — no gold-relevant regulation was left unrouted in any of the 52
campaigns — passes risk calibration on 51 of 52 campaigns, and returns a mean
55 s per campaign. Two observations deserve care.

First, the two apparently missed provisions are a scoring artifact rather than a
capability gap. Both are AI Act Article 5 prohibitions on
`t3-emotion-optimized-ads`, the benchmark's hardest case (a platform-side
system inferring emotional state, engaging all four instruments). The first
run of that campaign omitted them; runs 2 and 3 cited both, correctly
attributed. Scored on a majority or union of the three runs, configuration C
also reaches recall 1.000. We report the first-run figure because it is the
conservative single-shot number a user would experience, but the sensitivity is
worth stating: for this architecture, run-to-run variance on genuinely hard
multi-instrument cases is a larger effect than any systematic omission.

Second, the single control false positive is a borderline data-protection
judgement rather than an over-reading of the marketing claims: the system
raised lawful-basis and objection findings on a compliant campaign's e-mail
programme. Notably, configuration B produced exactly one control false
positive as well, but on a *different* control campaign — indicating a general
tendency to over-attach GDPR provisions where a campaign mentions e-mail or
personalisation, rather than a defect specific to one case. This is precisely
the failure mode the calibration rules target (§3.2.4).

## 3.2.3 Citation validation contributes integrity, not precision

Configuration B disables the post-hoc validation that drops citations to
unknown identifiers or to another regulation's provisions. Across all 156
analyses it produced exactly **one** invalid citation: a knowledge-graph
*concept* node (`c-emotion-targeting`) cited as though it were a UCPD
provision. The validation layer is therefore cheap insurance rather than a
major quality contributor — because the specialists reach provisions through
graph tools that return only real provision nodes, invalid citations are rare
before validation ever runs. We report this as a negative result: the ablation
does not show validation improving recall, precision, or calibration, and the
over-flagging rate is statistically indistinguishable between B and C (2.96 vs
3.12 unexpected findings per campaign; the difference is within run-to-run
variation). Its value is that a single fabricated legal citation in a
regulator-facing report is a disproportionate failure, and the guarantee it
provides is absolute rather than probabilistic.

## 3.2.4 Calibration transfers to unseen cases

Configuration D is the study's clearest result. On the 15 held-out campaigns,
injecting the 15 human-approved calibration rules reduced unexpected actionable
findings from **44 to 5** — an 89% reduction, from 2.9 to 0.33 per campaign —
while recall remained at 1.000, both controls remained clean, risk calibration
remained 15/15, and run-to-run stability *improved* from 0.745 to 0.833.

A citation-level comparison of the two runs shows the mechanism is the intended
one: 39 unexpected citations were removed, **none were added, and no must-find
provision was lost**. The removals track the content of the rules rather than
being diffuse suppression — DSA platform obligations withdrawn from
advertiser-side campaigns (12 citations), GDPR provisions withdrawn where the
record showed no processing or consent defect (12), general-clause redundancy
eliminated where a specific blacklist item already captured the conduct (9),
and AI Act provisions withdrawn where no AI system was actually deployed (6).
The most pronounced case, an advertisement impersonating an official
government notice, fell from 11 unexpected citations to 1.

Two aspects make this more than a prompt-engineering result. The rules were
distilled only from deviations observed on the 37 calibration-visible
campaigns, and the 15 evaluation campaigns were designated before any rule was
written; the improvement is therefore transfer to unseen cases, not fitting.
And the rules are general legal principles about scope, addressee and
specificity — they never reference a campaign, a brand, or a benchmark answer
— so what improves is the system's doctrinal discipline rather than its memory
of the test set.

The five surviving unexpected citations are defensible-but-unrequired readings
rather than errors of law (for instance consent-quality provisions on an
aggressive retargeting programme), and are candidates for reclassification as
defensible extras under a second annotation pass. Residual precision headroom
is therefore smaller than the count suggests.

## 3.2.5 Limitations

- **Single annotator.** The gold labels were drafted with model assistance and
  reviewed by one domain expert. Inter-annotator agreement is not yet measured;
  the protocol for a second annotation pass is specified in
  `docs/paper/table1-runbook.md` §9, and stored raw outputs allow re-scoring
  against revised labels without re-running inference.
- **Single model, single provider.** All figures are for Claude Opus 4.8 on
  Bedrock. Whether the calibration transfer replicates on other model families
  is untested.
- **Benchmark scale and provenance.** 52 campaigns is small, and while tier 1
  cases are inspired by real enforcement actions, the campaigns themselves are
  synthetic reconstructions rather than sampled live advertising.
- **First-run scoring.** Point metrics come from the first of three runs
  (§3.2.2); majority-vote aggregation would raise configuration C's reported
  recall from 0.979 to 1.000.
- **Two incomplete analyses.** Configurations C (full) and C (holdout) each had
  one or two of their case-runs fail on transient infrastructure errors
  (154/156 and 44/45 completed). Every campaign retained at least two scored
  runs, so no campaign is missing from any row.

## Reproducibility statement (for the data-availability section)

Every reported number derives from an archived artifact. For each
configuration, `bench/results/` holds the scorecard, the machine-readable
per-campaign results, and the raw engine outputs; Table 1 is generated from
those files by `bench/make_table1.py`. Re-scoring a stored run against revised
labels requires no inference: `python bench/run.py --rescore
bench/results/<job>-reports.jsonl`. The gold set (`bench/cases.jsonl`), the
held-out split (`bench/holdout.json`), the approved calibration rules
(`knowledge/calibration.json`) and the knowledge graph (`knowledge/`) are all
versioned; each result file records the model identifier and a hash of the case
set it was scored against.
