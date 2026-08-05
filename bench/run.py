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


def load_holdout() -> set[str]:
    path = BENCH_DIR / "holdout.json"
    if not path.exists():
        return set()
    return set(json.loads(path.read_text()).get("holdout", []))


def load_provisions() -> dict[str, str] | None:
    """provision id -> regulation, from the knowledge graph (for detecting
    citations that validation would normally remove — configuration B)."""
    path = BENCH_DIR.parent / "knowledge" / "nodes.json"
    if not path.exists():
        return None
    return {n["id"]: n["regulation"] for n in json.loads(path.read_text())
            if n.get("type") == "provision"}


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


def extract_predictions(report: dict, provisions: dict[str, str] | None) -> dict:
    triage = report.get("triage") or {}
    all_findings = [f for v in report.get("verdicts", []) for f in v.get("findings", [])]
    invalid = None
    if provisions is not None:
        # Citations validation would remove: unknown ids, non-provisions, or a
        # provision belonging to another regulation than the citing agent's.
        invalid = sum(1 for f in all_findings
                      if provisions.get(f["provision_id"]) != f.get("regulation"))
    return {
        "routed": set(triage.get("regulations_to_check") or []),
        "found_any": {f["provision_id"] for f in all_findings},
        "found_actionable": {f["provision_id"] for f in all_findings if f.get("severity") in ACTIONABLE},
        "overall_risk": report.get("overall_risk", "unknown"),
        "invalid_citations": invalid,
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
        "invalid_citations": pred.get("invalid_citations"),
    }


