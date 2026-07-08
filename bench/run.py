#!/usr/bin/env python3
"""Benchmark harness: replay the gold cases against a running instance and score it.

Usage:
    python bench/run.py --base-url http://localhost:8000
    python bench/run.py --base-url https://<railway-app> --runs 3 --concurrency 2
    python bench/run.py --only t1-detox-tea-influencer t3-true-scarcity

Each case in cases.jsonl is a CampaignSubmission plus gold labels:
    relevant          regulations triage MUST route (recall-scored; over-routing
                      is reported but not penalised — triage is inclusive by design)
    provisions        provision node ids the findings MUST cite (recall)
    acceptable_extra  additional provisions that are defensible citations —
                      not required, not counted as precision errors
    compliant         true for control cases; ANY finding of severity >= medium
                      (or overall risk >= medium) counts as a false positive
    min_risk          minimum acceptable overall_risk for violating cases

Scoring conventions:
    - a gold provision counts as found at any severity (even "low");
    - predicted findings below "medium" are never precision errors (advisory);
    - unexpected provisions (>= medium, outside gold + acceptable_extra) are
      listed per case so reviewers can promote them into the gold set.

Results are printed as a markdown scorecard and saved under bench/results/.
"""
import argparse
import asyncio
import itertools
import json
import sys
import time
from pathlib import Path

import httpx

BENCH_DIR = Path(__file__).parent
RISK_ORDER = {"compliant": 0, "low": 1, "medium": 2, "high": 3, "critical": 4, "unknown": -1}
ACTIONABLE = ("critical", "high", "medium")
REGULATIONS = ("AI_ACT", "GDPR", "DSA", "UCPD")


def load_cases(path: Path, only: list[str] | None) -> list[dict]:
    cases = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "duplicate case ids in cases.jsonl"
    if only:
        unknown = set(only) - set(ids)
        assert not unknown, f"unknown case ids: {sorted(unknown)}"
        cases = [c for c in cases if c["id"] in only]
    return cases


async def run_case(client: httpx.AsyncClient, base_url: str, campaign: dict) -> dict:
    """POST the campaign and read the SSE stream until the final report event."""
    report, engine = None, None
    async with client.stream("POST", f"{base_url}/api/analyses/stream", json=campaign) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if not line.startswith("data: "):
                continue
            event = json.loads(line[6:])
            if event.get("type") == "accepted":
                engine = event.get("engine")
            elif event.get("type") == "report":
                report = event["report"]
            elif event.get("type") == "error":
                raise RuntimeError(f"analysis failed: {event.get('message')}")
    if report is None:
        raise RuntimeError("stream ended without a report event")
    report["_engine"] = engine or report.get("engine")
    return report


def extract_predictions(report: dict) -> dict:
    triage = report.get("triage") or {}
    all_findings = [f for v in report.get("verdicts", []) for f in v.get("findings", [])]
    return {
        "routed": set(triage.get("regulations_to_check") or []),
        "found_any": {f["provision_id"] for f in all_findings},
        "found_actionable": {f["provision_id"] for f in all_findings if f.get("severity") in ACTIONABLE},
        "overall_risk": report.get("overall_risk", "unknown"),
    }


def score_case(case: dict, pred: dict) -> dict:
    gold = case["gold"]
    gold_relevant = set(gold.get("relevant") or [])
    gold_provisions = set(gold.get("provisions") or [])
    allowed = gold_provisions | set(gold.get("acceptable_extra") or [])

    missed_routing = gold_relevant - pred["routed"]
    over_routing = pred["routed"] - gold_relevant

    matched = gold_provisions & pred["found_any"]
    missed = gold_provisions - pred["found_any"]
    unexpected = pred["found_actionable"] - allowed

    risk_rank = RISK_ORDER.get(pred["overall_risk"], -1)
    if gold.get("compliant"):
        false_positive = bool(pred["found_actionable"]) or risk_rank >= RISK_ORDER["medium"]
        risk_ok = not false_positive
    else:
        false_positive = False
        risk_ok = risk_rank >= RISK_ORDER.get(gold.get("min_risk", "medium"), 2)

    return {
        "id": case["id"],
        "tier": case["tier"],
        "compliant_control": bool(gold.get("compliant")),
        "routing_missed": sorted(missed_routing),
        "routing_extra": sorted(over_routing),
        "provisions_matched": sorted(matched),
        "provisions_missed": sorted(missed),
        "provisions_unexpected": sorted(unexpected),
        "gold_provision_count": len(gold_provisions),
        "overall_risk": pred["overall_risk"],
        "min_risk": gold.get("min_risk"),
        "risk_ok": risk_ok,
        "false_positive": false_positive,
    }


