"""Retrieve the text of an EU act from CELLAR by CELEX number.

Strategy (first source that succeeds wins):
1. CELLAR content negotiation on the CELEX-based PSI:
   http://publications.europa.eu/resource/celex/{CELEX}
   with Accept: application/xhtml+xml and Accept-Language: eng.
2. The EUR-Lex HTML rendition:
   https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:{CELEX}

Both return the full act as (X)HTML, which the parser splits into articles.
"""
import logging

import httpx

logger = logging.getLogger("ingest")

CELLAR_RESOURCE = "http://publications.europa.eu/resource/celex/{celex}"
EUR_LEX_HTML = "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:{celex}"

_HEADERS = {
    "Accept": "application/xhtml+xml,text/html;q=0.9",
    "Accept-Language": "eng,en",
    "User-Agent": "marketing-compliance-checker/1.0 (knowledge-graph ingestion)",
}


def fetch_act_html(celex: str, timeout: float = 60.0) -> str:
    errors: list[str] = []
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=_HEADERS) as client:
        for url in (CELLAR_RESOURCE.format(celex=celex), EUR_LEX_HTML.format(celex=celex)):
            try:
                logger.info("Fetching %s", url)
                response = client.get(url)
                response.raise_for_status()
                if len(response.text) < 2000:
                    raise ValueError(f"suspiciously short response ({len(response.text)} bytes)")
                return response.text
            except (httpx.HTTPError, ValueError) as exc:
                errors.append(f"{url}: {exc}")
    raise RuntimeError(
        "Could not retrieve the act from CELLAR or EUR-Lex:\n  " + "\n  ".join(errors)
    )
