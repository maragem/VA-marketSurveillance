"""In-memory legal knowledge graph over the curated regulation corpus.

The graph is small (dozens of nodes) and static, so it ships with the image
and is fully loaded at startup. Nodes are regulations, provisions and
cross-cutting marketing concepts; edges capture containment, cross-references
between regulations, and concept-to-provision governance links.
"""
import json
from collections import defaultdict
from pathlib import Path

import re

from .cellar import REGULATION_SOURCES, source_from_celex

_CELEX_IN_REF = re.compile(r"CELEX\s+(3\d{4}[A-Z]\d{4})")


class KnowledgeGraph:
    def __init__(self, knowledge_dir: Path):
        self.nodes: dict[str, dict] = {}
        self.out_edges: dict[str, list[dict]] = defaultdict(list)
        self.in_edges: dict[str, list[dict]] = defaultdict(list)

        nodes = json.loads((knowledge_dir / "nodes.json").read_text())
        edges = json.loads((knowledge_dir / "edges.json").read_text())

        # CELEX per regulation key: the core corpus is hard-coded; ingested
        # acts declare theirs on the regulation node (ref "CELEX 3....", or an
        # explicit "celex" field).
        celex_by_regulation = {key: src["celex"] for key, src in REGULATION_SOURCES.items()}
        for node in nodes:
            if node.get("type") == "regulation" and node.get("regulation"):
                celex = node.get("celex")
                if not celex:
                    m = _CELEX_IN_REF.search(node.get("ref", ""))
                    celex = m.group(1) if m else None
                if celex:
                    celex_by_regulation.setdefault(node["regulation"], celex)

        for node in nodes:
            # Anchor every regulation/provision node to its authoritative
            # source in CELLAR / EUR-Lex (CELEX, ELI, deep link).
            celex = celex_by_regulation.get(node.get("regulation") or "")
            if celex:
                node["source"] = source_from_celex(celex, node.get("ref"))
            self.nodes[node["id"]] = node
        self.edges = []
        for edge in edges:
            if edge["source"] not in self.nodes or edge["target"] not in self.nodes:
                raise ValueError(f"Edge references unknown node: {edge}")
            self.edges.append(edge)
            self.out_edges[edge["source"]].append(edge)
            self.in_edges[edge["target"]].append(edge)

    def get(self, node_id: str) -> dict | None:
        return self.nodes.get(node_id)

    def neighbors(self, node_id: str) -> list[dict]:
        """All edges touching a node, each annotated with the far-end node."""
        result = []
        for edge in self.out_edges.get(node_id, []):
            result.append({"direction": "out", "type": edge["type"],
                           "note": edge.get("note"), "node": self.nodes[edge["target"]]})
        for edge in self.in_edges.get(node_id, []):
            result.append({"direction": "in", "type": edge["type"],
                           "note": edge.get("note"), "node": self.nodes[edge["source"]]})
        return result

    def provisions_for_regulation(self, regulation: str) -> list[dict]:
        return [n for n in self.nodes.values()
                if n["type"] == "provision" and n.get("regulation") == regulation]

    def regulation_digest(self, regulation: str) -> str:
        """Community-summary style digest of one regulation's subgraph,
        used to ground each specialist agent (GraphRAG 'global' context)."""
        lines = []
        for p in self.provisions_for_regulation(regulation):
            lines.append(f"- [{p['id']}] {p['ref']} — {p['title']} ({p.get('severity_hint', 'rule')})")
        return "\n".join(lines)

    def summary(self) -> dict:
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "provisions": sum(1 for n in self.nodes.values() if n["type"] == "provision"),
            "concepts": sum(1 for n in self.nodes.values() if n["type"] == "concept"),
            "regulations": [n["id"] for n in self.nodes.values() if n["type"] == "regulation"],
        }
