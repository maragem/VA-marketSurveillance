# Results narrative for §3 (revised draft, October 2026)

Replaces the earlier §3.2 text. This revision adds the external-model
evaluation requested by both reviewers, interval estimates and significance
tests for the headline claims, a throughput-and-workload analysis for
large-scale use, and a reworked threats-to-validity section. Every figure is
generated from the committed artifacts in `bench/results/`; Table 1 comes from
`bench/make_table1.py` and the statistics from `bench/make_stats.py`.

**Editorial fixes to apply while integrating this text** (raised by Reviewer 1,
or found while checking the manuscript against the repository):

1. §3.2.2 contains the same paragraph twice ("Second, the single control false
   positive…"); the second copy also reads "e-mail programmed". Delete the
   duplicate.
2. §2.1 states the graph holds 36 provisions. It holds **40** provisions across
   60 nodes and 132 edges. Correct the count.
3. Tables 3, 4 and 5 report an earlier, superseded run and are flagged as such
   in their own captions. Table 4 in particular lists missed provisions (UCPD
   Arts. 6 and 7) that are not the omissions in the frozen results. Replace
   them with §§3.2.2–3.2.6 below, which are generated from the frozen
   artifacts, or delete them.

---

## 3.1 Evaluation protocol

All configurations were evaluated on the same frozen gold set of 52 campaigns
(19 tier 1, 17 tier 2, 16 tier 3) comprising 97 must-find provisions and 7
compliant control campaigns. Configurations A–D were executed server-side by
the deployed instance, which checkpoints every completed analysis to persistent
storage, so a configuration is evaluated as one indivisible unit rather than
assembled from partial client sessions; each ran three times per campaign.
Configurations A–D used a single model, Claude Opus 4.8, served through the
Amazon Bedrock European cross-region inference profile; configuration A uses no
language model at all.

Configuration E adds an **external, cross-family comparison**. Three models
were evaluated through the European Commission's GPT@EC interface — the
proprietary GPT-5.4 and GPT-5.6, and the open-weights gpt-oss-120b. The
interface exposes no programmatic API, so each campaign was submitted manually
in a fresh conversation by trained assistants: 52 campaigns × 2 runs × 3
models = 312 conversations. The prompt reproduces the deployed
specialist agents' task definition — the identical closed vocabulary of 40
provision identifiers with their references and obligations, the identical
five-level severity guide and risk scale, and a strict single-JSON-object
output contract — and the answers were scored by the same program that scored
the automated configurations. Configuration E therefore varies **both** the
model family and the architecture (a single call replaces triage, graph tool
use and synthesis), and is reported as an external baseline rather than as an
isolated model swap; §3.2.5 separates the two effects as far as the design
allows.

Fifteen of the 52 campaigns (2 controls, 26 must-find provisions) were
designated a held-out split before any calibration rule was written and were
excluded by construction from rule distillation. Configuration D is reported on
this split and compared against configuration C restricted to the same 15
campaigns; configuration E is reported on both panels.

Scoring conventions: a must-find provision counts as found if cited at any
severity; unexpected findings are actionable citations (severity ≥ medium)
outside the union of must-find and defensible-extra provisions; a control
campaign counts as a false positive if any actionable finding is returned or
the overall risk reaches medium; stability is the mean pairwise Jaccard
similarity of the finding sets across repeated runs. Point metrics other than
stability use the first run of each campaign. First-run scoring is deliberate:
it is the single-shot result a user actually receives, and it is the
conservative choice, since majority or union aggregation can only add
correctly-found provisions. §3.2.2 reports the sensitivity.

Recall figures carry 95% Wilson intervals. The calibration effect is tested by
an exact Wilcoxon signed-rank test over per-campaign counts with a paired
bootstrap interval, and configuration C is compared with each external model by
an exact McNemar test over must-find outcomes.

## Table 1

See `docs/paper/table1.md` (regenerate with `python bench/make_table1.py`).

## 3.2.1 The reasoning layer, not retrieval, produces usable assessments

Configuration A isolates the GraphRAG retrieval layer. It locates roughly half
the required provisions (recall 0.515, 95% CI [0.417, 0.612]) but is unusable
as a screening instrument: 303 unexpected actionable findings (5.8 per
campaign) and false positives on **all seven** compliant controls. Its perfect
stability reflects determinism, not quality. Retrieval establishes which
provisions are topically related to a campaign; deciding whether a provision is
actually engaged — and by this addressee, on these facts — is what the agentic
layer contributes. Adding it (configuration C) nearly doubles recall, halves
the over-flagging rate and takes control false positives from 7/7 to 1/7.

Because this configuration is deterministic it also cross-checks the
measurement apparatus: an independent replication executed five days later on a
separate instance, scored through the command-line harness rather than the
in-application runner, reproduced the deployment run exactly — identical
matched, missed and unexpected provision sets, risk verdicts and control
outcomes on all 52 campaigns. The two scoring paths and the two copies of the
gold labels are in exact agreement.

## 3.2.2 The deployed configuration

Configuration C recovers 95 of 97 must-find provisions (0.979, CI [0.928,
0.994]) with complete triage recall — no gold-relevant regulation was left
unrouted in any of the 52 campaigns — passes risk calibration on 51 of 52
campaigns, and returns a mean 54.7 s per campaign. Two observations deserve
care.

First, the two apparently missed provisions are a scoring artifact rather than a
capability gap. Both are AI Act Article 5 prohibitions on
`t3-emotion-optimized-ads`, the benchmark's hardest campaign (a platform-side
system inferring emotional state, engaging all four instruments). The first run
omitted them; runs 2 and 3 cited both, correctly attributed. Scored by majority
or union over the three runs, configuration C also reaches recall 1.000. We
report the first-run figure as the conservative single-shot number, but the
sensitivity matters: for this architecture, run-to-run variance on genuinely
hard multi-instrument campaigns is a larger effect than any systematic
omission.

