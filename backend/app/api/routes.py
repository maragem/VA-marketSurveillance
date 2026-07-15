import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from .. import config
from ..models import AnalysisReport, CampaignSubmission

logger = logging.getLogger("marketsurveillance")
router = APIRouter(prefix="/api")


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.get("/health")
async def health(request: Request):
    from .. import oxylabs
    return {
        "status": "ok",
        "llm_configured": config.llm_available(),
        "provider": config.CLAUDE_PROVIDER,
        "model": config.CLAUDE_MODEL if config.llm_available() else None,
        "youtube_configured": oxylabs.available(),
        "graph": request.app.state.graph.summary(),
    }


@router.get("/graph/summary")
async def graph_summary(request: Request):
    return request.app.state.graph.summary()


@router.get("/graph/full")
async def graph_full(request: Request):
    """Complete graph projection for the explorer visualisation."""
    graph = request.app.state.graph
    return {
        "nodes": [
            {
                "id": n["id"],
                "type": n["type"],
                "regulation": n.get("regulation"),
                "ref": n.get("ref"),
                "title": n.get("title"),
                "severity_hint": n.get("severity_hint"),
                "text": n.get("text"),
                "source": n.get("source"),
            }
            for n in graph.nodes.values()
        ],
        "edges": [
            {"source": e["source"], "target": e["target"], "type": e["type"], "note": e.get("note")}
            for e in graph.edges
        ],
    }


@router.get("/graph/nodes/{node_id}")
async def graph_node(node_id: str, request: Request):
    node = request.app.state.graph.get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Unknown node")
    return {"node": node, "neighbors": request.app.state.graph.neighbors(node_id)}


@router.get("/graph/search")
async def graph_search(q: str, request: Request, regulation: str | None = None, top_k: int = 8):
    return request.app.state.retriever.search(q, regulation=regulation, top_k=min(top_k, 20))


@router.get("/youtube/search")
async def youtube_search(q: str, upload_date: str | None = None, sort_by: str | None = None):
    """Search YouTube for candidate campaign videos via Oxylabs."""
    from .. import oxylabs
    if not oxylabs.available():
        raise HTTPException(status_code=503, detail="Oxylabs credentials not configured")
    if upload_date and upload_date not in ("last_hour", "today", "this_week", "this_month", "this_year"):
        raise HTTPException(status_code=400, detail="Invalid upload_date filter")
    if sort_by and sort_by not in ("relevance", "rating", "view_count", "upload_date"):
        raise HTTPException(status_code=400, detail="Invalid sort_by filter")
    try:
        return await oxylabs.search(q, upload_date=upload_date, sort_by=sort_by)
    except oxylabs.OxylabsError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        logger.exception("youtube search failed")
        raise HTTPException(status_code=502, detail=f"Oxylabs request failed: {exc}")


@router.get("/youtube/debug")
async def youtube_debug(q: str = "test"):
    """Structural sketch of the raw Oxylabs search response (parser tuning aid)."""
    from .. import oxylabs
    if not oxylabs.available():
        raise HTTPException(status_code=503, detail="Oxylabs credentials not configured")
    try:
        return await oxylabs.debug_search(q)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/youtube/videos/{video_id}")
async def youtube_video(video_id: str, language: str | None = None):
    """Fetch metadata + transcript for one video, ready for analysis.

    `language` is the preferred transcript language (ISO code) — omit or pass
    "auto" to take whatever captions the video has, with an English fallback.
    """
    from .. import oxylabs
    if not oxylabs.available():
        raise HTTPException(status_code=503, detail="Oxylabs credentials not configured")
    if language and not (2 <= len(language) <= 7 and language.replace("-", "").isalpha()):
        raise HTTPException(status_code=400, detail="Invalid language code")
    try:
        return await oxylabs.video_bundle(video_id, language=language)
    except oxylabs.OxylabsError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        logger.exception("youtube video fetch failed")
        raise HTTPException(status_code=502, detail=f"Oxylabs request failed: {exc}")


@router.get("/cellar/{celex}")
async def cellar_metadata(celex: str, request: Request):
    """Live document metadata from the Publications Office CELLAR repository.

    Display/verification aid only — analysis never depends on it. Returns
    {"available": false} when CELLAR is unreachable.
    """
    if not celex.isalnum() or len(celex) > 20:
        raise HTTPException(status_code=400, detail="Invalid CELEX identifier")
    return await request.app.state.cellar.metadata(celex)


# ---------------------------------------------------------------------------
# Benchmark gold-set editing
# ---------------------------------------------------------------------------

