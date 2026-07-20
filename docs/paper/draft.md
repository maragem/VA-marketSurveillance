# Regulator-in-the-Loop Compliance Screening: Graph-Grounded LLM Agents with a Continuously Calibrated Benchmark for EU Marketing Law

**Emmanouil Maragkoudakis** — European Commission¹
*(affiliation footnote, disclaimers and co-authors to be settled during internal clearance)*

¹ The views expressed are purely those of the author and may not in any circumstances be regarded as stating an official position of the European Commission.

---

## Abstract

Market-surveillance authorities face a growing volume of marketing content whose compliance with EU consumer and digital law — the Unfair Commercial Practices Directive (UCPD), the GDPR, the Digital Services Act (DSA) and the AI Act — cannot be reviewed manually at scale. We present a deployed decision-support system that screens marketing campaigns, submitted as text or harvested from public platforms, using large-language-model agents grounded in a curated legal knowledge graph. The system enforces *citation grounding*: findings may only reference provisions retrieved from the graph, are validated post-hoc against it, and are anchored to authentic legal text through CELLAR/ELI identifiers resolved against the EU Publications Office. Around the engine we build what we argue is the paper's main contribution: a **regulator-in-the-loop calibration methodology**. A human-reviewed gold benchmark of adversarially designed cases (enforcement-inspired, dataset-adapted, and synthetic compliant controls) is coupled with (i) an adversarial *adjudicator* that gives reviewers a second opinion on disputed citations, testing scope, addressee and textual support; (ii) a *lesson-distillation* step that converts recurring, human-confirmed errors into general calibration rules injected into the agents' prompts; and (iii) contamination discipline that keeps the benchmark an honest measurement while the engine learns from it. We report evaluation across engine ablations (retrieval-only, agentic, agentic + calibration) on the benchmark, and release the benchmark, knowledge graph and calibration corpus. [TODO: one sentence with headline numbers once final runs are in.]

**Keywords:** legal NLP, LLM agents, GraphRAG, market surveillance, consumer protection, UCPD, DSA, AI Act, GDPR, benchmark, human-in-the-loop

---

## 1. Introduction

Consumer-protection and digital-market enforcement in the EU rests on four instruments with overlapping reach into marketing practice: the UCPD (2005/29/EC) with its Annex I blacklist, the GDPR (2016/679) for data-driven marketing, the DSA (2022/2065) for platform-mediated advertising and dark patterns, and the AI Act (2024/1689) for AI-generated and AI-mediated persuasion. Enforcement capacity has not scaled with content volume: coordinated CPC sweeps repeatedly find high violation rates in areas such as dark patterns, influencer disclosure and environmental claims [refs], yet each sweep covers only hundreds of traders, manually.

Large language models are an obvious candidate for first-line screening, but their known failure modes are disqualifying in an enforcement context in their raw form: fabricated or imprecise legal citations, unstable verdicts, and reasoning that stretches provisions beyond their addressees (for example, applying platform obligations to advertisers). An authority cannot act — or even triage — on findings whose legal anchors may not exist.

This paper makes three claims. **First**, hallucination-resistant screening is an architecture property, not a model property: we constrain LLM agents to cite only provisions they have retrieved from a curated knowledge graph, validate every citation post-hoc against that graph, and resolve each provision to authentic text in the Publications Office CELLAR repository. **Second**, the scarce resource in this domain is not model capability but *calibrated legal judgement*, and it can be captured systematically: we couple a human-reviewed benchmark with an adversarial adjudication aid and a lesson-distillation step that converts recurring human-confirmed errors into general prompt-level calibration rules — a loop a single domain expert can operate from a web interface. **Third**, such a loop can remain honest: we make the train/test-contamination risk explicit and adopt discipline (generality constraints on rules, held-out cases) that preserves the benchmark's value as measurement.

We describe the deployed system (Section 3), the benchmark and its review methodology (Section 4), the calibration loop (Section 5), and an evaluation protocol with ablations isolating the contribution of graph grounding, agentic investigation and calibration (Section 6). We release the benchmark, the knowledge graph, and the calibration corpus. [TODO: repository/DOI reference after clearance.]

## 2. Related Work