Second, the single control false positive is a borderline data-protection
judgement rather than an over-reading of the marketing claims: the system
raised lawful-basis and objection findings on a compliant campaign's e-mail
programme. Configuration B produced exactly one control false positive as well,
but on a *different* control campaign, which indicates a general tendency to
over-attach GDPR provisions wherever a campaign mentions e-mail or
personalisation rather than a defect specific to one case. This is precisely
the failure mode the calibration rules target (§3.2.4).

## 3.2.3 Citation validation contributes integrity, not precision

Configuration B disables the post-hoc validation that drops citations to
unknown identifiers or to another regulation's provisions. Across all 156
analyses it produced exactly **one** invalid citation: a knowledge-graph
*concept* node (`c-emotion-targeting`) cited as though it were a UCPD
provision. We report this as a negative result. The ablation does not show
validation improving recall, precision or calibration, and the over-flagging
rate is statistically indistinguishable between B and C (2.96 against 3.12
unexpected findings per campaign, within run-to-run variation). Its value is
categorical rather than statistical: one fabricated legal citation in a
regulator-facing report is a disproportionate failure, and the guarantee
validation provides is absolute rather than probabilistic.

Configuration E sharpens the interpretation considerably. Across **309 scored
external-model runs spanning three models — two proprietary and one
open-weights — not one invalid citation was produced**: no invented identifier,
no provision attributed to the wrong instrument. The constraint that does the
work is therefore the *closed vocabulary supplied in the prompt*, not the
agentic loop and not the post-hoc validator. Given an explicit, enumerated set
of citable provisions, four models across three families stayed inside it, and
the one open-weights model did so despite being the weakest performer on every
other metric in Table 1. This is the strongest available evidence for the
architectural claim of Section 1 — that hallucination resistance is a property
of the closed-world citation design rather than of any particular model — and
it is evidence the single-model experiments could not have provided. The post-hoc validator remains justified as a cheap backstop for
the rare lapse and for the concept-node confusion configuration B exposed, but
it should be presented as defence in depth, not as the mechanism.

## 3.2.4 Calibration transfers to unseen campaigns

Configuration D is the study's clearest result. On the 15 held-out campaigns,
injecting the 15 human-approved calibration rules reduced unexpected actionable
findings from **44 to 5** — an 88.6% reduction, from 2.93 to 0.33 per campaign
— while recall remained at 1.000, both controls remained clean, risk
calibration remained 15/15 and run-to-run stability *improved* from 0.745 to
0.833.

The effect is statistically unambiguous despite the modest sample. Paired by
campaign, 11 of 15 campaigns improved, **none worsened** and 4 were unchanged;
the mean reduction is 2.6 unexpected findings per campaign (bootstrap 95% CI
[1.33, 4.07]; exact Wilcoxon signed-rank W = 0, two-sided p = 0.00098).

