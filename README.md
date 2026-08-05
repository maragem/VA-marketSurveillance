# Marketing Compliance Checker

A decision-support system that helps marketers screen campaign texts against four EU legal
frameworks — the **AI Act** (Regulation (EU) 2024/1689), the **GDPR** (Regulation (EU) 2016/679),
the **DSA** (Regulation (EU) 2022/2065) and the **UCPD** (Directive 2005/29/EC) — using
**GraphRAG** over a curated legal knowledge graph and an **agentic** analysis pipeline built on
the Claude API. Deployable on **Railway** as a single service.

> ⚠️ Results are indicative screening, not legal advice.

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
                             Knowledge graph (56 nodes / 117 edges):
                             provisions + cross-cutting marketing concepts,
                             edges: CONTAINS · GOVERNED_BY · REFERENCES · RELATED_TO
```

**GraphRAG retrieval** is hybrid: BM25 lexical scoring finds entry nodes, then results are
expanded one hop through the graph — so a query about "countdown timers" surfaces UCPD Annex I
point 7 directly *and*, via graph edges, the DSA dark-pattern prohibition and the UCPD
aggressive-practices rules. Every finding carries the graph path that produced it, and agent
citations are validated against the graph (hallucinated provision ids are dropped).

**Agent progress streams live** to the UI over Server-Sent Events: triage result, per-agent
status, each graph tool call, and the final consolidated report.

**No API key? Heuristic mode.** Without `ANTHROPIC_API_KEY` the system still runs end-to-end
using deterministic GraphRAG retrieval (clearly labelled in the UI) — useful for demos and CI.

## Stack

| Layer      | Technology |
|------------|------------|
| Frontend   | Angular 21 + **eUI 21** (`@eui/components`, `@eui/styles`) — EC look & feel |
| Backend    | Python 3.12, FastAPI, SSE streaming |
| Agents     | Anthropic Python SDK, Claude (default `claude-opus-5`), parallel tool-use loops |
| GraphRAG   | Curated legal knowledge graph (JSON) + BM25 + 1-hop graph expansion |
| Storage    | SQLite (reports); attach a Railway volume for persistence |
| Deployment | Docker multi-stage build, single Railway service |

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

3. (Optional) Attach a **volume** mounted at `/app/data` so analysis reports survive redeploys.
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

## API

| Endpoint | Description |
|---|---|
| `POST /api/analyses/stream` | Submit a campaign, receive SSE progress events, final event carries the report |
| `GET /api/analyses` | List past analyses |
| `GET /api/analyses/{id}` | Fetch a stored report |
| `GET /api/graph/summary` | Knowledge-graph statistics |
| `GET /api/graph/search?q=…` | Direct GraphRAG hybrid search (debug/exploration) |
| `GET /api/graph/nodes/{id}` | Node detail + neighbours |
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

## Benchmarking the engine

`bench/` contains a versioned gold-standard test set (20 cases: enforcement-inspired,
dataset-adapted, and synthetic controls) and a harness that replays it against a running
instance, scoring triage routing, provision-level recall/precision, false positives on
compliant campaigns, risk calibration, and run-to-run stability:

```bash
python bench/run.py --base-url https://<your-app>.up.railway.app --runs 3
```

See `bench/README.md` for the case format, the gold-label review workflow, and metric
definitions. Run it after any prompt, graph, or model change. The **Benchmark** page in
the app provides a review UI for the gold labels: edit cases with graph-validated
provision pickers, run cases against the live engine with a gold-vs-outcome comparison,
then export the corrected `cases.jsonl` to commit back.

The benchmark also feeds **engine calibration** (`knowledge/calibration.json`): human-approved
rules — general legal principles distilled from review deviations, e.g. DSA platform duties
don't bind advertisers — are injected into the specialist agents' prompts on every analysis.
The Benchmark page manages the rules ("Propose lessons from benchmark" drafts candidates from
stored deviations; you approve or dismiss) and exports the file for committing. To keep the
benchmark an honest measurement, rules must never encode case-specific answers.

## Repository layout

```
backend/app/
  graphrag/        # knowledge graph + hybrid BM25/graph retriever
  agents/          # triage → parallel specialists → synthesis (+ heuristic fallback)
  api/routes.py    # REST + SSE endpoints
  store.py         # SQLite report store
knowledge/         # curated legal knowledge graph (nodes.json / edges.json)
frontend/          # Angular 21 + eUI 21 SPA
Dockerfile         # multi-stage: Angular build → Python runtime
railway.json       # Railway service configuration
```
