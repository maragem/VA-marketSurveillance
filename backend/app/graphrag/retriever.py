"""Hybrid GraphRAG retriever.

Stage 1 (entry points): BM25 lexical scoring over node title/text/keywords
finds candidate nodes for a query. No external embedding service is required,
which keeps the system deployable with a single API key; the scorer can be
swapped for a vector index without touching callers.

Stage 2 (graph expansion): candidates are expanded one hop through the graph
(concept -> governing provisions, provision -> cross-referenced provisions),
so a query about "countdown timers" surfaces not only UCPD Annex I point 7
but also the related DSA dark-pattern and aggressive-practice provisions.
"""
import math
import re
from collections import Counter

from .graph import KnowledgeGraph

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class GraphRetriever:
    def __init__(self, graph: KnowledgeGraph):
        self.graph = graph
        self._docs: dict[str, Counter] = {}
        self._doc_len: dict[str, int] = {}
        df: Counter = Counter()
        for node_id, node in graph.nodes.items():
            text = " ".join([
                node.get("title", ""),
                node.get("text", ""),
                " ".join(node.get("keywords", [])) * 3,  # keywords weigh more
            ])
            toks = _tokens(text)
            self._docs[node_id] = Counter(toks)
            self._doc_len[node_id] = len(toks)
            for term in set(toks):
                df[term] += 1
        self._n_docs = len(self._docs)
        self._avg_len = sum(self._doc_len.values()) / max(1, self._n_docs)
        self._idf = {
            term: math.log(1 + (self._n_docs - freq + 0.5) / (freq + 0.5))
            for term, freq in df.items()
        }

    def _bm25(self, query_tokens: list[str], node_id: str, k1: float = 1.5, b: float = 0.75) -> float:
        doc = self._docs[node_id]
        dl = self._doc_len[node_id]
        score = 0.0
        for term in query_tokens:
            tf = doc.get(term, 0)
            if not tf:
                continue
            idf = self._idf.get(term, 0.0)
            score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / self._avg_len))
        return score

    def search(self, query: str, regulation: str | None = None, top_k: int = 6) -> list[dict]:
        """Hybrid search: BM25 entry points + 1-hop graph expansion.

        Returns provision/concept nodes ranked by combined score, each with
        the graph path that surfaced it.
        """
        q = _tokens(query)
        scored: dict[str, tuple[float, list[str]]] = {}

        for node_id in self._docs:
            node = self.graph.nodes[node_id]
            if node["type"] == "regulation":
                continue
            s = self._bm25(q, node_id)
            if s > 0:
                scored[node_id] = (s, [node_id])

        # Graph expansion: propagate a fraction of each entry node's score to
        # its neighbours so structurally-related provisions surface too.
        for node_id, (score, path) in list(scored.items()):
            for nb in self.graph.neighbors(node_id):
                nb_node = nb["node"]
                if nb_node["type"] == "regulation":
                    continue
                bonus = score * (0.6 if nb["type"] == "GOVERNED_BY" else 0.4)
                prev = scored.get(nb_node["id"])
                if prev is None or prev[0] < bonus:
                    scored[nb_node["id"]] = (
                        max(bonus, prev[0] if prev else 0.0),
                        path + [f"--{nb['type']}-->", nb_node["id"]],
                    )

        results = []
        for node_id, (score, path) in scored.items():
            node = self.graph.nodes[node_id]
            if regulation and node["type"] == "provision" and node.get("regulation") != regulation:
                continue
            results.append({
                "id": node_id,
                "score": round(score, 3),
                "graph_path": path,
                "type": node["type"],
                "regulation": node.get("regulation"),
                "ref": node.get("ref"),
                "title": node.get("title"),
                "severity_hint": node.get("severity_hint"),
                "text": node.get("text"),
            })
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]