def aggregate(rows: list[dict]) -> dict:
    violating = [r for r in rows if not r["compliant_control"]]
    controls = [r for r in rows if r["compliant_control"]]

    gold_total = sum(r["gold_provision_count"] for r in violating)
    matched_total = sum(len(r["provisions_matched"]) for r in violating)
    unexpected_total = sum(len(r["provisions_unexpected"]) for r in rows)

    invalid_counts = [r["invalid_citations"] for r in rows if r["invalid_citations"] is not None]
    return {
        "cases": len(rows),
        "engine": None,  # filled by caller
        "finding_recall": round(matched_total / gold_total, 3) if gold_total else None,
        "unexpected_findings": unexpected_total,
        "false_positives_on_controls": sum(1 for r in controls if r["false_positive"]),
        "controls": len(controls),
        "risk_calibration_pass": sum(1 for r in rows if r["risk_ok"]),
        "routing_missed_total": sum(len(r["routing_missed"]) for r in violating),
        "invalid_citations_total": sum(invalid_counts) if invalid_counts else None,
        "mean_latency_s": None,  # filled by caller
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
    ]
    if summary.get("invalid_citations_total") is not None:
        lines.append(f"- Invalid citations surviving to reports (would be removed by validation): "
                     f"**{summary['invalid_citations_total']}**")
    if summary.get("mean_latency_s") is not None:
        lines.append(f"- Mean latency per case: **{summary['mean_latency_s']}s**")
    lines += [
        "",
        "| case | tier | risk (min) | ok | matched | missed | unexpected | routing missed | invalid | s |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        ok = "✅" if (r["risk_ok"] and not r["provisions_missed"] and not r["false_positive"]) else "❌"
        lines.append(
            f"| {r['id']} | {r['tier']} | {r['overall_risk']} ({r['min_risk']}) | {ok} "
            f"| {', '.join(r['provisions_matched']) or '—'} "
            f"| {', '.join(r['provisions_missed']) or '—'} "
            f"| {', '.join(r['provisions_unexpected']) or '—'} "
            f"| {', '.join(r['routing_missed']) or '—'} "
            f"| {r['invalid_citations'] if r['invalid_citations'] is not None else '—'} "
            f"| {r.get('latency_s', '—')} |"
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
    holdout_group = parser.add_mutually_exclusive_group()
    holdout_group.add_argument("--holdout", action="store_true",
                               help="run only the held-out subset (bench/holdout.json) — use for configuration D")
    holdout_group.add_argument("--exclude-holdout", action="store_true",
                               help="run only calibration-visible cases (complement of bench/holdout.json)")
    parser.add_argument("--rescore", metavar="REPORTS_JSONL",
                        help="score a stored -reports.jsonl against the CURRENT gold labels "
                             "instead of running the engine (use after relabelling)")
    args = parser.parse_args()

    cases = load_cases(Path(args.cases), args.only)
    if args.holdout or args.exclude_holdout:
        holdout = load_holdout()
        assert holdout, "bench/holdout.json missing or empty"
        cases = [c for c in cases if (c["id"] in holdout) == args.holdout]
        print(f"{'Held-out' if args.holdout else 'Calibration-visible'} subset: {len(cases)} case(s)")
    provisions = load_provisions()
    if provisions is None:
        print("knowledge/nodes.json not found — invalid-citation detection disabled", file=sys.stderr)
    semaphore = asyncio.Semaphore(args.concurrency)
    engines: set[str] = set()
    reports: dict[str, list[dict | None]] = {c["id"]: [None] * args.runs for c in cases}
    latencies: dict[str, list[float]] = {c["id"]: [] for c in cases}

    if args.rescore:
        stored: dict[str, list[dict]] = {}
        for line in Path(args.rescore).read_text().splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            stored.setdefault(entry["case_id"], []).append(entry["report"])
        case_ids = {c["id"] for c in cases}
        reports = {cid: runs for cid, runs in stored.items() if cid in case_ids}
        for runs in reports.values():
            for report in runs:
                engines.add(report.get("_engine") or report.get("engine") or "unknown")
        missing = case_ids - set(reports)
        print(f"Re-scoring {sum(len(r) for r in reports.values())} stored report(s) "
              f"for {len(reports)} case(s) against the current gold labels"
              + (f" — no stored output for: {', '.join(sorted(missing))}" if missing else ""))
        cases = [c for c in cases if c["id"] in reports]
        latencies = {c["id"]: [] for c in cases}
        return score_and_save(args, cases, reports, latencies, engines, provisions)

    async with httpx.AsyncClient(timeout=httpx.Timeout(args.timeout, connect=15.0)) as client:
        async def one(case: dict, run_idx: int) -> None:
            async with semaphore:
                started = time.monotonic()
                try:
                    report = await run_case(client, args.base_url.rstrip("/"), case["campaign"])
                except Exception as exc:
                    print(f"  ✗ {case['id']} run {run_idx + 1}: {exc}", file=sys.stderr)
                    return
                elapsed = time.monotonic() - started
                engines.add(report["_engine"])
                reports[case["id"]][run_idx] = report
                latencies[case["id"]].append(elapsed)
                print(f"  ✓ {case['id']} run {run_idx + 1} "
                      f"({report.get('overall_risk')}, {elapsed:.0f}s)")

        print(f"Running {len(cases)} case(s) × {args.runs} against {args.base_url} …")
        await asyncio.gather(*(one(c, i) for c in cases for i in range(args.runs)))

    failed = [cid for cid, runs in reports.items() if all(r is None for r in runs)]
    if failed:
        print(f"\n{len(failed)} case(s) produced no report: {failed}", file=sys.stderr)

    return score_and_save(args, cases, reports, latencies, engines, provisions)


def score_and_save(args, cases, reports, latencies, engines, provisions) -> int:
    rows = []
    stability: dict[str, float] = {}
    for case in cases:
        runs = [r for r in reports[case["id"]] if r is not None]
        if not runs:
            continue
        row = score_case(case, extract_predictions(runs[0], provisions))
        if latencies.get(case["id"]):
            row["latency_s"] = round(sum(latencies[case["id"]]) / len(latencies[case["id"]]), 1)
        rows.append(row)
        if len(runs) > 1:
            sets = [extract_predictions(r, provisions)["found_any"] for r in runs]
            pairs = list(itertools.combinations(sets, 2))
            jaccard = [len(a & b) / len(a | b) if (a | b) else 1.0 for a, b in pairs]
            stability[case["id"]] = round(sum(jaccard) / len(jaccard), 3)

    if not rows:
        print("No results to score.", file=sys.stderr)
        return 1

    summary = aggregate(rows)
    summary["engine"] = ", ".join(sorted(engines)) or "unknown"
    all_latencies = [s for values in latencies.values() for s in values]
    if all_latencies:
        summary["mean_latency_s"] = round(sum(all_latencies) / len(all_latencies), 1)
    scorecard = markdown_scorecard(summary, rows, stability or None)
    print("\n" + scorecard)

    results_dir = BENCH_DIR / "results"
    results_dir.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S") + ("-rescored" if args.rescore else "")
    (results_dir / f"{stamp}.md").write_text(scorecard + "\n")
    (results_dir / f"{stamp}.json").write_text(json.dumps(
        {"summary": summary, "cases": rows, "stability": stability}, indent=2) + "\n")
    saved = f"bench/results/{stamp}.md and .json"
    if not args.rescore:
        # Raw reports: relabelling the gold set later means re-scoring these
        # stored outputs (--rescore) instead of re-paying for inference.
        with open(results_dir / f"{stamp}-reports.jsonl", "w") as f:
            for case_id, case_runs in reports.items():
                for run_idx, report in enumerate(case_runs):
                    if report is not None:
                        f.write(json.dumps({"case_id": case_id, "run": run_idx + 1,
                                            "report": report}, ensure_ascii=False) + "\n")
        saved += f" and {stamp}-reports.jsonl (raw outputs for --rescore)"
    print(f"\nSaved {saved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
