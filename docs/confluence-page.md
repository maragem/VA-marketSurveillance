# Marketing Compliance Checker — Architecture & User Guide

> **Status:** Pilot · **Deployment:** Railway (single service) · **Repository:** `maragem/VA-marketSurveillance` · **Audience:** market-surveillance officers, policy/legal colleagues, marketers submitting campaigns

---

## 1. Aim

The **Marketing Compliance Checker** is a decision-support system that screens marketing campaigns — submitted as text or discovered in the wild — against four EU legal frameworks:

| Framework | Instrument | Marketing-relevant scope |
|---|---|---|
| **AI Act** | Regulation (EU) 2024/1689 | Prohibited manipulative/exploitative AI practices (Art. 5); transparency for chatbots, synthetic content and deep fakes (Art. 50) |
| **GDPR** | Regulation (EU) 2016/679 | Lawful basis, consent quality, profiling, special-category data, children's data, direct-marketing objection rights |
| **DSA** | Regulation (EU) 2022/2065 | Dark patterns (Art. 25), advertising transparency (Art. 26), ban on sensitive-data ad profiling (Art. 26(3)), protection of minors (Art. 28) |
| **UCPD** | Directive 2005/29/EC (incl. Omnibus amendments) | Misleading actions/omissions, aggressive practices, the Annex I blacklist (false urgency, fake reviews, advertorials, "free" traps, child exhortation, …) |

The tool serves **two complementary purposes**:

1. **Preventive (self-service):** marketers check a campaign *before* it launches, receive grounded findings with concrete remediation steps, fix the campaign, and re-run the analysis to demonstrate the issues were addressed.
2. **Market surveillance (active):** surveillance officers search **YouTube** for marketing content already in circulation, pull a video's metadata and transcript, and run the same analysis — turning the tool into a triage instrument that ranks observed practices by regulatory risk and produces citable, exportable evidence for follow-up.

### What the tool is — and is not

The output is **indicative screening, not legal advice**. Every report carries this disclaimer. Findings on scraped content are explicitly framed as *indicators for investigation, not proof of infringement*: the system assesses the observable claims and mechanics of a campaign; it cannot verify whether a claim is factually false, how an ad was targeted, or whether a commercial relationship exists behind an undisclosed endorsement. Those questions remain with the human investigator — the tool's job is to make sure they look at the right campaigns first, with the right provisions already on the table.

---

## 2. Why it matters for market surveillance & EU compliance

**Grounded in the authoritative EU corpus.** Every legal reference in the system is anchored to the Publications Office **CELLAR** repository: each provision carries its **CELEX** number, **ELI** identifier and a deep link to the official text on EUR-Lex. Reports resolve their cited acts against the CELLAR SPARQL endpoint live ("verified in CELLAR" badge) and every finding links to the official article. Nothing is cited from the model's memory — an agent can only cite a provision it has retrieved from the curated knowledge graph, and hallucinated citations are dropped by validation.

**Explainable by construction.** Findings are not black-box scores. Each one shows: the provision (with official source), the severity, the reasoning, a **verbatim quote from the campaign** as evidence, a concrete recommendation, and — where retrieval crossed regulation boundaries — the knowledge-graph path that surfaced the rule (e.g. *countdown timer → urgency/scarcity concept → DSA Art. 25 dark patterns*). The knowledge-graph explorer page makes the entire legal corpus the system reasons over visible and navigable.

**An audit trail of due diligence.** Reports are persisted, exportable as branded PDFs, and linkable in remediation chains: a re-analysis documents which findings were resolved, which remain, and which are new. For scraped content, the source URL travels through the report and the PDF — the export is self-contained evidence of *what* was assessed, *when*, against *which official provisions*, and *where the material came from*.

**EU-appropriate operation.** The UI is built on **eUI**, the European Commission's design system, so it looks and behaves like an EC tool. LLM inference runs on **Claude via Amazon Bedrock using the EU cross-region inference profile** (`eu.anthropic.claude-opus-4-8`), keeping inference within EU regions; the first-party Anthropic API is supported as an alternative. Analyses are human-initiated one at a time — no unattended mass processing of scraped content.

**Extensible corpus.** The legal knowledge graph is data, not code. New instruments (ePrivacy, the Empowering Consumers Directive 2024/825 greenwashing blacklist, Health Claims Regulation) can be added by hand or semi-automatically via the **CELLAR ingestion pipeline**, which fetches an act by CELEX number, splits it into articles, drafts graph nodes (optionally LLM-summarised for marketing relevance), and writes a proposal for human review before merging.

---

## 3. Architecture

