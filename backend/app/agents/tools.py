"""Tool definitions and executor giving Claude agents access to the knowledge graph."""
import json

from ..graphrag.graph import KnowledgeGraph
from ..graphrag.retriever import GraphRetriever

GRAPH_TOOLS = [
    {
        "name": "search_regulation_graph",
        "description": (
            "Hybrid GraphRAG search over the EU marketing-law knowledge graph "
            "(AI Act, GDPR, DSA, UCPD provisions plus cross-cutting marketing concepts). "
            "Finds lexical entry points and expands them one hop through the graph, so "
            "results include structurally related provisions from other regulations. "
            "Call this with short, focused queries describing a practice found in the "
            "campaign (e.g. 'countdown timer urgency', 'AI chatbot disclosure', "
            "'health condition targeting')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Short focused search query about one practice."},
                "regulation": {
                    "type": "string",
                    "enum": ["AI_ACT", "GDPR", "DSA", "UCPD"],
                    "description": "Optional: restrict provision results to one regulation. Concepts always cross regulations.",
                },
                "top_k": {"type": "integer", "description": "Number of results (default 6, max 12)."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_provision",
        "description": "Fetch the full text of a specific node (provision or concept) from the knowledge graph by its id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "Node id, e.g. 'ucpd-annex1-7' or 'c-dark-patterns'."},
            },
            "required": ["node_id"],
        },
    },
    {
        "name": "expand_provision",
        "description": (
            "Traverse the knowledge graph from a node: returns all connected nodes with the "
            "edge type (CONTAINS, GOVERNED_BY, REFERENCES, RELATED_TO) and explanatory notes. "
            "Use this to discover cross-regulation implications of a provision."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "Node id to expand."},
            },
            "required": ["node_id"],
        },
    },
]


class GraphToolExecutor:
    def __init__(self, graph: KnowledgeGraph, retriever: GraphRetriever):
        self.graph = graph
        self.retriever = retriever

    def execute(self, name: str, tool_input: dict) -> str:
        try:
            if name == "search_regulation_graph":
                top_k = min(int(tool_input.get("top_k", 6)), 12)
                results = self.retriever.search(
                    tool_input["query"],
                    regulation=tool_input.get("regulation"),
                    top_k=top_k,
                )
                return json.dumps(results, ensure_ascii=False)
            if name == "get_provision":
                node = self.graph.get(tool_input["node_id"])
                return json.dumps(node or {"error": f"unknown node id {tool_input['node_id']}"}, ensure_ascii=False)
            if name == "expand_provision":
                node_id = tool_input["node_id"]
                if not self.graph.get(node_id):
                    return json.dumps({"error": f"unknown node id {node_id}"})
                nbs = self.graph.neighbors(node_id)
                return json.dumps([
                    {
                        "edge_type": nb["type"],
                        "direction": nb["direction"],
                        "note": nb.get("note"),
                        "id": nb["node"]["id"],
                        "ref": nb["node"].get("ref"),
                        "title": nb["node"].get("title"),
                        "regulation": nb["node"].get("regulation"),
                    }
                    for nb in nbs
                ], ensure_ascii=False)
            return json.dumps({"error": f"unknown tool {name}"})
        except (KeyError, TypeError, ValueError) as exc:
            return json.dumps({"error": f"bad tool input: {exc}"})
