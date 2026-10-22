# Marketing Compliance Checker

A decision-support system that screens digital marketing campaigns against four EU legal
frameworks — the **AI Act** (Regulation (EU) 2024/1689), the **GDPR** (Regulation (EU) 2016/679),
the **DSA** (Regulation (EU) 2022/2065) and the **UCPD** (Directive 2005/29/EC) — using
**GraphRAG** over a curated legal knowledge graph and an **agentic** analysis pipeline built on
the Claude API. Deployable on **Railway** as a single service.

> ⚠️ **This is a screening prioritiser, not a legal assessor.** Its output ranks material for
> review by qualified people. It is indicative screening, not legal advice, and a campaign it
> reports as raising no concern is *not* thereby compliant — see
> [Scope and limitations](#scope-and-limitations).

## Author

**Manolis Maragoudakis** — author, owner and maintainer of this repository
(Department of Informatics, Ionian University, Corfu, Greece · mmarag@ionio.gr), and co-author
of the accompanying article.

## Research paper

This repository is the artifact accompanying:

> Kaponis, A.; Maragoudakis, M. **Regulator-in-the-Loop Compliance Screening: Graph-Grounded
> LLM Agents with a Continuously Calibrated Benchmark for EU Marketing Law.** *Multimedia*
> (MDPI), 2026. Accepted 20 October 2026; in production.

The DOI and article number are assigned at publication — update `CITATION.cff` and this section
once they are issued. Everything the paper reports is reproducible from this repository: the
frozen benchmark, the held-out split, the approved calibration rules, the agent prompts, the
evaluation harness, and the archived result artifacts for every configuration in Table 1.

## How it works

```
                            ┌──────────────────────────────────────────────┐
 Campaign text ──POST──►    │  FastAPI backend                             │
                            │                                              │
   Angular 21 + eUI 21      │  1. Triage agent (Claude, forced tool call)  │
   ◄──SSE progress────      │       └─ decides which regulations apply    │
                            │  2. Specialist agents — run in parallel      │
                            │       AI Act │ GDPR │ DSA │ UCPD             │
                            │       each is a Claude tool-use loop with    │
                            │       GraphRAG tools over the knowledge      │
                            │       graph (search / expand / get node)     │
                            │  3. Synthesis agent → risk level, executive  │
                            │     summary, prioritised remediation plan    │
                            └───────────────┬──────────────────────────────┘
                                            │
                             Knowledge graph (60 nodes / 132 edges):
                             4 regulations · 40 provisions · 16 marketing concepts,
                             edges: CONTAINS · GOVERNED_BY · REFERENCES · RELATED_TO
```

**Closed-world citation.** A specialist agent may only cite a provision it has actually
retrieved from the graph, and citations outside the agent's own regulation are dropped by a
post-hoc validation step. This is the system's central design claim: hallucination resistance
is a property of the architecture rather than of the model — see
[Evaluation](#evaluation-results) for the evidence.

**GraphRAG retrieval** is hybrid: BM25 lexical scoring finds entry nodes, then results are
expanded one hop through the graph — so a query about "countdown timers" surfaces UCPD Annex I
point 7 directly *and*, via graph edges, the DSA dark-pattern prohibition and the UCPD
aggressive-practices rules. Every finding carries the graph path that produced it.

**Agent progress streams live** to the UI over Server-Sent Events: triage result, per-agent
status, each graph tool call, and the final consolidated report.

**No API key? Heuristic mode.** Without model credentials the system still runs end-to-end
using deterministic GraphRAG retrieval (clearly labelled in the UI) — useful for demos and CI,
and reported as configuration A in the paper.

## Evaluation results

Headline rows from the paper's Table 1, all reproducible from `bench/results/`. The benchmark
is 52 campaigns with 97 must-find provisions and 7 compliant controls; 15 campaigns are held
out from calibration-rule distillation. Three runs per campaign for A–D, two for E.

| Configuration | n | Provision recall ↑ | Unexpected/case ↓ | Control FP ↓ | Invalid citations ↓ |
|---|---|---|---|---|---|
| A — retrieval only, no LLM | 52 | 0.515 | 5.83 | 7/7 | 0 |
| B — agentic, no citation validation | 52 | 1.000 | 2.96 | 1/7 | 1 |
| **C — agentic, deployed default** | 52 | **0.979** | 3.12 | 1/7 | 0 |
| E1 — single call, GPT-5.4 | 52 | 0.825 | 1.65 | 0/7 | 0 |
| E2 — single call, GPT-5.6 | 52 | 0.763 | 0.23 | 0/7 | 0 |
| E3 — single call, gpt-oss-120b | 52 | 0.608 | 2.40 | 6/7 | 0 |
| C — deployed default (holdout) | 15 | 1.000 | 2.93 | 0/2 | 0 |
| **D — C + calibration (holdout)** | 15 | **1.000** | **0.33** | 0/2 | 0 |

Two findings carry the paper:

- **Citation integrity is architectural, screening quality is not.** Across 309 scored runs on
  four models from three families — including an open-weights model that failed on every other
  metric — not one invalid citation was produced. The closed vocabulary does that work. Recall,
  by contrast, ranged from 0.608 to 0.979 and control false positives from 6/7 to 0/7.
- **Calibration transfers to unseen campaigns.** On the held-out split, human-approved rules cut
  unexpected findings from 44 to 5 (−88.6%) with recall unchanged at 1.000: 11 campaigns
  improved, none worsened (exact Wilcoxon *p* = 0.00098).

Regenerate the table and statistics from the artifacts:

```bash
python bench/make_table1.py            # Table 1 (markdown or --csv)
python bench/make_stats.py             # Wilson intervals, Wilcoxon, McNemar
```

> The published figures were produced on Claude Opus 4.8 via Amazon Bedrock. The code's default
> model has since moved to Opus 5; set `ANTHROPIC_MODEL` explicitly to reproduce the paper's
> numbers exactly.

## Stack

| Layer      | Technology |
|------------|------------|
| Frontend   | Angular 21 + **eUI 21** (`@eui/components`, `@eui/styles`) — EC look & feel |
| Backend    | Python 3.12, FastAPI, SSE streaming |
| Agents     | Anthropic Python SDK, Claude (default `claude-opus-5`), parallel tool-use loops |
| GraphRAG   | Curated legal knowledge graph (JSON) + BM25 + 1-hop graph expansion |
| Storage    | SQLite (reports); attach a Railway volume for persistence |
| Deployment | Docker multi-stage build, single Railway service |

## Quick start (local, no credentials)

The fastest way to see the system work — runs in heuristic mode, no API key, no cost:

```bash
git clone https://github.com/maragem/VA-marketSurveillance
cd VA-marketSurveillance/frontend && npm install && npx ng build
cd ../backend && pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000      # open http://localhost:8000
```

Add `ANTHROPIC_API_KEY=sk-ant-...` to the last command to enable the full agentic pipeline.

## Deploy on Railway

1. Create a new Railway project → **Deploy from GitHub repo** → select this repository.
   Railway picks up `railway.json` and builds the `Dockerfile` automatically.
2. Set environment variables on the service. Two LLM providers are supported — configure one:

   **Option A — Claude API (first-party):**

   | Variable | Description |
   |---|---|
   | `ANTHROPIC_API_KEY` | Anthropic API key. |
   | `CLAUDE_MODEL` | Optional; default `claude-opus-5`. |

   **Option B — Claude on Amazon Bedrock (bearer token / Bedrock API key):**

   | Variable | Description |
   |---|---|
   | `AWS_BEARER_TOKEN_BEDROCK` | Your Bedrock API key (bearer token). |
   | `AWS_REGION` | e.g. `eu-west-1`. |
   | `ANTHROPIC_MODEL` (or `CLAUDE_MODEL`) | Bedrock model / inference-profile id, e.g. `eu.anthropic.claude-opus-5` (the default in Bedrock mode). |
   | `BEDROCK_ENDPOINT` | Optional: `runtime` (default — classic InvokeModel endpoint, works with plain Bedrock API keys) or `mantle` (newer Messages endpoint; the key additionally needs the `bedrock-mantle:CreateInference` IAM action). |

   The provider is auto-detected from which credentials are present
   (`ANTHROPIC_API_KEY` wins if both are set; override with `CLAUDE_PROVIDER=anthropic|bedrock`).
   Standard AWS SigV4 credentials (`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`) also work for Bedrock.
   With no credentials at all the app runs in heuristic (retrieval-only) mode.

   **Optional — YouTube surveillance (Oxylabs Web Scraper API):**

   | Variable | Description |
   |---|---|
   | `OXYLABS_USERNAME` / `OXYLABS_PASSWORD` | Oxylabs credentials. When set, the "YouTube" page lets users search YouTube (`youtube_search`), pull a video's metadata + transcript (`youtube_metadata`, `youtube_transcript`) and run it through the compliance analysis, with the video URL kept as provenance in the report and PDF. Without them the page shows a "not configured" notice. |

   **Common:**

   | Variable | Description |
   |---|---|
   | `AGENT_MAX_TURNS` | Tool-use round trips per specialist agent (default 8). |
   | `DATA_DIR` | Report storage dir, default `/app/data`. |
   | `EXPERIMENT_SKIP_CITATION_VALIDATION` | **Research only.** `1` disables post-hoc citation validation (the paper's configuration B). Never set on a production deployment. |

3. (Optional) Attach a **volume** mounted at `/app/data` so analysis reports, benchmark edits,
   calibration rules and experiment jobs survive redeploys.
4. Generate a domain — done. Health check: `GET /api/health`.

## Local development

```bash
# Backend (serves the API; also serves the frontend if it has been built)
cd backend
pip install -r requirements.txt
ANTHROPIC_API_KEY=sk-ant-... python -m uvicorn app.main:app --reload --port 8000

# Frontend (dev server with /api proxy to :8000)
cd frontend
npm install
npm start          # http://localhost:4200

# Or build the whole thing like production:
cd frontend && npx ng build && cd ../backend && python -m uvicorn app.main:app
```

## Pages in the app

| Page | What it does |
|---|---|
| **New analysis** | Submit a campaign; watch triage, specialists and synthesis stream live |
| **Dashboard / Analytics** | Stored reports, risk distribution, findings by regulation and channel |
| **YouTube** | Search or fetch a video, assemble its text, and screen it (needs Oxylabs) |
| **Knowledge graph** | Explore provisions, concepts and edges |
| **Benchmark** | Review and edit gold labels, run single cases, adjudicate deviations, manage calibration rules |
| **Experiments** | Run whole evaluation configurations (A–D) as server-side jobs |
| **Help** | Built-in user manual |

## API

| Endpoint | Description |
|---|---|
| `POST /api/analyses/stream` | Submit a campaign, receive SSE progress events, final event carries the report |
| `GET /api/analyses` | List past analyses |
| `GET /api/analyses/{id}` | Fetch a stored report |
| `PATCH /api/analyses/{id}` | Rename an analysis |
| `GET /api/analyses/{id}/pdf` | Download the report as PDF |
| `GET /api/graph/summary` · `/graph/full` | Knowledge-graph statistics and full projection |
| `GET /api/graph/search?q=…` | Direct GraphRAG hybrid search (debug/exploration) |
| `GET /api/graph/nodes/{id}` | Node detail + neighbours |
| `GET /api/cellar/{celex}` | Live CELLAR metadata lookup (display aid) |
| `GET/POST/PUT/DELETE /api/bench/cases…` | Gold-label CRUD, export, per-case runs, adjudication |
| `GET /api/calibration` · `POST /api/calibration/rules` | Approved calibration rules |
| `GET /api/experiments/configs` · `POST /api/experiments/jobs` | Evaluation configurations and jobs |
| `GET /api/experiments/jobs/{id}/{scorecard,results,reports}` | Download a job's artifacts |
| `GET /api/health` | Health + configuration status |

## CELLAR / EUR-Lex source anchoring

Every regulation and provision node in the knowledge graph is anchored to the authoritative EU
corpus maintained by the Publications Office in the **CELLAR** common repository:

- **CELEX** number (e.g. AI Act = `32024R1689`, GDPR = `32016R0679`, DSA = `32022R2065`,
  UCPD = `32005L0029`)
- **ELI** (European Legislation Identifier, e.g. `http://data.europa.eu/eli/reg/2024/1689/oj`)
- **CELLAR resource URI** (`http://publications.europa.eu/resource/celex/{CELEX}`)
- A deep **EUR-Lex link** with an article/annex anchor where derivable (e.g. `…CELEX:32024R1689#art_5`)

These identifiers flow through the whole pipeline: graph nodes expose them to the agents through
the GraphRAG tools, every finding in a report carries its `celex` and `source_url`, and the UI
renders an "Official text" link next to each finding. `GET /api/cellar/{celex}` additionally
queries the CELLAR SPARQL endpoint (`publications.europa.eu/webapi/rdf/sparql`) live for document
metadata (official title, date, CELLAR work URI) with caching — purely a display/verification aid
that degrades gracefully (`available: false`) if CELLAR is unreachable, so the analysis itself
never depends on external availability.

## Extending the knowledge graph

**Manually:** the legal corpus lives in `knowledge/nodes.json` (regulations, provisions,
marketing concepts) and `knowledge/edges.json` (containment, governance, cross-references).
Add nodes/edges and restart — the retriever indexes them automatically and agents can cite
them immediately.

**Semi-automatically — CELLAR ingestion pipeline:** `python -m app.ingest` (run from
`backend/`) fetches any act from CELLAR by CELEX number, splits it into articles, and drafts
graph nodes/edges into a **proposal file** for human review; `--merge` folds an approved
proposal into the live graph. Ingested acts automatically receive derived ELI identifiers and
EUR-Lex deep links.

```bash
# Draft the ePrivacy Directive, LLM-enriched (marketing-relevance summaries,
# retrieval keywords, links to existing concepts), keeping only relevant articles
python -m app.ingest --celex 32002L0058 --regulation EPRIVACY \
    --label "ePrivacy Directive 2002/58/EC" --llm --relevant-only

# Add further GDPR articles to the existing corpus (plain text, no LLM)
python -m app.ingest --celex 32016R0679 --regulation GDPR \
    --label "GDPR (Regulation (EU) 2016/679)" --articles 15,17,20

# Review knowledge/proposals/proposal-<CELEX>.json, then:
python -m app.ingest --merge knowledge/proposals/proposal-32002L0058.json
# ...and restart the backend to index the new nodes.
```

Flags: `--articles 1-15` / `--articles 5,9,22` selects articles; `--llm` uses the configured
Claude provider (Anthropic API or Bedrock) to summarise each article and propose concept
links; `--relevant-only` drops articles the model judges not marketing-relevant (committees,
entry into force, …); `--from-file act.html` works offline from saved HTML.

Note: the four **core regulations** (AI Act, GDPR, DSA, UCPD) each have a dedicated specialist
agent and can appear in findings. Ingested acts enrich the graph — they surface through
GraphRAG retrieval and graph traversal as context for the agents — but findings always cite
core-regulation provisions. Promoting an ingested act to a fifth specialist agent is a small
code change (`config.REGULATIONS`, the `Regulation` literal in `models.py`, and labels).

Suitable candidates: ePrivacy Directive, Empowering Consumers Directive (EU) 2024/825
blacklist items, Health Claims Regulation (EC) 1924/2006, national transpositions.

## Benchmark and calibration

`bench/` holds the versioned gold set — **52 campaigns** (19 enforcement-inspired, 17
dataset-adapted, 16 synthetic), **97 must-find provisions**, **7 compliant controls**, with
**15 campaigns held out** (`bench/holdout.json`) from calibration-rule distillation — plus a
harness that replays it against a running instance:

```bash
python bench/run.py --base-url http://localhost:8000 --runs 3
python bench/run.py --base-url http://localhost:8000 --runs 3 --holdout
python bench/run.py --rescore bench/results/<job>-reports.jsonl   # re-score after relabelling
```

See `bench/README.md` for the case format, the gold-label review workflow, and metric
definitions. The **Benchmark** page in the app provides the review UI: graph-validated
provision pickers, per-case runs with a gold-vs-outcome comparison, an adversarial
"second opinion" adjudicator for disputed citations, and export of the corrected
`cases.jsonl`.

**Engine calibration** (`knowledge/calibration.json`) closes the loop: human-approved rules —
general legal principles distilled from review deviations, e.g. *DSA platform duties do not bind
advertisers whose campaigns merely run on a platform* — are injected into the specialist agents'
prompts on every analysis. The Benchmark page drafts candidates from stored deviations and
manages approvals. To keep the benchmark an honest measurement, rules must never encode
case-specific answers, and the held-out split must stay out of rule distillation.

## Reproducing the evaluation

The **Experiments** page runs whole configurations as server-side jobs that checkpoint every
completed analysis to the data volume and resume automatically after a restart, so a run
survives closing the browser:

| Config | What it isolates |
|---|---|
| A | GraphRAG retrieval alone (no LLM) |
| B | Full pipeline with citation validation disabled |
| C | The deployed pipeline, no calibration (full set and holdout) |
| D | C plus the approved calibration rules, on the holdout |

Configuration E (external models through a chat interface, where no API is available) is run
manually from a generated workbook and scored by the same code:

```bash
python bench/make_gptec_workbook.py                       # build the workbook
python bench/score_gptec_workbook.py <filled>.xlsx --sheet "Run sheet"
```

Every job writes `scorecard.md`, `results.json` and `reports.jsonl` into `bench/results/`;
all configurations reported in the paper are committed there.

## Scope and limitations

- **Four EU-level instruments only.** National transpositions of the UCPD, sector-specific
  advertising rules (medicinal products, financial promotions, food and health claims,
  audiovisual media services) and Member State supervisory practice are outside the graph. A
  campaign screened as raising no concern here is **not** thereby compliant in any Member State.
- **Text, not pixels.** The engine reasons over textual, contextual and provenance
  representations — including spoken transcripts for retrieved video — not over image frames or
  audio signals. Violations carried solely in the visual or audio channel (an illegible on-screen
  disclaimer, a superimposed claim absent from the transcript) are outside its present reach.
- **Synthetic benchmark.** Tier-1 campaigns are inspired by real enforcement actions, but all 52
  are synthetic reconstructions, not sampled live advertising.
- **Single-annotator gold labels.** Reviewed by one domain expert; inter-annotator agreement is
  not yet measured. Contributions here are especially welcome (see below).
- **Screening, not adjudication.** Every design choice — provision anchoring, verbatim evidence
  quotes, EUR-Lex links, explicit engine labelling — serves reviewability by a qualified human,
  not autonomy.

## Repository layout

```
backend/app/
  graphrag/          # knowledge graph + hybrid BM25/graph retriever
  agents/            # triage → parallel specialists → synthesis (+ heuristic fallback)
  api/routes.py      # REST + SSE endpoints
  bench.py           # gold-label store, adjudicator, summary scoring
  calibration.py     # approved calibration rules, lesson proposer
  experiments.py     # server-side evaluation job runner (configurations A–D)
  store.py           # SQLite report store
knowledge/           # curated legal knowledge graph + calibration.json
bench/
  cases.jsonl        # the frozen 52-campaign gold set
  holdout.json       # the 15 held-out campaign ids
  run.py             # CLI harness (--runs, --holdout, --rescore)
  make_table1.py     # regenerates the paper's Table 1 from artifacts
  make_stats.py      # intervals and significance tests
  results/           # archived scorecards, per-case results and raw outputs
docs/paper/          # results narrative, Table 1, runbook, Colab notebook
frontend/            # Angular 21 + eUI 21 SPA
Dockerfile           # multi-stage: Angular build → Python runtime
railway.json         # Railway service configuration
```

## Contributing

The most useful contributions, in rough order of value to the research:

1. **A second annotation pass on the gold labels** — the largest open threat to validity. The
   protocol is specified in `docs/paper/table1-runbook.md` §9, and because every raw engine
   output is archived, revised labels are applied by re-scoring at no inference cost.
2. **New benchmark campaigns**, especially multi-instrument and platform-side cases; the
   held-out split currently has no recall headroom left to measure.
3. **Multimodal evidence extraction** — passing image frames or audio to the specialists. The
   citation mechanism is modality-independent, so this is an ingestion change, not a redesign.
4. **Additional instruments** via the CELLAR ingestion pipeline.

Please keep gold-label changes and engine changes in separate commits, and never add a
calibration rule that encodes a case-specific answer.

## Licence

Copyright © 2026 Manolis Maragoudakis.

Licensed under the **European Union Public Licence v. 1.2** (EUPL-1.2). You may not use this
work except in compliance with the Licence; the full text is in [`LICENSE`](LICENSE) and the
official multilingual versions are published by the European Commission on
[Joinup](https://joinup.ec.europa.eu/collection/eupl/eupl-text-eupl-12).

The EUPL is a copyleft licence: if you distribute the work or a derivative, or make it
available to the public as a network service, you must do so under the EUPL (or one of the
compatible licences listed in its Appendix) and make the source code available. It is
compatible with the GPL, AGPL, MPL, LGPL, EPL, CeCILL and the other licences named there, so
EUPL-licensed code can be combined with projects under those terms.

Note that the knowledge graph in `knowledge/` reproduces short summaries of EU legislation;
the underlying legal texts are published by the Publications Office of the European Union and
are not covered by this licence. The accompanying article is published open access under CC BY.

## Disclaimer

Developed in a personal/research capacity. The views expressed are those of the authors and may
not in any circumstances be regarded as stating an official position of the European Commission.
Outputs are indicative screening for human review and do not constitute legal advice.
