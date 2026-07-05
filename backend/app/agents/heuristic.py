"""Deterministic fallback engine used when no ANTHROPIC_API_KEY is configured.

It runs the same GraphRAG retriever directly over the campaign text so the
application remains demonstrable end-to-end (submission -> streamed progress
-> report) without LLM access. Findings are retrieval-based, not reasoned, and
are labelled accordingly in the report (`engine: "heuristic"`).
"""
from typing import Awaitable, Callable

from .. import config
from ..graphrag.retriever import GraphRetriever
from ..models import AnalysisReport, Finding, RegulationVerdict, TriageResult

_SEVERITY_BY_HINT = {
    "prohibition": "high",
    "obligation": "medium",
    "transparency": "medium",
    "principle": "low",
    "definition": "info",
}

_RISK_ORDER = ["compliant", "low", "medium", "high", "critical"]


async def run_heuristic_analysis(
    report: AnalysisReport,
    retriever: GraphRetriever,
    emit: Callable[[dict], Awaitable[None]],
) -> AnalysisReport:
    campaign = report.campaign
    query = f"{campaign.title} {campaign.text} {campaign.target_audience or ''} {' '.join(campaign.channels)}"

    report.triage = TriageResult(
        detected_practices=[],
        ai_involved=bool(campaign.uses_ai_generation),
        personal_data_involved=bool(campaign.uses_personalisation),
        minors_potentially_reached=False,
        regulations_to_check=list(config.REGULATIONS),
        summary="Heuristic mode: all four regulations screened via GraphRAG retrieval (no LLM available).",
    )
    await emit({"type": "triage", "triage": report.triage.model_dump()})

    hits = retriever.search(query, top_k=12)
    by_regulation: dict[str, list[Finding]] = {r: [] for r in config.REGULATIONS}
    for hit in hits:
        if hit["type"] != "provision" or hit["score"] < 1.0:
            continue
        reg = hit["regulation"]
        by_regulation[reg].append(Finding(
            regulation=reg,
            provision_id=hit["id"],
            provision_ref=hit["ref"],
            title=hit["title"],
            severity=_SEVERITY_BY_HINT.get(hit.get("severity_hint") or "", "medium"),
            rationale=("Retrieved as relevant by GraphRAG matching against the campaign text "
                       f"(graph path: {' '.join(hit['graph_path'])}). Verify applicability manually — "
                       "heuristic mode performs retrieval, not legal reasoning."),
            recommendation="Review the campaign against this provision; configure ANTHROPIC_API_KEY for full agentic analysis.",
            graph_path=hit["graph_path"],
        ))

    verdicts = []
    for reg in config.REGULATIONS:
        findings = by_regulation[reg][:4]
        status = "attention" if findings else "not_applicable"
        verdicts.append(RegulationVerdict(
            regulation=reg, status=status, findings=findings,
            notes="Heuristic screening result." if findings else "No relevant provisions retrieved.",
        ))
        await emit({"type": "agent_completed", "regulation": reg, "verdict": verdicts[-1].model_dump()})

    report.verdicts = verdicts
    worst = "compliant"
    for v in verdicts:
        for f in v.findings:
            if _RISK_ORDER.index(f.severity if f.severity in _RISK_ORDER else "medium") > _RISK_ORDER.index(worst):
                worst = f.severity if f.severity in _RISK_ORDER else "medium"
    report.overall_risk = worst
    report.executive_summary = (
        "Heuristic GraphRAG screening completed without LLM reasoning. The provisions listed were "
        "retrieved as potentially relevant to the campaign text and require manual verification. "
        "Configure ANTHROPIC_API_KEY to enable the full agentic analysis."
    )
    report.recommendations = ["Configure ANTHROPIC_API_KEY on the deployment to enable agentic compliance analysis."]
    report.engine = "heuristic"
    report.status = "completed"
    return report