A citation-level comparison shows the mechanism is the intended one: 39
unexpected citations were removed, **none were added, and no must-find
provision was lost**. The removals track the content of the rules rather than
being diffuse suppression — 12 DSA platform-obligation citations withdrawn from
advertiser-side campaigns, 12 GDPR citations withdrawn where the record showed
no processing or consent defect, 9 UCPD citations of which 8 were general
clauses eliminated where a specific blacklist item already captured the
conduct, and 6 AI Act citations withdrawn where no AI system was actually
deployed. The most pronounced case,
an advertisement impersonating an official government notice, fell from 11
unexpected citations to 1.

Two aspects make this more than a prompt-engineering result. The rules were
distilled only from deviations observed on the 37 calibration-visible
campaigns, and the 15 evaluation campaigns were designated before any rule was
written, so the improvement measures transfer to unseen campaigns rather than
fitting. And the rules are general legal principles about scope, addressee and
specificity that never reference a campaign, a brand or a benchmark answer, so
what improves is the system's doctrinal discipline rather than its memory of
the test set.

The five surviving unexpected citations are defensible-but-unrequired readings
rather than errors of law (for instance consent-quality provisions on an
aggressive retargeting programme) and are candidates for reclassification as
defensible extras; §3.3 explains why that judgement is deferred to the second
annotator rather than made by the authors.

## 3.2.5 External models: what is architecture and what is model

Configurations E1–E3 place three further models against the same gold set,
under the same closed vocabulary and the same scoring rules, but in a single
call rather than the agentic pipeline: two proprietary frontier models from a
different vendor (GPT-5.4, GPT-5.6) and one open-weights model
(gpt-oss-120b).

**The agentic pipeline's advantage is recall, and it is large and significant.**
Configuration C found 95 of 97 must-find provisions; GPT-5.4 found 80 (0.825,
CI [0.737, 0.888]), GPT-5.6 found 74 (0.763, CI [0.669, 0.836]) and
gpt-oss-120b found 59 (0.608, CI [0.509, 0.699]). The comparison is
near-dominant rather than merely favourable: paired over must-find outcomes, 15
provisions were found only by configuration C and none only by GPT-5.4 (exact
McNemar p = 6.1 × 10⁻⁵); against GPT-5.6, 22 only by configuration C and 1 only
by the external model (p = 5.7 × 10⁻⁶); against gpt-oss-120b, 37 only by
configuration C and 1 only by the external model (p = 2.8 × 10⁻¹⁰). On the
harder held-out split the gap widens, to 0.615, 0.692 and 0.538 against
1.000.

**The single-call baselines are, however, markedly more conservative.** GPT-5.4
produced 1.65 unexpected actionable findings per campaign and GPT-5.6 only 0.23
— against 3.12 for configuration C — and both achieved 0/7 on the compliant
controls, where configuration C recorded one false positive. Read alone, that
looks like a precision win for the simpler architecture. Read against
configuration D it is not: calibrated configuration D reaches 0.33 unexpected
findings per campaign on the held-out split **while keeping recall at 1.000**,
whereas GPT-5.6 reaches a comparable 0.27 only by forgoing 31% of the must-find
provisions. The calibration loop therefore delivers the precision of the
conservative baseline without its recall cost, which is the central practical
argument for the regulator-in-the-loop design.

**The open-weights model separates two claims that the proprietary models left
entangled.** gpt-oss-120b honoured the closed vocabulary perfectly (zero
invalid citations in 104 runs) yet failed at screening in every other respect:
recall 0.608, 2.40 unexpected findings per campaign, the lowest stability in
the study (0.550), and — most damaging for an enforcement instrument — false
positives on **six of seven** compliant controls, a control-discipline failure
close to the retrieval-only baseline's 7/7. The distinction this licenses is
worth stating precisely, because it is the honest answer to the
model-agnosticism question: the *citation-integrity* property of the
architecture is model-agnostic, holding even on a weak open-weights model,
whereas *screening quality* is not. A deployment can inherit the guarantee that
no fabricated legal anchor reaches a report without inheriting usable recall or
usable precision; capability still has to be bought.

Severity judgement also separates the configurations: risk calibration passes
51/52 for configuration C against 47/52, 43/52 and 45/52 for the external
models, and 15/15 against 12/15, 10/15 and 13/15 on the held-out split — the
single-call models under-rate severity on campaigns they do flag.

