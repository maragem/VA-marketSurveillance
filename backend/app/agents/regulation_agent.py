"""Specialist regulation agent: a Claude tool-use loop scoped to one regulation.

Each agent receives the campaign, the triage signals, and a digest of its
regulation's subgraph, then investigates using the GraphRAG tools and submits
structured findings through a forced `submit_assessment` tool call.
"""
import json
from typing import Awaitable, Callable

from anthropic import AsyncAnthropic

from .. import config
from ..models import Finding, RegulationVerdict
from .tools import GRAPH_TOOLS, GraphToolExecutor

SUBMIT_TOOL = {
    "name": "submit_assessment",
    "description": "Submit your final compliance assessment for this regulation. Call exactly once, when your investigation is complete.",
    "input_schema": {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["violation_likely", "risk_identified", "attention", "compliant", "not_applicable"],
            },
            "notes": {"type": "string", "description": "Short overall assessment for this regulation (2-4 sentences)."},
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "provision_id": {"type": "string", "description": "Knowledge-graph node id of the provision, e.g. 'ucpd-annex1-7'."},
                        "severity": {"type": "string", "enum": ["critical", "high", "medium", "low", "info"]},
                        "rationale": {"type": "string", "description": "Why this campaign engages/violates the provision."},
                        "evidence_quote": {"type": "string", "description": "Short verbatim quote from the campaign text that triggers the issue."},
                        "recommendation": {"type": "string", "description": "Concrete, actionable fix the marketer can apply."},
                    },
                    "required": ["provision_id", "severity", "rationale", "recommendation"],
                },
            },
        },
        "required": ["status", "notes", "findings"],
    },
}

SYSTEM_PROMPT = """You are a specialist EU marketing-compliance agent for the {label}.

You review a marketing campaign submitted as text and assess it ONLY against this regulation. Other agents cover the other regulations in parallel — do not report their findings, but you may use cross-regulation graph edges to understand context.

Provisions of your regulation available in the knowledge graph:
{digest}

Method:
1. Identify the concrete practices in the campaign (claims, targeting, AI usage, design tactics, audiences).
2. Use search_regulation_graph / expand_provision / get_provision to ground every finding in a specific provision. Never cite a provision you have not retrieved from the graph.
3. Severity guide: critical = blacklisted/prohibited practice clearly present; high = prohibition or key obligation likely breached; medium = obligation engaged and probably not satisfied as described; low = obligation engaged, easily fixed; info = worth flagging, no likely breach.
4. Only report findings genuinely supported by the campaign text. If the campaign does not engage this regulation, submit status "not_applicable" with no findings.
5. Quote the campaign text verbatim in evidence_quote where possible.

When done, call submit_assessment exactly once with all findings."""


async def run_regulation_agent(
    client: AsyncAnthropic,
    regulation: str,
    campaign_block: str,
    triage_summary: str,
    executor: GraphToolExecutor,
    emit: Callable[[dict], Awaitable[None]],
) -> RegulationVerdict:
    graph = executor.graph
    system = SYSTEM_PROMPT.format(
        label=config.REGULATION_LABELS[regulation],
        digest=graph.regulation_digest(regulation),
    )
    messages = [{
        "role": "user",
        "content": (
            f"Campaign submission:\n{campaign_block}\n\n"
            f"Triage signals from the supervisor agent:\n{triage_summary}\n\n"
            f"Investigate and submit your assessment for {config.REGULATION_LABELS[regulation]}."
        ),
    }]
    tools = GRAPH_TOOLS + [SUBMIT_TOOL]

    for turn in range(config.AGENT_MAX_TURNS):
        force_submit = turn == config.AGENT_MAX_TURNS - 1
        response = await client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=config.AGENT_MAX_TOKENS,
            system=system,
            messages=messages,
            tools=tools,
            tool_choice={"type": "tool", "name": "submit_assessment"} if force_submit else {"type": "auto"},
        )
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        submitted: dict | None = None
        for block in response.content:
            if block.type != "tool_use":
                continue
            if block.name == "submit_assessment":
                submitted = block.input
                tool_results.append({
                    "type": "tool_result", "tool_use_id": block.id, "content": "Assessment recorded.",
                })
            else:
                await emit({
                    "type": "agent_tool_call",
                    "regulation": regulation,
                    "tool": block.name,
                    "input": block.input,
                })
                result = executor.execute(block.name, block.input)
                tool_results.append({
                    "type": "tool_result", "tool_use_id": block.id, "content": result,
                })

        if submitted is not None:
            return _to_verdict(regulation, submitted, executor)

        if response.stop_reason != "tool_use":
            break
        messages.append({"role": "user", "content": tool_results})

    return RegulationVerdict(
        regulation=regulation, status="attention", findings=[],
        notes="The agent did not conclude its assessment within the allotted turns; manual review recommended.",
    )


def _to_verdict(regulation: str, submitted: dict, executor: GraphToolExecutor) -> RegulationVerdict:
    findings: list[Finding] = []
    for raw in submitted.get("findings", []):
        node = executor.graph.get(raw.get("provision_id", ""))
        # Drop hallucinated citations and findings pinned to another regulation's provision.
        if not node or node.get("type") != "provision" or node.get("regulation") != regulation:
            continue
        source = node.get("source") or {}
        findings.append(Finding(
            regulation=regulation,
            provision_id=node["id"],
            provision_ref=node["ref"],
            title=node["title"],
            severity=raw.get("severity", "medium"),
            rationale=raw.get("rationale", ""),
            evidence_quote=raw.get("evidence_quote"),
            recommendation=raw.get("recommendation", ""),
            celex=source.get("celex"),
            source_url=source.get("eur_lex_url"),
        ))
    status = submitted.get("status", "attention")
    if findings and status in ("compliant", "not_applicable"):
        status = "attention"
    return RegulationVerdict(
        regulation=regulation,
        status=status,
        findings=findings,
        notes=submitted.get("notes", ""),
    )
