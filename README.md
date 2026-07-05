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
| Agents     | Anthropic Python SDK, Claude (default `claude-opus-4-8`), parallel tool-use loops |
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
   | `CLAUDE_MODEL` | Optional; default `claude-opus-4-8`. |

   **Option B — Claude on Amazon Bedrock (bearer token / Bedrock API key):**

   | Variable | Description |
   |---|---|
   | `AWS_BEARER_TOKEN_BEDROCK` | Your Bedrock API key (bearer token). |
   | `AWS_REGION` | e.g. `eu-west-1`. |
   | `ANTHROPIC_MODEL` (or `CLAUDE_MODEL`) | Bedrock model / inference-profile id, e.g. `eu.anthropic.claude-opus-4-8` (the default in Bedrock mode). |

   The provider is auto-detected from which credentials are present
   (`ANTHROPIC_API_KEY` wins if both are set; override with `CLAUDE_PROVIDER=anthropic|bedrock`).
   Standard AWS SigV4 credentials (`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`) also work for Bedrock.
   With no credentials at all the app runs in heuristic (retrieval-only) mode.

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

## Extending the knowledge graph

The legal corpus lives in `knowledge/nodes.json` (regulations, provisions, marketing concepts)
and `knowledge/edges.json` (containment, governance, cross-references). Add nodes/edges and
restart — the retriever indexes them automatically and agents can cite them immediately.
Suitable next steps: ePrivacy Directive, Empowering Consumers Directive (EU) 2024/825 blacklist
items, Health Claims Regulation, national transpositions.

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
