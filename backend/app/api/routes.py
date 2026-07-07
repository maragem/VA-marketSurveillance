import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

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
async def analyze_stream(campaign: CampaignSubmission, request: Request, parent_id: str | None = None):
    """Run the agentic analysis, streaming progress events as SSE.

    The client POSTs the campaign and reads the SSE stream from the response
    body (fetch + ReadableStream — EventSource does not support POST).
    The final event carries the complete report, which is also persisted.
    Pass ?parent_id= to link the run to an earlier report as a re-analysis.
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
            await store.save(result)
            await queue.put({"type": "report", "report": json.loads(result.model_dump_json())})
        except Exception as exc:
            logger.exception("analysis %s failed", report.id)
            report.status = "failed"
            report.error = str(exc)
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