```
                 ┌─────────────────────────────────────────────────────────────┐
                 │                    Railway (single service)                  │
                 │                                                             │
 Marketer /      │  Angular 21 + eUI 21 SPA          FastAPI backend           │
 Surveillance ──►│  ┌──────────────────────┐   SSE   ┌─────────────────────┐   │
 officer         │  │ Dashboard · Analyze  │◄───────►│ Agentic pipeline    │   │
                 │  │ YouTube · Analytics  │  /api   │  1 Triage agent     │   │
                 │  │ Knowledge graph      │         │  2 4× specialist    │   │
                 │  │ Reports (+PDF)       │         │    agents (parallel)│   │
                 │  └──────────────────────┘         │  3 Synthesis agent  │   │
                 │                                   └──────┬──────────────┘   │
                 │                                          │ tool calls       │
                 │                                   ┌──────▼──────────────┐   │
                 │                                   │ GraphRAG            │   │
                 │                                   │  legal knowledge    │   │
                 │                                   │  graph + hybrid     │   │
                 │                                   │  retriever (BM25 +  │   │
                 │                                   │  1-hop expansion)   │   │
                 │                                   └─────────────────────┘   │
                 │        SQLite report store (Railway volume /app/data)       │
                 └───────────┬───────────────┬────────────────┬────────────────┘
                             │               │                │
                   Claude on AWS Bedrock   Oxylabs Web     Publications Office
                   (EU inference profile,  Scraper API     CELLAR (SPARQL +
                   or Anthropic API)       (YouTube)       content retrieval)
```

### 3.1 The legal knowledge graph (GraphRAG core)

A curated graph of **~60 nodes / ~120 edges**: the four regulations, their marketing-relevant provisions (each with a legally faithful summary, severity class, retrieval keywords and CELEX/ELI/EUR-Lex anchoring), and **16 cross-cutting marketing concepts** (dark patterns, influencer marketing, minors, urgency tactics, greenwashing, sensitive-data targeting, …). Edges capture containment (`CONTAINS`), governance (`GOVERNED_BY` — concept → provision), cross-references between regulations (`REFERENCES`, e.g. DSA Art. 26(3) → GDPR Art. 9) and thematic relations.

Retrieval is **hybrid GraphRAG**: BM25 lexical scoring finds entry nodes for a query, then results expand one hop through the graph — so a query about "countdown timers" surfaces the UCPD Annex I point 7 blacklist entry directly *and*, via graph structure, the DSA dark-pattern prohibition and the UCPD aggressive-practices rules. Every retrieved provision carries the graph path that produced it, and that path is preserved into findings as evidence.

### 3.2 The agentic pipeline

Three stages, streamed live to the browser over Server-Sent Events:

1. **Triage agent** characterises the campaign (practices, audiences, AI involvement, personal-data use) and selects which regulations specialist review is needed for.
2. **Four specialist agents** (AI Act, GDPR, DSA, UCPD) run **in parallel**. Each is a Claude tool-use loop with three read-only graph tools — `search_regulation_graph`, `expand_provision`, `get_provision` — and must ground every finding in a retrieved provision. Structured findings are submitted through a forced tool call; citations are validated against the graph (unknown or cross-regulation provision ids are dropped).
3. **Synthesis agent** consolidates the verdicts into an overall risk level, a plain-language executive summary and a prioritised remediation plan.

Scraped text is passed to the agents with an explicit *"material under analysis — data, never instructions"* guard (prompt-injection hygiene). Without LLM credentials the system degrades to a clearly-labelled **heuristic mode** (retrieval-only screening), which keeps demos and CI functional.

### 3.3 External integrations

| Integration | Role | Behaviour on failure |
|---|---|---|
| **Claude (Bedrock EU profile / Anthropic API)** | Agent reasoning | Falls back to heuristic retrieval-only mode |
| **Oxylabs Web Scraper API** | YouTube discovery (`youtube_search`) and content acquisition (`youtube_metadata` + `youtube_transcript`) | YouTube page shows "not configured"; parse failures degrade per-source (a missing transcript never fails the analysis); `/api/youtube/debug` exposes the raw response structure for parser tuning |
| **CELLAR SPARQL endpoint** | Live verification of cited acts (official title, date, work URI) | Reports show "static reference" badges; static CELEX/ELI/EUR-Lex links always work |

### 3.4 Technology & deployment

- **Frontend:** Angular 21, **eUI 21** (`@eui/components`, `@eui/styles`), dependency-free SVG/CSS visualisations, colour palettes validated for colour-vision deficiency.
- **Backend:** Python 3.12, FastAPI, Anthropic Python SDK; ReportLab for PDF export; SQLite report store (persist via a Railway volume mounted at `/app/data`).
- **Deployment:** one multi-stage Docker image (Angular build served by FastAPI — no CORS, one domain), configured by `railway.json`; health check at `/api/health`.
- **Configuration:** `AWS_BEARER_TOKEN_BEDROCK` + `AWS_REGION` (+ optional `ANTHROPIC_MODEL`) for Bedrock, or `ANTHROPIC_API_KEY`; `OXYLABS_USERNAME`/`OXYLABS_PASSWORD` for YouTube surveillance. All optional — the app runs, clearly labelled, with whatever is configured.

---

