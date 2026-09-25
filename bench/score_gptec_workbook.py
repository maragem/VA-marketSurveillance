#!/usr/bin/env python3
"""Score a filled-in GPT@EC evaluation workbook.

Reads the pasted chat answers, scores them with the SAME code that scored the
automated configurations (bench/run.py), and writes the standard artifact
triple into bench/results/ so the result can be added to Table 1 by
bench/make_table1.py.

    python bench/score_gptec_workbook.py bench/gptec-evaluation.xlsx
    python bench/score_gptec_workbook.py wb.xlsx --label "E-gpt5" --holdout

Malformed answers are reported, never silently repaired: a reply that is not
usable JSON is scored as a run that produced no findings, which is what it is.
"""
import argparse
import importlib.util
import itertools
import json
import re
import time
from pathlib import Path

from openpyxl import load_workbook

BENCH = Path(__file__).parent
RESULTS = BENCH / "results"


def load_scoring():
    spec = importlib.util.spec_from_file_location("bench_run_scoring", BENCH / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.I)


def parse_answer(raw: str):
    """Extract the JSON object from a pasted chat reply.

    Tolerates code fences and surrounding prose (both are protocol violations
    the instructions warn against, but they do not invalidate the legal
    content of the answer). Returns (payload, problem_description).
    """
    if raw is None:
        return None, "empty"
    text = str(raw).strip()
    if not text:
        return None, "empty"
    candidate = _FENCE.sub("", text).strip()
    try:
        return json.loads(candidate), None
    except ValueError:
        pass
    # Fall back to the outermost {...} span.
    start, end = candidate.find("{"), candidate.rfind("}")
    if start != -1 and end > start:
        try:
            payload = json.loads(candidate[start:end + 1])
            return payload, "surrounding prose stripped"
        except ValueError:
            pass
    return None, "not parseable as JSON"


