"""Turn parsed articles into knowledge-graph node/edge proposals.

Two modes:
- plain: nodes carry the (truncated) article text verbatim, keywords derived
  from the title. Fast, offline, zero LLM cost.
- LLM-enriched (--llm): the configured Claude provider summarises each article
  with its marketing relevance, proposes retrieval keywords, a severity hint,
  and links to existing concept nodes. Uses the same provider setup as the
  analysis pipeline (Anthropic API or Bedrock).
"""
import asyncio
import json
import logging
import re

from .. import config
from .parse import Article

logger = logging.getLogger("ingest")

MAX_TEXT_CHARS = 1500

_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "shall", "article", "of", "to",
    "in", "a", "an", "or", "be", "by", "on", "as", "is", "are", "any", "such",
}

SUMMARY_TOOL = {
    "name": "submit_article_summaries",
    "description": "Submit knowledge-graph summaries for the given articles. Call exactly once.",
    "input_schema": {
        "type": "object",
        "properties": {
            "articles": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "number": {"type": "string", "description": "Article number as given, e.g. '13' or '5a'."},
                        "summary": {
                            "type": "string",
                            "description": "3-6 sentence summary of the obligation/prohibition, ending with 1-2 sentences on 'Marketing relevance: ...' describing when a marketing campaign engages it.",
                        },
                        "keywords": {
                            "type": "array", "items": {"type": "string"},
                            "description": "8-15 lowercase retrieval keywords/phrases marketers would use.",
                        },
                        "severity_hint": {
                            "type": "string",
                            "enum": ["prohibition", "obligation", "transparency", "principle", "definition"],
                        },
                        "marketing_relevant": {
                            "type": "boolean",
                            "description": "false for purely institutional/procedural articles (committees, delegated acts, entry into force).",
                        },
                        "concept_links": {
                            "type": "array", "items": {"type": "string"},
                            "description": "ids of existing concept nodes this article governs (only from the provided list).",
                        },
                    },
                    "required": ["number", "summary", "keywords", "severity_hint", "marketing_relevant"],
                },
            },
        },
        "required": ["articles"],
    },
}


def _slug(regulation_key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", regulation_key.lower()).strip("-")


def _keywords_from(article: Article) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z-]{3,}", article.title.lower())
    return [w for w in words if w not in _STOPWORDS][:10]


def _plain_node_fields(article: Article) -> dict:
    text = article.text[:MAX_TEXT_CHARS]
    if len(article.text) > MAX_TEXT_CHARS:
        text += " […]"
    return {
        "text": text,
        "keywords": _keywords_from(article),
        "severity_hint": "obligation",
        "marketing_relevant": True,
        "concept_links": [],
    }


async def _llm_fields(articles: list[Article], regulation_label: str, concepts: list[dict]) -> dict[str, dict]:
    client = config.make_async_client()
    if client is None:
        raise RuntimeError(
            "--llm requires LLM credentials (ANTHROPIC_API_KEY, or "
            "AWS_BEARER_TOKEN_BEDROCK + AWS_REGION for Bedrock).")

    concept_list = "\n".join(f"- {c['id']}: {c['title']}" for c in concepts)
    results: dict[str, dict] = {}
    batch_size = 6
    for start in range(0, len(articles), batch_size):
        batch = articles[start:start + batch_size]
        block = "\n\n".join(
            f"### Article {a.number} — {a.title}\n{a.text[:6000]}" for a in batch
        )
        logger.info("LLM summarising articles %s", ", ".join(a.number for a in batch))
        response = await client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=config.AGENT_MAX_TOKENS,
            system=(
                f"You prepare knowledge-graph entries about {regulation_label} for an EU "
                "marketing-compliance screening system. Summaries must be legally faithful "
                "and focused on what marketing teams need. Existing concept nodes you may "
                f"link to:\n{concept_list}"
            ),
            messages=[{"role": "user", "content": f"Articles:\n\n{block}\n\nSubmit the summaries."}],
            tools=[SUMMARY_TOOL],
            tool_choice={"type": "tool", "name": "submit_article_summaries"},
        )
        for content_block in response.content:
            if content_block.type == "tool_use":
                for item in content_block.input.get("articles", []):
                    results[str(item["number"]).lower()] = {
                        "text": item["summary"],
                        "keywords": item.get("keywords", []),
                        "severity_hint": item.get("severity_hint", "obligation"),
                        "marketing_relevant": item.get("marketing_relevant", True),
                        "concept_links": item.get("concept_links", []),
                    }
    return results


