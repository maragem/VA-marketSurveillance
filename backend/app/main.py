import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .agents.orchestrator import Orchestrator
from .api.routes import router
from .graphrag.graph import KnowledgeGraph
from .graphrag.retriever import GraphRetriever
from .store import ReportStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("marketsurveillance")


@asynccontextmanager
async def lifespan(app: FastAPI):
    graph = KnowledgeGraph(config.KNOWLEDGE_DIR)
    retriever = GraphRetriever(graph)
    app.state.graph = graph
    app.state.retriever = retriever
    app.state.orchestrator = Orchestrator(graph, retriever)
    app.state.store = ReportStore(config.DATA_DIR)
    logger.info("Knowledge graph loaded: %s", graph.summary())
    if not config.llm_available():
        logger.warning("ANTHROPIC_API_KEY not set — running in heuristic (retrieval-only) mode.")
    yield


app = FastAPI(title="EU Marketing Compliance Checker", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# Serve the built Angular app when present (single-service deployment).
if config.STATIC_DIR.is_dir():

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        candidate = (config.STATIC_DIR / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(config.STATIC_DIR.resolve()):
            return FileResponse(candidate)
        return FileResponse(config.STATIC_DIR / "index.html")
