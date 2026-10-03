#!/usr/bin/env python3
"""Generate the paper's Table 1 from the committed benchmark result artifacts.

The table is derived from bench/results/*-results.json rather than transcribed
by hand, so every published number traces to a stored run (and its raw
outputs, which remain re-scorable with `run.py --rescore`).

    python bench/make_table1.py                  # markdown to stdout
    python bench/make_table1.py --csv            # csv instead
    python bench/make_table1.py --out docs/paper/table1.md

Rows are declared below in reporting order. Add a configuration by naming its
results file; nothing else needs to change.
"""
import argparse
import json
from pathlib import Path

BENCH_DIR = Path(__file__).parent
RESULTS = BENCH_DIR / "results"

# (row label, results file, evaluated subset) in reporting order.
ROWS = [
    ("A — retrieval only, no LLM", "A-20260808-114736-results.json", "full"),
    ("B — agentic, no citation validation", "B-20260808-114752-results.json", "full"),
    ("C — agentic, deployed default", "C-full-20260813-071439-results.json", "full"),
    ("E1 — single call, GPT-5.4", "E1-gpt54-2*-results.json", "full"),
    ("E2 — single call, GPT-5.6", "E2-gpt56-2*-results.json", "full"),
    ("C — deployed default (holdout)", "C-holdout-20260813-083740-results.json", "holdout"),
    ("D — deployed default + calibration (holdout)", "D-20260813-091230-results.json", "holdout"),
    ("E1 — single call, GPT-5.4 (holdout)", "E1-gpt54-holdout-*-results.json", "holdout"),
    ("E2 — single call, GPT-5.6 (holdout)", "E2-gpt56-holdout-*-results.json", "holdout"),
]

COLUMNS = [
    ("Configuration", "{label}"),
    ("n", "{cases}"),
    ("Provision recall ↑", "{recall}"),
    ("Unexpected findings ↓ (per case)", "{unexpected} ({unexpected_per_case})"),
    ("Control FP ↓", "{fp}/{controls}"),
    ("Risk calibration ↑", "{risk}/{cases}"),
    ("Stability ↑", "{stability}"),
    ("Invalid citations ↓", "{invalid}"),
    ("Latency (s)", "{latency}"),
]


def load(path: Path) -> dict:
    data = json.loads(path.read_text())
    summary = data["summary"]
    stability = data.get("stability") or {}
    mean_stability = (summary.get("stability_mean")
                      or (round(sum(stability.values()) / len(stability), 3) if stability else None))
    cases = summary["cases"]
    unexpected = summary["unexpected_findings"]
    return {
        "cases": cases,
        "recall": f"{summary['finding_recall']:.3f}" if summary.get("finding_recall") is not None else "—",
        "unexpected": unexpected,
        "unexpected_per_case": f"{unexpected / cases:.2f}" if cases else "—",
        "fp": summary["false_positives_on_controls"],
        "controls": summary["controls"],
        "risk": summary["risk_calibration_pass"],
        "stability": f"{mean_stability:.3f}" if mean_stability is not None else "—",
        "invalid": summary["invalid_citations_total"] if summary.get("invalid_citations_total") is not None else 0,
        "latency": (f"{summary['mean_latency_s']:.1f}" if summary.get("mean_latency_s")
                    else ("n/a" if "chat-ui" in (summary.get("engine") or "") else "<1")),
        "engine": summary.get("engine") or "—",
        "model": (data.get("job") or {}).get("model") or "n/a (no LLM)",
        "cases_sha256": (data.get("job") or {}).get("cases_sha256") or "repo cases.jsonl",
        "job": (data.get("job") or {}).get("id", path.stem),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csv", action="store_true", help="emit CSV instead of markdown")
    parser.add_argument("--out", help="write to this file instead of stdout")
    args = parser.parse_args()

    import glob
    rows = []
    for label, filename, subset in ROWS:
        matches = sorted(glob.glob(str(RESULTS / filename)))
        if not matches:
            print(f"missing results file for pattern: {filename}")
            return 1
        rows.append({"label": label, "subset": subset, **load(Path(matches[-1]))})

    headers = [name for name, _ in COLUMNS]
    body = [[template.format(**row) for _, template in COLUMNS] for row in rows]

    if args.csv:
        import csv
        import io
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(headers)
        writer.writerows(body)
        text = buf.getvalue()
    else:
        lines = [
            "**Table 1.** Evaluation of the four configurations on the gold benchmark "
            "(52 campaigns, 97 must-find provisions, 7 compliant controls; three runs per "
            "campaign). Configurations C (holdout) and D are evaluated on the 15 held-out "
            "campaigns (2 controls, 26 must-find provisions) excluded from calibration-rule "
            "distillation; D is therefore compared against the C (holdout) row, not the full "
            "set. Arrows mark the desirable direction. Provision recall counts must-find "
            "provisions cited at any severity; unexpected findings are actionable "
            "(\u2265 medium) citations outside the must-find and defensible-extra sets; "
            "stability is the mean pairwise Jaccard of finding sets across the three runs; "
            "invalid citations are those the validation layer removes (unknown identifiers or "
            "cross-regulation citations), zero by construction in A, C and D.",
            "",
            "| " + " | ".join(headers) + " |",
            "|" + "|".join("---" for _ in headers) + "|",
        ]
        lines += ["| " + " | ".join(cells) + " |" for cells in body]
        lines += ["", "Provenance:", ""]
        for row in rows:
            lines.append(f"- **{row['label']}** — job `{row['job']}`, engine `{row['engine']}`, "
                         f"model `{row['model']}`, case set `{row['cases_sha256']}`")
        text = "\n".join(lines) + "\n"

    if args.out:
        Path(args.out).write_text(text)
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