**LLMs for legal analysis.** [1–2 paragraphs: legal judgment prediction and statutory reasoning; LegalBench and related evaluation suites; known citation-hallucination results in legal settings and their consequences; distinguish our provision-level *screening with mandatory grounding* from open-ended legal QA.]

**Retrieval- and graph-augmented generation.** [GraphRAG literature; hybrid lexical+graph retrieval; tool-use/agentic patterns. Our contribution is not a new retrieval algorithm but the *closed-world citation constraint*: the graph is simultaneously retrieval substrate, citation validator and provenance anchor.]

**Computational consumer protection.** [Dark-pattern detection at scale (Mathur et al.); automated UCPD/GDPR compliance checking (e.g. Claudette-style unfair-terms work); environmental-claim datasets; influencer-disclosure detection. Position: prior work targets single practices or single instruments with bespoke classifiers; we target the multi-instrument routing + provision-level finding problem, with a legally reviewable output format.]

**Human-in-the-loop evaluation and self-improvement.** [LLM-as-judge and its failure modes; constitutional/rule-based steering; benchmark contamination. Our loop differs in that *rules are human-approved artifacts distilled from adjudicated errors*, versioned and inspectable, rather than opaque model self-critique.]

## 3. System

### 3.1 Legal knowledge graph

The corpus is a curated graph of the four regulations: regulation nodes, provision nodes (36 at time of writing: articles and Annex I items with summarised obligations, severity hints and retrieval keywords) and marketing-concept nodes (16: e.g. *urgency and scarcity claims*, *hidden advertising*, *deep fakes*), connected by CONTAINS, GOVERNED_BY, REFERENCES and RELATED_TO edges (117 edges). Concept nodes function as the bridge between campaign language and legal language: a countdown timer in the campaign matches the *urgency and scarcity* concept lexically, whose GOVERNED_BY edges lead to UCPD Annex I point 7 and related provisions.

Each provision carries its CELEX number; European Legislation Identifiers (ELI) and article-anchored EUR-Lex links are derived mechanically, and document metadata is verified at display time against the Publications Office CELLAR SPARQL endpoint. Analyses never depend on CELLAR availability; anchoring is a provenance property of the report. A semi-automatic ingestion pipeline (CELLAR fetch → article segmentation → LLM-assisted summarisation → human-reviewed proposal merge) extends the corpus to further acts.

### 3.2 Agentic analysis pipeline

A campaign (title, free-text brief, channels, audience, markets, AI/personalisation flags, optional provenance URL) is processed in three stages, all streamed live to the user:

1. **Triage.** A supervisor agent characterises the campaign (detected practices, audience signals, AI/personal-data involvement) and routes the plausibly engaged regulations. Routing is deliberately inclusive — the cost asymmetry between a wasted specialist run and an unexamined violation dictates it.
2. **Specialist agents.** One agent per routed regulation investigates in a tool-use loop over three read-only graph tools (hybrid BM25+graph search, 1-hop expansion, provision fetch), then submits a structured verdict through a forced tool call: status, notes, and findings each carrying provision id, severity (5-point scale anchored to legal categories: *critical* = blacklisted practice present, …), rationale, verbatim evidence quote and remediation. **Citation validation** then drops any finding whose provision id does not exist in the graph, is not a provision node, or belongs to another regulation — hallucinated anchors cannot reach the report.
3. **Synthesis.** A final agent merges verdicts into an overall risk level, executive summary and prioritised remediation plan.

Two engineering properties matter for enforcement use: a deterministic *retrieval-only fallback* runs when no model credentials are configured (and doubles as an ablation baseline), and scraped third-party content is wrapped as *material under analysis — data, never instructions* to resist prompt injection from surveilled content.

### 3.3 Surveillance ingestion

Beyond self-submission, a surveillance mode retrieves public marketing content: YouTube search and direct-URL analysis via a commercial scraping API, assembling title, channel, description and spoken transcript (with a preferred-language → source-default → English fallback chain) into a campaign submission with recorded provenance. This shifts the system from an advertiser self-check tool to an authority-side screening instrument. [Screenshot figure: analysis report with provenance line and EUR-Lex-anchored findings.]

## 4. Benchmark

### 4.1 Design

