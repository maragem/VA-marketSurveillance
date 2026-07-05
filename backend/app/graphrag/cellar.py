"""CELLAR / EUR-Lex source references for the legal knowledge graph.

CELLAR is the Publications Office of the EU's common content repository — the
semantic backend of EUR-Lex. Every act in the corpus is identified by a CELEX
number and an ELI (European Legislation Identifier); CELLAR exposes them as
linked-data resources and via a public SPARQL endpoint.

This module provides:
- static, network-free source references (CELEX, ELI, CELLAR resource URI,
  EUR-Lex landing page, article-level deep links) used to enrich graph nodes
  and findings, and
- an optional live metadata lookup against the CELLAR SPARQL endpoint
  (official title, publication date) with caching and graceful failure, so
  reports can show that references were verified against the authoritative
  repository.
"""
import asyncio
import logging
import re
import time
from typing import Optional

import httpx

logger = logging.getLogger("marketsurveillance")

SPARQL_ENDPOINT = "https://publications.europa.eu/webapi/rdf/sparql"

# Authoritative identifiers per regulation in the corpus.
REGULATION_SOURCES: dict[str, dict[str, str]] = {
    "AI_ACT": {
        "celex": "32024R1689",
        "eli": "http://data.europa.eu/eli/reg/2024/1689/oj",
    },
    "GDPR": {
        "celex": "32016R0679",
        "eli": "http://data.europa.eu/eli/reg/2016/679/oj",
    },
    "DSA": {
        "celex": "32022R2065",
        "eli": "http://data.europa.eu/eli/reg/2022/2065/oj",
    },
    "UCPD": {
        "celex": "32005L0029",
        "eli": "http://data.europa.eu/eli/dir/2005/29/oj",
    },
}

_ARTICLE_RE = re.compile(r"Arts?\.\s*(\d+)")
_ANNEX_RE = re.compile(r"Annex\s+([IVX]+)", re.IGNORECASE)


def _eur_lex_url(celex: str, ref: Optional[str] = None) -> str:
    url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"
    if ref:
        m = _ARTICLE_RE.search(ref)
        if m:
            return f"{url}#art_{m.group(1)}"
        m = _ANNEX_RE.search(ref)
        if m:
            return f"{url}#anx_{m.group(1)}"
    return url


# CELEX document types -> ELI type segment (sector 3 = legislation).
_CELEX_RE = re.compile(r"^3(\d{4})([LRD])(\d{4})$")
_ELI_TYPES = {"L": "dir", "R": "reg", "D": "dec"}


def _eli_from_celex(celex: str) -> Optional[str]:
    m = _CELEX_RE.match(celex)
    if not m:
        return None
    year, doc_type, number = m.groups()
    return f"http://data.europa.eu/eli/{_ELI_TYPES[doc_type]}/{year}/{int(number)}/oj"


def source_from_celex(celex: str, ref: Optional[str] = None, eli: Optional[str] = None) -> dict:
    """Source-reference block for any act identified by CELEX number."""
    return {
        "celex": celex,
        "eli": eli or _eli_from_celex(celex),
        "cellar_uri": f"http://publications.europa.eu/resource/celex/{celex}",
        "eur_lex_url": _eur_lex_url(celex, ref),
    }


def source_for(regulation: Optional[str], ref: Optional[str] = None) -> Optional[dict]:
    """Static source-reference block for a node of the given core regulation."""
    src = REGULATION_SOURCES.get(regulation or "")
    if not src:
        return None
    return source_from_celex(src["celex"], ref, eli=src["eli"])


class CellarClient:
    """Minimal async client for the CELLAR SPARQL endpoint.

    Used for display metadata only — the analysis itself relies on the curated
    graph, so CELLAR being unreachable degrades gracefully to static links.
    """

    _QUERY = """
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
SELECT ?work ?title ?date WHERE {{
  ?work cdm:resource_legal_id_celex "{celex}"^^<http://www.w3.org/2001/XMLSchema#string> .
  OPTIONAL {{ ?work cdm:work_date_document ?date . }}
  OPTIONAL {{
    ?exp cdm:expression_belongs_to_work ?work ;
         cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/ENG> ;
         cdm:expression_title ?title .
  }}
}} LIMIT 1
"""

    def __init__(self, cache_ttl: float = 24 * 3600):
        self._cache: dict[str, tuple[float, dict]] = {}
        self._ttl = cache_ttl
        self._lock = asyncio.Lock()

    async def metadata(self, celex: str) -> dict:
        async with self._lock:
            cached = self._cache.get(celex)
            if cached and time.monotonic() - cached[0] < self._ttl:
                return cached[1]

        result: dict = {"celex": celex, "available": False}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    SPARQL_ENDPOINT,
                    params={
                        "query": self._QUERY.format(celex=celex),
                        "format": "application/sparql-results+json",
                    },
                    headers={"Accept": "application/sparql-results+json"},
                )
                response.raise_for_status()
                bindings = response.json()["results"]["bindings"]
                if bindings:
                    row = bindings[0]
                    result = {
                        "celex": celex,
                        "available": True,
                        "cellar_work": row.get("work", {}).get("value"),
                        "title": row.get("title", {}).get("value"),
                        "date_document": row.get("date", {}).get("value"),
                    }
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.warning("CELLAR lookup failed for %s: %s", celex, exc)

        if result.get("available"):
            async with self._lock:
                self._cache[celex] = (time.monotonic(), result)
        return result