**The blind spots are systematic and relevant to this venue.** Twelve must-find
provisions were missed by *both* proprietary external models yet found by
configuration C.
Five of those twelve are synthetic-media provisions — UCPD Annex I point 23c
(fake endorsement) and AI Act Article 50(2) (synthetic-content marking) — and
they account for every AI-media campaign in the set: the cloned-voice radio
spot, the AI-retouched cosmetics campaign, the deepfake physician endorsement
and the virtual influencer. Three more cluster on
`t3-emotion-optimized-ads`, the four-instrument platform case. Per instrument,
external recall falls furthest on the two newest instruments: DSA (3/6, 4/6 and
3/6 against 6/6) and the AI Act (4/8, 5/8 and 5/8 against 6/8), while UCPD
recall holds up better (51/59, 46/59 and 39/59 against 59/59). The reading we offer is that
single-pass assessment handles well-established consumer-protection doctrine
reasonably but under-detects the AI- and platform-specific obligations that
require connecting a campaign's technical description to a recent provision —
exactly where graph-grounded retrieval and multi-turn investigation contribute
most, and exactly the content types that motivate this work.

**Two caveats bound these comparisons.** First, configuration E changes
architecture and model family together, so the recall gap cannot be attributed
to the model alone; isolating that factor requires running the full pipeline on
a different model, which needs programmatic access the GPT@EC interface does
not offer. Second, configuration E ran two repetitions per campaign against
three for configurations A–D, so its stability figures (0.653, 0.775 and 0.550)
rest on a single pair per campaign.

## 3.2.6 Throughput, cost and reviewer workload at scale

Configuration C's measured mean latency is 54.7 s per campaign (configuration
D, 52.5 s), with per-campaign latency ranging from 35.8 s to 72.9 s. Because
campaigns are independent, throughput scales with concurrency rather than with
corpus size: at the deliberately conservative concurrency of 2 used for these
runs, a 10,000-campaign sweep would take roughly 76 hours of wall-clock time,
and at concurrency 10 roughly 15 hours — within the horizon of a coordinated
CPC sweep, which typically runs over weeks. Inference cost is of the order of a
few tens of euro-cents per campaign at the provider's published rates for the
model used, so the same sweep costs a few thousand euro: material, but small
beside the human effort it triages.

The more instructive scaling quantity is **reviewer workload**, which the
calibration loop changes by an order of magnitude. Uncalibrated, configuration
C emits 3.12 unexpected actionable findings per campaign, each of which a human
must adjudicate as either an engine error or a gold-label gap; across 10,000
campaigns that is on the order of 31,000 review items. Calibrated, the rate on
unseen campaigns is 0.33 per campaign — on the order of 3,300 items, with 41 of
52 campaigns in the most conservative configuration returning no unexpected
finding at all. Since the rules are written once and apply to every subsequent
campaign, the human cost of calibration is fixed while its benefit scales
linearly with the corpus. That asymmetry, rather than raw latency, is what
makes the design plausible for authority-scale screening.

Two limits on this extrapolation should be stated. The benchmark campaigns are
compact textual briefs; authentic scraped material is longer and noisier, which
will raise both latency and the deviation rate. And no claim is made that
calibration rules distilled from 37 campaigns suffice for a corpus three orders
of magnitude larger: the loop is designed to continue, with new rules proposed
as new error patterns appear, and the honest expectation is a decaying
but non-zero rule-authoring workload as coverage broadens.

## 3.3 Threats to validity

**Single-annotator gold labels.** The gold labels were drafted with model
assistance and reviewed by one domain expert, who is also an author of this
paper and who approved the calibration rules. Inter-annotator agreement is not
yet measured, so residual unexpected citations may conflate engine error with
label incompleteness, and the independence of the transfer claim in §3.2.4
rests on one person's judgement. A second annotation pass is specified and
tooled: a second qualified annotator labels the full set (or a stratified
sample) through the benchmark interface; agreement is reported as percentage
agreement and Cohen's κ on the compliant/violating decision, per-provision
precision and recall of the second annotator against the first with
defensible-extras treated as agreement-neutral, and agreement within one level
on minimum risk; disagreements are adjudicated jointly. Because every raw
engine output is stored, revised labels are applied by re-scoring without any
re-running of inference, so the reported configurations can all be updated
against the corrected gold at no inference cost. The five surviving unexpected
citations in configuration D are deliberately left unreclassified until that
pass, so that the authors do not adjudicate their own system's residual errors.