The gold set contains N=20 cases (grown continuously; numbers to be updated for camera-ready) in three tiers: **T1** enforcement-inspired (rewritten from the fact patterns of ASA rulings, CPC sweep findings and DPA decisions — rewriting avoids licensing issues and verbatim training-data leakage), **T2** dataset-adapted (from public research corpora: dark patterns at scale, environmental claims, deceptive ads, fake reviews), and **T3** synthetic — including three *compliant controls* and a *true-scarcity near-miss* whose urgency language is factually accurate, probing over-enforcement.

Each case pairs a campaign with gold labels: regulations triage **must route**; provision ids findings **must cite** (must-finds); *acceptable extras* — defensible citations that are neither required nor penalised, absorbing legitimate legal ambiguity into an explicit annotation category rather than noise; a minimum overall risk; and the compliant flag. All provision ids are validated against the knowledge graph, and must-finds must belong to routed regulations.

### 4.2 Metrics

Per run we score: **gold-provision recall** (a must-find counts at any severity); **unexpected actionable findings** (severity ≥ medium outside must-finds ∪ extras) reported per case rather than averaged away, since each is either an engine error or a gold-label gap; **false positives on compliant controls**; **risk calibration** (overall risk ≥ gold minimum; controls must come back clean); **routing recall** (missed routings only — over-routing is by design); and, across repeated runs, **stability** (mean pairwise Jaccard of finding sets).

### 4.3 Review tooling

Label quality is the bottleneck, so review is first-class in the deployed application: a benchmark UI lists cases with their labels, provision pickers populated from the graph (invalid ids are unrepresentable), one-click promotion between must-find and extra, per-case test runs against the live engine with a gold-vs-outcome comparison, and persisted run outcomes. For every disputed citation the reviewer sees the engine's own rationale and evidence quote, and can request a **second opinion**: an independent, deliberately adversarial adjudicator prompt tests the citation on three questions — *scope* (does the provision govern the conduct?), *addressee* (does the obligation bind the campaign's operator, e.g. platform duties vs advertisers?) and *support* (is there concrete textual basis?) — returning must-find / acceptable-extra / reject with reasoning. The adjudicator is an aid, not an authority: nothing enters the gold labels without a human click, and we discuss its shared-blind-spot risk in Section 7.

[Figure: review card with engine justification, adjudication verdict and one-click accept actions.]

## 5. Calibration: learning from reviewed mistakes

Model weights are fixed; learning happens at the prompt layer through **calibration rules** — short, general legal principles injected into the specialist agents' system prompts (globally or per regulation). Rules originate two ways: written directly by the reviewer, or **distilled**: a proposer model receives the corpus of benchmark deviations (over-citations with adjudication verdicts, missed must-finds, control false positives) and drafts at most five candidate rules for *recurring* patterns, under hard constraints — general principles only; no case ids, brand names or campaign facts; no duplication of existing rules. Every proposal requires explicit human approval; the approved rule set is a versioned, human-readable artifact (e.g., from our deployment: *"DSA platform obligations (Arts. 25, 26, 28) are addressed to providers of online platforms, not to advertisers whose campaigns merely run on a platform"*).

**Contamination discipline.** A benchmark the engine learns from can no longer measure what it taught. We keep the loop honest by (i) the generality constraint above — rules must transfer to unseen campaigns, memorised answers are prohibited and auditable since rules are plain text; (ii) growing the set and designating held-out cases that never feed rule distillation; and (iii) reporting before/after scorecards for every calibration change, so claimed improvements are attributable and reversible.

## 6. Evaluation

### 6.1 Protocol