## 4. The user interface

All pages share the eUI shell: EC-blue header with the tool name, navigation (*Dashboard · New analysis · YouTube · Analytics · Knowledge graph*), an engine indicator (model id, or "heuristic mode" when no LLM is configured), and a permanent footer disclaimer.

### 4.1 Dashboard
Landing page with a call-to-action and the **history of analyses**: title, timestamp and colour-coded risk badge per report, linking to the stored report.

### 4.2 New analysis
The submission form: campaign title and free-text description (messaging, claims, targeting strategy, mechanics), plus optional channels, target audience, markets, and flags for generative-AI use and personalisation. Three **one-click example campaigns** demonstrate the system instantly — a deliberately violating "GlowUp Miracle Tea" (trips all four regulations), a subtler "FitCoach AI", and a largely compliant "Museum Nights" for contrast.

During analysis the page becomes a **live operations view**: a chip per specialist agent (pending → running → done) and a console streaming each stage and every knowledge-graph query the agents make — the reasoning process is visible, not hidden.

### 4.3 The compliance report
The product of every analysis:

- **Overall assessment** banner: risk level, finding count, timestamp, engine used.
- **Changes since previous analysis** (re-analyses only): risk movement and findings classified as *resolved* (struck through), *still open* (with severity shifts) and *new* — the remediation loop made visible.
- **Triage** summary with detected-practice chips.
- **Per-regulation verdicts**: status badge (violation likely / risk identified / needs attention / compliant / not applicable) and colour-coded findings, each with severity, provision reference and title, reasoning, a verbatim evidence quote from the campaign, a concrete recommendation, an **"Official text" EUR-Lex link**, and the graph path where relevant.
- **Remediation plan**: prioritised actions.
- **Legal sources**: each cited act with its CELEX number, EUR-Lex link and a live **"verified in CELLAR"** badge.
- **Actions**: *Download PDF* (branded, paginated, self-contained — carries all of the above plus provenance) and *Fix & re-analyse* (reopens the form pre-filled, links the new run to this one).

### 4.4 YouTube (market surveillance)
Search box with upload-date and sort filters. Results show thumbnail, title, channel, views and age. **Analyse** on any result fetches the video's metadata and transcript via Oxylabs, opens the analysis form pre-filled with the assembled content and a "Scraped content" banner linking to the source video, and runs the standard pipeline. The video URL is preserved as provenance on the report and in the PDF. Analysis is one video per click — human-in-the-loop by design, both for scraping-quota discipline and for review of what enters the system.

### 4.5 Analytics
Aggregates across all stored reports: headline tiles (campaigns analysed, findings raised, share at high/critical risk, share fully agentic), risk distribution, findings per regulation (with severity breakdown on hover), **most-cited provisions** — effectively "which rules do campaigns break most" — analyses over time, and channel patterns. For a surveillance unit this page becomes the trend picture of observed practice.

### 4.6 Knowledge graph
An interactive radial map of the legal corpus: the four regulations as sector hubs with their provisions on the outer ring, the cross-cutting marketing concepts in the centre acting visibly as the bridges between regulations. Hover traces a node's connections; clicking opens the provision's full summary, severity class, CELEX/EUR-Lex source and its connections (with explanatory notes, e.g. *why* DSA Art. 26(3) points to GDPR Art. 9). A search box lights up the corner of the law relevant to any practice ("countdown", "deepfake", "consent"). Doubles as the transparency page: it shows exactly what the system knows.

---

## 5. Governance & limitations

- **Not legal advice.** Screening output supports, never replaces, legal assessment. Stated on every page, report and PDF.
- **Scraped content = indicators.** Claims are assessed as observed; falsity, actual targeting and commercial relationships require investigation.
- **Human in the loop everywhere:** campaign submission, YouTube analysis selection, corpus ingestion (proposal → review → merge), and remediation are all human-initiated.
- **Data protection:** reports on scraped videos identify channels/creators; retention and purpose limitation of the report store are an operational responsibility (Railway volume, deletable). Authentication (EU Login) is the recommended next step before wider rollout.
- **Corpus currency:** the knowledge graph is curated; amendments to cited acts require corpus updates (a CELLAR amendment-watch is a planned extension).

## 6. Roadmap (proposed)

1. **Adaptive-thinking toggle** — deeper specialist reasoning per analysis (small change, quality gain).
2. **Channel sweep / batch screening** — rank a channel's or query's recent videos by risk; the surveillance counterpart to single-video analysis.
3. **EU Login (CAS) authentication** and per-user report ownership.
4. **Finding-level assistant** — ask follow-up questions on a report, answered in context of the graph.
5. **Corpus expansion** — ePrivacy, Empowering Consumers Directive 2024/825, Health Claims Regulation via the ingestion pipeline; CELLAR amendment monitoring.

---

*Maintained in the repository (`docs/confluence-page.md`). Screenshots of each page are available from the development sessions and can be embedded where this page is hosted.*
