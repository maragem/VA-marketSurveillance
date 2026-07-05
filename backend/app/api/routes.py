import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from .. import config
from ..models import AnalysisReport, CampaignSubmission

logger = logging.getLogger("marketsurveillance")
router = APIRouter(prefix="/api")


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.get("/health")
async def health(request: Request):
    return {
        "status": "ok",
        "llm_configured": config.llm_available(),
        "provider": config.CLAUDE_PROVIDER,
        "model": config.CLAUDE_MODEL if config.llm_available() else None,
        "graph": request.app.state.graph.summary(),
    }


@router.get("/graph/summary")
async def graph_summary(request: Request):
    return request.app.state.graph.summary()


@router.get("/graph/nodes/{node_id}")
async def graph_node(node_id: str, request: Request):
    node = request.app.state.graph.get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Unknown node")
    return {"node": node, "neighbors": request.app.state.graph.neighbors(node_id)}


@router.get("/graph/search")
async def graph_search(q: str, request: Request, regulation: str | None = None, top_k: int = 8):
    return request.app.state.retriever.search(q, regulation=regulation, top_k=min(top_k, 20))


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


@router.post("/analyses/stream")
async def analyze_stream(campaign: CampaignSubmission, request: Request):
    """Run the agentic analysis, streaming progress events as SSE.

    The client POSTs the campaign and reads the SSE stream from the response
    body (fetch + ReadableStream — EventSource does not support POST).
    The final event carries the complete report, which is also persisted.
    """
    orchestrator = request.app.state.orchestrator
    store = request.app.state.store
    report = AnalysisReport(campaign=campaign, status="running")
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
