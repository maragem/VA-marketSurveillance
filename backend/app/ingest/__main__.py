"""CELLAR ingestion CLI — semi-automatic knowledge-graph expansion.

Fetches an act from the Publications Office CELLAR repository by CELEX number,
splits it into articles, and drafts knowledge-graph nodes/edges. The output is
a proposal file under knowledge/proposals/ for human review; --merge folds a
proposal into the live graph.

Examples:
    # Draft nodes for the ePrivacy Directive, LLM-enriched, only articles 1-15
    python -m app.ingest --celex 32002L0058 --regulation EPRIVACY \
        --label "ePrivacy Directive 2002/58/EC" --articles 1-15 --llm

    # Add more GDPR articles to the existing corpus (plain text, no LLM)
    python -m app.ingest --celex 32016R0679 --regulation GDPR \
        --label "GDPR (Regulation (EU) 2016/679)" --articles 15,17,20

    # Work offline from a saved HTML file
    python -m app.ingest --celex 32002L0058 --regulation EPRIVACY \
        --label "ePrivacy Directive 2002/58/EC" --from-file eprivacy.html

    # Merge a reviewed proposal into knowledge/
    python -m app.ingest --merge knowledge/proposals/proposal-32002L0058.json
"""
import argparse
import json
import logging
import sys
from pathlib import Path

from .. import config
from .fetch import fetch_act_html
from .generate import build_proposal, merge_proposal
from .parse import split_articles

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("ingest")


def _parse_article_selection(spec: str) -> set[str]:
    selected: set[str] = set()
    for part in spec.split(","):
        part = part.strip().lower()
        if "-" in part:
            lo, hi = part.split("-", 1)
            selected.update(str(n) for n in range(int(lo), int(hi) + 1))
        elif part:
            selected.add(part)
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--celex", help="CELEX number, e.g. 32002L0058")
    parser.add_argument("--regulation", help="Regulation key for the graph, e.g. EPRIVACY or GDPR")
    parser.add_argument("--label", help="Human-readable label, e.g. 'ePrivacy Directive 2002/58/EC'")
    parser.add_argument("--articles", help="Article selection, e.g. '1-15' or '5,9,22'. Default: all.")
    parser.add_argument("--from-file", help="Parse a local HTML file instead of fetching from CELLAR.")
    parser.add_argument("--llm", action="store_true",
                        help="Summarise articles with the configured Claude provider (marketing relevance, keywords, concept links).")
    parser.add_argument("--relevant-only", action="store_true",
                        help="With --llm: drop articles judged not marketing-relevant.")
    parser.add_argument("--merge", metavar="PROPOSAL_JSON",
                        help="Merge a reviewed proposal file into the knowledge graph and exit.")
    args = parser.parse_args()

    if args.merge:
        proposal = json.loads(Path(args.merge).read_text())
        added_nodes, added_edges = merge_proposal(proposal, config.KNOWLEDGE_DIR)
        print(f"Merged: {added_nodes} nodes, {added_edges} edges -> {config.KNOWLEDGE_DIR}")
        print("Restart the backend to index the new nodes.")
        return 0

    if not (args.celex and args.regulation and args.label):
        parser.error("--celex, --regulation and --label are required (unless using --merge)")

    if args.from_file:
        html = Path(args.from_file).read_text()
    else:
        html = fetch_act_html(args.celex)

    articles = split_articles(html)
    if not articles:
        logger.error("No articles found — the act's HTML structure may be unusual. "
                     "Save the HTML and inspect it, then retry with --from-file.")
        return 1
    logger.info("Parsed %d articles (%s … %s)", len(articles), articles[0].number, articles[-1].number)

    if args.articles:
        selection = _parse_article_selection(args.articles)
        articles = [a for a in articles if a.number in selection]
        logger.info("Selected %d articles: %s", len(articles), ", ".join(a.number for a in articles))

    existing_nodes = {
        n["id"]: n for n in json.loads((config.KNOWLEDGE_DIR / "nodes.json").read_text())
    }

    proposal = build_proposal(
        articles,
        celex=args.celex,
        regulation_key=args.regulation.upper(),
        regulation_label=args.label,
        existing_nodes=existing_nodes,
        use_llm=args.llm,
        only_marketing_relevant=args.relevant_only,
    )

    out_dir = config.KNOWLEDGE_DIR / "proposals"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"proposal-{args.celex}.json"
    out_path.write_text(json.dumps(proposal, indent=2, ensure_ascii=False) + "\n")

    print(f"\nProposal written: {out_path}")
    print(f"  nodes: {len(proposal['nodes'])}, edges: {len(proposal['edges'])}, "
          f"skipped: {len(proposal['skipped'])}")
    for item in proposal["skipped"]:
        print(f"  - skipped {item}")
    print("\nReview the file, then merge with:")
    print(f"  python -m app.ingest --merge {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