def to_report(payload: dict) -> dict:
    """Shape a chat answer like an engine report so the scorer can read it."""
    findings = []
    for f in payload.get("findings") or []:
        if not isinstance(f, dict) or not f.get("provision_id"):
            continue
        findings.append({
            "provision_id": str(f.get("provision_id")).strip(),
            "regulation": str(f.get("regulation") or "").strip().upper().replace(" ", "_"),
            "severity": str(f.get("severity") or "medium").strip().lower(),
            "rationale": f.get("rationale") or "",
            "evidence_quote": f.get("evidence_quote"),
        })
    routed = [str(r).strip().upper().replace(" ", "_")
              for r in (payload.get("regulations_to_check") or [])]
    return {
        "triage": {"regulations_to_check": routed},
        "verdicts": [{"regulation": "MIXED", "status": "attention", "findings": findings}],
        "overall_risk": str(payload.get("overall_risk") or "unknown").strip().lower(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("workbook")
    parser.add_argument("--label", help="row label for Table 1 (default: derived from MODEL_NAME)")
    parser.add_argument("--holdout", action="store_true",
                        help="score only the held-out campaigns (comparable with the C/D holdout rows)")
    parser.add_argument("--cases", default=str(BENCH / "cases.jsonl"))
    args = parser.parse_args()

    scoring = load_scoring()
    provisions = scoring.load_provisions()
    cases = {c["id"]: c for c in scoring.load_cases(Path(args.cases), None)}
    holdout = scoring.load_holdout()

    ws = load_workbook(args.workbook, data_only=True)["Run sheet"]
    header = [c.value for c in ws[1]]
    col = {name: i for i, name in enumerate(header)}

    def get(row, prefix):
        for name, idx in col.items():
            if name and str(name).startswith(prefix):
                return row[idx]
        return None

    answers = {}          # case_id -> {run_no: report}
    problems, models, skipped = [], set(), 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        case_id = row[col["CASE_ID"]]
        if not case_id or str(case_id).startswith("EXAMPLE"):
            continue
        raw = get(row, "RESPONSE_JSON")
        if raw is None or not str(raw).strip():
            skipped += 1
            continue
        if case_id not in cases:
            problems.append((case_id, "?", "unknown campaign id — not in cases.jsonl"))
            continue
        if args.holdout and case_id not in holdout:
            continue
        run_no = get(row, "RUN_NO") or 1
        try:
            run_no = int(run_no)
        except (TypeError, ValueError):
            problems.append((case_id, run_no, "RUN_NO is not a number"))
            continue
        model = (get(row, "MODEL_NAME") or "").strip()
        if model:
            models.add(model)
        else:
            problems.append((case_id, run_no, "MODEL_NAME missing"))
        payload, problem = parse_answer(raw)
        if payload is None:
            problems.append((case_id, run_no, problem))
            payload = {}
        elif problem:
            problems.append((case_id, run_no, problem))
        answers.setdefault(case_id, {})[run_no] = to_report(payload)

    if not answers:
        print("No responses found in the workbook.")
        return 1

    scored_ids = [cid for cid in cases if cid in answers]
    if args.holdout:
        scored_ids = [cid for cid in scored_ids if cid in holdout]

    rows, stability, invalid_detail = [], {}, []
    max_runs = max(len(v) for v in answers.values())
    for cid in scored_ids:
        runs = [answers[cid][k] for k in sorted(answers[cid])]
        pred = scoring.extract_predictions(runs[0], provisions)
        row = scoring.score_case(cases[cid], pred)
        rows.append(row)
        for f in runs[0]["verdicts"][0]["findings"]:
            if provisions.get(f["provision_id"]) != f["regulation"]:
                invalid_detail.append((cid, f["provision_id"], f["regulation"] or "(none)"))
        if len(runs) > 1:
            sets = [scoring.extract_predictions(r, provisions)["found_any"] for r in runs]
            pairs = list(itertools.combinations(sets, 2))
            jaccard = [len(a & b) / len(a | b) if (a | b) else 1.0 for a, b in pairs]
            stability[cid] = round(sum(jaccard) / len(jaccard), 3)

    summary = scoring.aggregate(rows)
    model_label = ", ".join(sorted(models)) or "unknown"
    summary["engine"] = f"chat-ui ({model_label})"
    summary["mean_latency_s"] = None
    if stability:
        summary["stability_mean"] = round(sum(stability.values()) / len(stability), 3)

    scorecard = scoring.markdown_scorecard(summary, rows, stability or None)
    label = args.label or f"E-{model_label.replace(' ', '-')}"
    stamp = f"{label}{'-holdout' if args.holdout else ''}-{time.strftime('%Y%m%d-%H%M%S')}"
    RESULTS.mkdir(exist_ok=True)
    header_line = (f"Configuration: E — single-call chat UI (GPT@EC) · model: {model_label} · "
                   f"campaigns scored: {len(rows)} · runs/campaign: up to {max_runs} · "
                   f"manual evaluation\n\n")
    (RESULTS / f"{stamp}-scorecard.md").write_text(header_line + scorecard + "\n")
    (RESULTS / f"{stamp}-results.json").write_text(json.dumps({
        "job": {"id": stamp, "config": "E", "label": f"E — single-call chat UI ({model_label})",
                "model": model_label, "runs": max_runs,
                "cases_sha256": "manual (see workbook)"},
        "summary": summary, "cases": rows, "stability": stability}, indent=2) + "\n")
    with open(RESULTS / f"{stamp}-reports.jsonl", "w") as f:
        for cid in scored_ids:
            for run_no in sorted(answers[cid]):
                report = dict(answers[cid][run_no])
                report["_engine"] = f"chat-ui ({model_label})"
                f.write(json.dumps({"case_id": cid, "run": run_no, "report": report},
                                   ensure_ascii=False) + "\n")

    print(scorecard)
    print(f"\nModel(s): {model_label}")
    print(f"Campaigns scored: {len(rows)}"
          + (f" (held-out subset)" if args.holdout else "")
          + f" · rows without an answer: {skipped}")
    missing = [cid for cid in (holdout if args.holdout else cases) if cid not in answers]
    if missing:
        print(f"No answer yet for {len(missing)} campaign(s): {', '.join(sorted(missing)[:8])}"
              + (" …" if len(missing) > 8 else ""))
    if invalid_detail:
        print(f"\nInvalid citations (outside the provision vocabulary or mis-attributed): "
              f"{len(invalid_detail)}")
        for cid, pid, reg in invalid_detail:
            print(f"  {cid}: {pid} cited as {reg}")
    if problems:
        print(f"\nData problems ({len(problems)}) — inspect these rows in the workbook:")
        for cid, run_no, why in problems:
            print(f"  {cid} run {run_no}: {why}")
    print(f"\nSaved bench/results/{stamp}-{{scorecard.md, results.json, reports.jsonl}}")
    print("Add to Table 1 by listing the results file in bench/make_table1.py ROWS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