We evaluate four configurations on the benchmark: **(A)** retrieval-only heuristic (no LLM); **(B)** agentic engine without graph-citation validation [ablation implemented for the experiment]; **(C)** agentic engine with validation (deployed default); **(D)** C + approved calibration rules. Each configuration runs every case k=3 times ([model], temperature/config fixed; runs via the released harness). We report the Section 4.2 metrics with per-tier breakdowns, stability, and cost/latency per case. Annotation quality: a second legal annotator labels [all / a stratified subset of] cases independently; we report inter-annotator agreement (Cohen's κ on routing and risk; F1 overlap on provision sets) and adjudicate disagreements before final runs.

### 6.2 Results

[TODO — table skeleton:]

| Configuration | Provision recall | Unexpected/case | FP on controls | Risk calib. | Stability | Cost/case |
|---|---|---|---|---|---|---|
| A retrieval-only | 0.73* | 5.6* | 3/3* | … | 1.00* | ~0 |
| B agentic, no validation | | | | | | |
| C agentic + validation | | | | | | |
| D C + calibration | | | | | | |

\*Preliminary numbers from the development deployment, to be re-run under the final protocol. The retrieval-only baseline illustrates the design space's floor: near-total recall pathology-free but with an unusable false-positive profile (all compliant controls flagged; ~5.6 unexpected findings per case).

**Qualitative error analysis.** [To include: the DSA-addressee confusion as the dominant pre-calibration error family; specificity errors (general clauses stacked on blacklist items); before/after evidence that the two seed calibration rules eliminate the family without recall loss; representative adjudicator transcripts.]

### 6.3 Threats to validity

Single-expert gold labels (mitigated by the second annotator and the published labels inviting scrutiny); benchmark scale; adjudicator and engine sharing a base model (shared blind spots — the adversarial framing mitigates but does not eliminate); synthetic and rewritten campaigns rather than raw enforcement files (a deliberate privacy/licensing choice); one model family evaluated [extend if feasible].

## 7. Discussion and limitations

The system is a *screening prioritiser*, not an assessor: its output ranks material for qualified human review, and every design choice (provision anchoring, verbatim evidence quotes, EUR-Lex links, explicit engine labelling) serves reviewability rather than autonomy. Legal limitations bound its competence: it sees only the submitted text, not the factual truth of claims (the true-scarcity control probes exactly this boundary); severity is a triage heuristic, not a sanction gradation; and the four-instrument scope, while covering the marketing core, omits sectoral rules (the ingestion pipeline and the promotion path from graph context to a fifth specialist are the designed extension route). The calibration loop's central open question is longitudinal: whether rule accumulation remains monotonic as the rule set grows, or begins to interact (rule conflicts, prompt dilution) — the versioned rule corpus makes this measurable.

## 8. Ethical and deployment considerations

Screening public marketing content is processing at arm's length from individuals; nevertheless the deployment analyses trader conduct, not consumer data, stores reports on infrastructure under the authority's control, and sends campaign text only to the configured model endpoint [deployment details]. False positives carry a chilling-effect risk if screening output leaks into public accusations — hence the persistent indicative-not-probative framing in every report and export. Scraped content is treated as untrusted data to resist adversarial injection by surveilled parties. The benchmark's enforcement-inspired tier is rewritten, not reproduced. [Internal clearance items: institutional disclaimer, model-dependency disclosure, author/reviewer overlap statement.]

## 9. Conclusion

We presented a deployed, graph-grounded agentic screening system for EU marketing-law compliance and — as the primary contribution — a regulator-in-the-loop methodology that turns a single expert's review effort into three compounding artifacts: a gold benchmark, an adjudicated error corpus, and a versioned set of general calibration rules that measurably improve the engine while explicit contamination discipline preserves the benchmark as measurement. The pattern is not specific to marketing law: any provision-anchored screening domain (financial promotions, food claims, medicinal advertising) could instantiate it. We release the benchmark, graph and calibration corpus to invite exactly the scrutiny the domain demands.

---

## Appendices (planned)

- **A.** Benchmark case format and full gold set
- **B.** Agent prompts (triage, specialist, synthesis, adjudicator, lesson proposer) and tool schemas
- **C.** Calibration rule corpus with provenance
- **D.** Scorecards for all configurations; harness usage
- **E.** Knowledge-graph statistics and CELLAR/ELI anchoring details

## References

[To be populated — key anchors: UCPD 2005/29/EC; GDPR 2016/679; DSA 2022/2065; AI Act 2024/1689; Commission UCPD Guidance (2021); CPC sweep reports (dark patterns 2023, influencers 2024, green claims); Mathur et al., Dark Patterns at Scale, CSCW 2019; Stammbach et al., Environmental Claims, 2022; Zeng et al., Bad Ads, 2021; Lippi et al., CLAUDETTE, AI & Law 2019; Guha et al., LegalBench, 2023; LLM legal-hallucination studies (Dahl et al., 2024); GraphRAG (Edge et al., 2024); constitutional AI / rule-based steering; LLM-as-judge critiques.]