def build_proposal(
    articles: list[Article],
    celex: str,
    regulation_key: str,
    regulation_label: str,
    existing_nodes: dict[str, dict],
    use_llm: bool = False,
    only_marketing_relevant: bool = False,
) -> dict:
    """Assemble a proposal document with nodes and edges ready for review."""
    slug = _slug(regulation_key)
    concepts = [n for n in existing_nodes.values() if n.get("type") == "concept"]
    valid_concept_ids = {c["id"] for c in concepts}

    if use_llm:
        fields_by_number = asyncio.run(_llm_fields(articles, regulation_label, concepts))
    else:
        fields_by_number = {}

    reg_node_id = f"reg-{slug}"
    nodes: list[dict] = []
    edges: list[dict] = []
    skipped: list[str] = []

    if reg_node_id not in existing_nodes:
        nodes.append({
            "id": reg_node_id,
            "type": "regulation",
            "regulation": regulation_key,
            "ref": f"CELEX {celex}",
            "title": regulation_label,
            "text": f"{regulation_label} (CELEX {celex}), ingested from CELLAR.",
            "keywords": [regulation_label.lower(), celex.lower()],
        })

    for article in articles:
        fields = fields_by_number.get(article.number, _plain_node_fields(article))
        if only_marketing_relevant and not fields.get("marketing_relevant", True):
            skipped.append(f"art. {article.number} (not marketing-relevant)")
            continue
        node_id = f"{slug}-art{article.number}"
        if node_id in existing_nodes:
            skipped.append(f"art. {article.number} (node {node_id} already exists)")
            continue
        nodes.append({
            "id": node_id,
            "type": "provision",
            "regulation": regulation_key,
            "ref": f"{regulation_label.split('(')[0].strip()}, Art. {article.number}",
            "title": article.title or f"Article {article.number}",
            "severity_hint": fields["severity_hint"],
            "text": fields["text"],
            "keywords": fields["keywords"],
        })
        edges.append({"source": reg_node_id, "target": node_id, "type": "CONTAINS"})
        for concept_id in fields.get("concept_links", []):
            if concept_id in valid_concept_ids:
                edges.append({"source": concept_id, "target": node_id, "type": "GOVERNED_BY"})

    return {
        "celex": celex,
        "regulation_key": regulation_key,
        "regulation_label": regulation_label,
        "generated_with_llm": use_llm,
        "model": config.CLAUDE_MODEL if use_llm else None,
        "skipped": skipped,
        "nodes": nodes,
        "edges": edges,
    }


def merge_proposal(proposal: dict, knowledge_dir) -> tuple[int, int]:
    """Merge a reviewed proposal into knowledge/nodes.json and edges.json."""
    nodes_path = knowledge_dir / "nodes.json"
    edges_path = knowledge_dir / "edges.json"
    nodes = json.loads(nodes_path.read_text())
    edges = json.loads(edges_path.read_text())
    existing_ids = {n["id"] for n in nodes}
    existing_edge_keys = {(e["source"], e["target"], e["type"]) for e in edges}

    added_nodes = 0
    for node in proposal["nodes"]:
        if node["id"] not in existing_ids:
            nodes.append(node)
            existing_ids.add(node["id"])
            added_nodes += 1

    added_edges = 0
    for edge in proposal["edges"]:
        key = (edge["source"], edge["target"], edge["type"])
        if key not in existing_edge_keys and edge["source"] in existing_ids and edge["target"] in existing_ids:
            edges.append(edge)
            existing_edge_keys.add(key)
            added_edges += 1

    nodes_path.write_text(json.dumps(nodes, indent=2, ensure_ascii=False) + "\n")
    edges_path.write_text(json.dumps(edges, indent=2, ensure_ascii=False) + "\n")
    return added_nodes, added_edges