@router.get("/bench/cases")
async def bench_cases(request: Request):
    """The benchmark working copy (seeded from bench/cases.jsonl on first use)."""
    return {"cases": await request.app.state.bench.list()}


@router.post("/bench/cases", status_code=201)
async def bench_create(case: dict, request: Request):
    from ..bench import validate_case
    errors = validate_case(case, request.app.state.graph)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    try:
        await request.app.state.bench.upsert(case, create=True)
    except KeyError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return case


@router.put("/bench/cases/{case_id}")
async def bench_update(case_id: str, case: dict, request: Request):
    if case.get("id") != case_id:
        raise HTTPException(status_code=400, detail="Case id in the body must match the URL.")
    from ..bench import validate_case
    errors = validate_case(case, request.app.state.graph)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    try:
        await request.app.state.bench.upsert(case, create=False)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return case


@router.delete("/bench/cases/{case_id}", status_code=204)
async def bench_delete(case_id: str, request: Request):
    try:
        await request.app.state.bench.delete(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ---------------------------------------------------------------------------
# Engine calibration (lessons learned from benchmark review)
# ---------------------------------------------------------------------------

class CalibrationRuleRequest(BaseModel):
    regulation: str
    rule: str
    origin: str = "manual"


@router.get("/calibration")
async def calibration_rules(request: Request):
    """Approved calibration rules, grouped by section (GLOBAL + one per regulation)."""
    return await request.app.state.calibration.all()


@router.post("/calibration/rules", status_code=201)
async def calibration_add(body: CalibrationRuleRequest, request: Request):
    try:
        return await request.app.state.calibration.add(
            body.regulation, body.rule, body.origin[:200])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.delete("/calibration/rules/{rule_id}", status_code=204)
async def calibration_remove(rule_id: str, request: Request):
    try:
        await request.app.state.calibration.remove(rule_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/calibration/export")
async def calibration_export(request: Request):
    """Download the working calibration set, ready to commit to knowledge/calibration.json."""
    text = await request.app.state.calibration.export_text()
    return Response(
        content=text,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="calibration.json"'},
    )


@router.post("/bench/lessons/propose")
async def bench_propose_lessons(request: Request):
    """Distil benchmark deviations into candidate calibration rules (human approves)."""
    if not config.llm_available():
        raise HTTPException(status_code=503,
                            detail="Lesson proposals require LLM credentials (agentic mode).")
    from ..calibration import propose_lessons
    bench = request.app.state.bench
    cases = await bench.list()
    runs = await bench.runs()
    if not any(c["id"] in runs for c in cases):
        raise HTTPException(status_code=400,
                            detail="No stored test runs yet — run some cases first, so there are "
                                   "deviations to learn from.")
    existing = await request.app.state.calibration.all()
    try:
        proposals = await propose_lessons(request.app.state.graph, cases, runs, existing)
    except Exception as exc:
        logger.exception("lesson proposal failed")
        raise HTTPException(status_code=502, detail=f"Lesson proposal failed: {exc}")
    return {"proposals": proposals}


class AdjudicateRequest(BaseModel):
    campaign: CampaignSubmission
    provision_id: str
    severity: str = "medium"
    rationale: str = ""
    evidence_quote: str | None = None


@router.post("/bench/adjudicate")
async def bench_adjudicate(body: AdjudicateRequest, request: Request):
    """Second opinion on a disputed engine citation (benchmark review aid)."""
    if not config.llm_available():
        raise HTTPException(status_code=503,
                            detail="Second opinions require LLM credentials (agentic mode).")
    from ..bench import adjudicate_finding
    try:
        return await adjudicate_finding(
            request.app.state.graph, body.campaign, body.provision_id,
            body.severity, body.rationale, body.evidence_quote)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("adjudication failed")
        raise HTTPException(status_code=502, detail=f"Adjudication failed: {exc}")


@router.get("/bench/runs")
async def bench_runs(request: Request):
    """Stored last-run outcome per case id."""
    return await request.app.state.bench.runs()


@router.put("/bench/runs/{case_id}")
async def bench_save_run(case_id: str, outcome: dict, request: Request):
    """Persist the outcome of a UI test run for a case (last run wins)."""
    if len(json.dumps(outcome)) > 100_000:
        raise HTTPException(status_code=413, detail="Run outcome too large")
    from datetime import datetime, timezone
    outcome["recorded_at"] = datetime.now(timezone.utc).isoformat()
    try:
        await request.app.state.bench.save_run(case_id, outcome)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return outcome


@router.get("/bench/summary")
async def bench_summary(request: Request):
    """Scorecard-style aggregate of the stored UI test runs."""
    from ..bench import build_summary
    bench = request.app.state.bench
    return build_summary(await bench.list(), await bench.runs(), request.app.state.graph)


@router.get("/bench/summary/export")
async def bench_summary_export(request: Request, format: str = "md"):
    """Download the results summary as markdown or JSON."""
    from ..bench import build_summary, summary_markdown
    bench = request.app.state.bench
    summary = build_summary(await bench.list(), await bench.runs(), request.app.state.graph)
    stamp = (summary.get("latest_run_at") or "")[:10] or "latest"
    if format == "json":
        return Response(
            content=json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="benchmark-summary-{stamp}.json"'},
        )
    return Response(
        content=summary_markdown(summary),
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="benchmark-summary-{stamp}.md"'},
    )


@router.get("/bench/export")
async def bench_export(request: Request):
    """Download the working copy as cases.jsonl, ready to commit to the repo."""
    text = await request.app.state.bench.export_text()
    return Response(
        content=text,
        media_type="application/jsonl",
        headers={"Content-Disposition": 'attachment; filename="cases.jsonl"'},
    )


@router.get("/analytics")
async def analytics(request: Request):
    from ..analytics import build_analytics
    reports = await request.app.state.store.payloads()
    return build_analytics(reports)


@router.get("/analyses")
async def list_analyses(request: Request):
    return await request.app.state.store.list()


@router.get("/analyses/{report_id}")
async def get_analysis(report_id: str, request: Request):
    report = await request.app.state.store.get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Unknown analysis")
    return report


class RenameRequest(BaseModel):
    title: str


@router.patch("/analyses/{report_id}")
async def rename_analysis(report_id: str, body: RenameRequest, request: Request):
    """Rename a stored analysis (report title = campaign title)."""
    title = " ".join(body.title.split())
    if not title:
        raise HTTPException(status_code=400, detail="Title must not be empty")
    if len(title) > 200:
        raise HTTPException(status_code=400, detail="Title too long (max 200 characters)")
    report = await request.app.state.store.rename(report_id, title)
    if not report:
        raise HTTPException(status_code=404, detail="Unknown analysis")
    return report


@router.get("/analyses/{report_id}/pdf")
async def analysis_pdf(report_id: str, request: Request):
    report = await request.app.state.store.get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Unknown analysis")
    from ..pdf import build_pdf
    pdf_bytes = await asyncio.to_thread(build_pdf, report)
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in report.campaign.title)[:60].strip()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="compliance-report-{safe_title or report_id}.pdf"'},
    )