**Model and provider coverage.** Configurations A–D use one model from one
provider; configuration E adds three further models, including one with open
weights, but only in the single-call architecture. The claim that the
architecture is model-agnostic is therefore established for the closed-world
citation property — which held across four models and three families, 309
external runs, without a single invalid citation — and explicitly *not* claimed
for screening quality, which varied by a factor of 1.6 in recall and by 6/7
against 0/7 in control false positives across those same models. What remains
untested is the agentic pipeline itself on a non-Claude model; that requires
programmatic access and a per-job model override in the evaluation runner, and
is the natural next experiment.

**Benchmark scale and provenance.** The frozen benchmark contains 52 campaigns
with 15 held out. Tier-1 campaigns are inspired by real enforcement actions,
but all campaigns are synthetic reconstructions rather than sampled live
advertising, so external validity to noisy authentic material remains open. The
held-out panel is small enough that recall intervals are wide (1.000 on 26
must-find provisions has a 95% lower bound of 0.871). A further constraint now
binds: configurations C and D both score 1.000 on the holdout, so the benchmark
has no remaining recall headroom to measure improvement on. Expanding the set —
towards roughly 100 campaigns with a 30-campaign holdout, weighted towards
multi-instrument and platform-side cases — is therefore necessary for the
metric to stay informative, independent of the sample-size argument.

**Modality.** The present system reasons over textual, contextual and
provenance representations of campaigns, including spoken transcripts for
retrieved video, and not over image pixels, video frames or acoustic signals.
Violations carried solely in the visual or audio channel — an illegible
on-screen disclaimer, a superimposed claim absent from the transcript,
child-appealing visual styling under neutral copy — are therefore outside its
present reach. This is a boundary of the current deployment rather than of the
architecture, since the specialist agents' inputs are model-native and the
graph-grounded citation mechanism is modality-independent; §4 sets out the
extension.

**First-run scoring and incomplete repetitions.** Point metrics other than
stability use the first of up to three runs, for the reasons given in §3.1;
majority or union scoring would raise configuration C's recall from 0.979 to
1.000. Configurations C (full) and C (holdout) each lost one or two case-runs
to transient infrastructure errors (154/156 and 44/45 completed), with every
campaign retaining at least two scored runs. In configuration E1, three of 104
recorded answers could not be attributed to a campaign with certainty, because
replies for several campaigns had been pasted into one cell during manual
transcription; those runs were excluded rather than scored, leaving 101 of 104.
Manual transcription is an error channel the automated configurations do not
have, and it is a reason to prefer programmatic access wherever a provider
offers it.

**Calibration contamination and shared blind spots.** The held-out split was
designated before calibration-rule writing and excluded from rule distillation,
which materially strengthens the transfer claim. It does not establish
independence from the benchmark design or from the base model: rules were
distilled by, and adjudication assisted by, the same model family under
evaluation, so a shared blind spot would be invisible to this procedure.
Configuration E provides partial reassurance — an external model family
independently reproduced the addressee error the DSA rule was written to
correct, citing a platform obligation against an advertiser while explicitly
noting in its own rationale that the obligation binds platform providers —
which suggests the rules encode a general doctrinal weakness rather than a
quirk of one model.

**Jurisdictional scope.** The legal graph covers four EU-level instruments.
National transpositions of the UCPD, sector-specific advertising rules
(medicinal products, financial promotions, food and health claims, audiovisual
media services) and Member State supervisory practice are outside it. A
campaign screened as raising no concern against this corpus is therefore not
thereby compliant in any Member State, and the system's output must not be read
as a jurisdictional clearance. The benchmark's gold labels share this boundary:
provisions outside the four instruments are deliberately absent from the
must-find sets even where they would apply in practice, which the annotation
guidance records explicitly.

## Reproducibility statement

Every reported number derives from an archived artifact. For each
configuration, `bench/results/` holds the scorecard, the machine-readable
per-campaign results and the raw engine outputs; Table 1 is generated from
those files by `bench/make_table1.py` and the interval and significance
estimates by `bench/make_stats.py`. Re-scoring a stored run against revised
labels requires no inference
(`python bench/run.py --rescore bench/results/<job>-reports.jsonl`). The gold
set, the held-out split, the approved calibration rules, the knowledge graph,
the agent prompts and the evaluation harness are all versioned; each result
file records the model identifier and a hash of the case set it was scored
against. The manual evaluation of configuration E is reproducible from the
distributed workbook (`bench/gptec-evaluation.xlsx`), which carries the
per-campaign prompts, and the completed workbook with all 208 transcribed
answers is archived alongside the results
(`bench/gptec-evaluation-completed.xlsx`).