def aggregate(rows: list[dict]) -> dict:
    violating = [r for r in rows if not r["compliant_control"]]
    controls = [r for r in rows if r["compliant_control"]]

    gold_total = sum(r["gold_provision_count"] for r in violating)
    matched_total = sum(len(r["provisions_matched"]) for r in violating)
    unexpected_total = sum(len(r["provisions_unexpected"]) for r in rows)

    return {
        "cases": len(rows),
        "engine": None,  # filled by caller
        "finding_recall": round(matched_total / gold_total, 3) if gold_total else None,
        "unexpected_findings": unexpected_total,
        "false_positives_on_controls": sum(1 for r in controls if r["false_positive"]),
        "controls": len(controls),
        "risk_calibration_pass": sum(1 for r in rows if r["risk_ok"]),
        "routing_missed_total": sum(len(r["routing_missed"]) for r in violating),
    }


def markdown_scorecard(summary: dict, rows: list[dict], stability: dict[str, float] | None) -> str:
    lines = [
        f"# Benchmark scorecard — engine: {summary['engine']}",
        "",
        f"- Cases run: **{summary['cases']}** ({summary['controls']} compliant controls)",
        f"- Gold-provision recall: **{summary['finding_recall']}**",
        f"- Missed triage routings: **{summary['routing_missed_total']}**",
        f"- Unexpected actionable findings (review these): **{summary['unexpected_findings']}**",
        f"- False positives on compliant controls: **{summary['false_positives_on_controls']}/{summary['controls']}**",
        f"- Risk calibration passed: **{summary['risk_calibration_pass']}/{summary['cases']}**",
        "",
        "| case | tier | risk (min) | ok | matched | missed | unexpected | routing missed |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        ok = "✅" if (r["risk_ok"] and not r["provisions_missed"] and not r["false_positive"]) else "❌"
        lines.append(
            f"| {r['id']} | {r['tier']} | {r['overall_risk']} ({r['min_risk']}) | {ok} "
            f"| {', '.join(r['provisions_matched']) or '—'} "
            f"| {', '.join(r['provisions_missed']) or '—'} "
            f"| {', '.join(r['provisions_unexpected']) or '—'} "
            f"| {', '.join(r['routing_missed']) or '—'} |"
        )
    if stability:
        lines += ["", "## Stability (mean pairwise Jaccard of finding sets across runs)", ""]
        lines += [f"- {cid}: {val}" for cid, val in sorted(stability.items())]
    return "\n".join(lines)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--cases", default=str(BENCH_DIR / "cases.jsonl"))
    parser.add_argument("--only", nargs="*", help="run only these case ids")
    parser.add_argument("--runs", type=int, default=1, help="repeat each case N times (stability)")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=600.0, help="per-case timeout in seconds")
    args = parser.parse_args()

    cases = load_cases(Path(args.cases), args.only)
    semaphore = asyncio.Semaphore(args.concurrency)
    engines: set[str] = set()
    reports: dict[str, list[dict | None]] = {c["id"]: [None] * args.runs for c in cases}

    async with httpx.AsyncClient(timeout=httpx.Timeout(args.timeout, connect=15.0)) as client:
        async def one(case: dict, run_idx: int) -> None:
            async with semaphore:
                started = time.monotonic()
                try:
                    report = await run_case(client, args.base_url.rstrip("/"), case["campaign"])
                except Exception as exc:
                    print(f"  ✗ {case['id']} run {run_idx + 1}: {exc}", file=sys.stderr)
                    return
                engines.add(report["_engine"])
                reports[case["id"]][run_idx] = report
                print(f"  ✓ {case['id']} run {run_idx + 1} "
                      f"({report.get('overall_risk')}, {time.monotonic() - started:.0f}s)")

        print(f"Running {len(cases)} case(s) × {args.runs} against {args.base_url} …")
        await asyncio.gather(*(one(c, i) for c in cases for i in range(args.runs)))

    failed = [cid for cid, runs in reports.items() if all(r is None for r in runs)]
    if failed:
        print(f"\n{len(failed)} case(s) produced no report: {failed}", file=sys.stderr)

    rows = []
    stability: dict[str, float] = {}
    for case in cases:
        runs = [r for r in reports[case["id"]] if r is not None]
        if not runs:
            continue
        rows.append(score_case(case, extract_predictions(runs[0])))
        if len(runs) > 1:
            sets = [extract_predictions(r)["found_any"] for r in runs]
            pairs = list(itertools.combinations(sets, 2))
            jaccard = [len(a & b) / len(a | b) if (a | b) else 1.0 for a, b in pairs]
            stability[case["id"]] = round(sum(jaccard) / len(jaccard), 3)

    if not rows:
        print("No results to score.", file=sys.stderr)
        return 1

    summary = aggregate(rows)
    summary["engine"] = ", ".join(sorted(engines)) or "unknown"
    scorecard = markdown_scorecard(summary, rows, stability or None)
    print("\n" + scorecard)

    results_dir = BENCH_DIR / "results"
    results_dir.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (results_dir / f"{stamp}.md").write_text(scorecard + "\n")
    (results_dir / f"{stamp}.json").write_text(json.dumps(
        {"summary": summary, "cases": rows, "stability": stability}, indent=2) + "\n")
    print(f"\nSaved bench/results/{stamp}.md and .json")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