@router.get("/analyses/{report_id}/diff")
async def analysis_diff(report_id: str, request: Request):
    """Diff a re-analysis against its parent report."""
    store = request.app.state.store
    current = await store.get(report_id)
    if not current:
        raise HTTPException(status_code=404, detail="Unknown analysis")
    if not current.parent_id:
        raise HTTPException(status_code=400, detail="This analysis has no parent to compare against")
    parent = await store.get(current.parent_id)
    if not parent:
        raise HTTPException(status_code=404, detail="Parent analysis no longer exists")
    from ..diff import build_diff
    return build_diff(parent, current)


@router.post("/analyses/stream")
async def analyze_stream(campaign: CampaignSubmission, request: Request,
                         parent_id: str | None = None, persist: bool = True):
    """Run the agentic analysis, streaming progress events as SSE.

    The client POSTs the campaign and reads the SSE stream from the response
    body (fetch + ReadableStream — EventSource does not support POST).
    The final event carries the complete report, which is also persisted.
    Pass ?parent_id= to link the run to an earlier report as a re-analysis,
    or ?persist=false for throwaway runs (e.g. benchmark test runs) that
    should not appear in the dashboard.
    """
    orchestrator = request.app.state.orchestrator
    store = request.app.state.store
    if parent_id and not await store.get(parent_id):
        raise HTTPException(status_code=404, detail="Unknown parent analysis")
    report = AnalysisReport(campaign=campaign, status="running", parent_id=parent_id)
    queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def emit(event: dict) -> None:
        await queue.put(event)

    async def run() -> None:
        try:
            result = await orchestrator.run(report, emit)
            if persist:
                await store.save(result)
            await queue.put({"type": "report", "report": json.loads(result.model_dump_json())})
        except Exception as exc:
            logger.exception("analysis %s failed", report.id)
            report.status = "failed"
            report.error = str(exc)
            if persist:
                await store.save(report)
            await queue.put({"type": "error", "message": str(exc), "report_id": report.id})
        finally:
            await queue.put(None)

    async def stream():
        task = asyncio.create_task(run())
        yield _sse({"type": "accepted", "report_id": report.id,
                    "engine": "agentic" if config.llm_available() else "heuristic"})
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield _sse(event)
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
