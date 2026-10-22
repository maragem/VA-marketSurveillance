#!/usr/bin/env python3
"""Statistics for the evaluation section: recall intervals and paired tests.

Reviewers of a 52/15-campaign benchmark will ask what the point estimates are
worth, so the reported numbers carry intervals. Everything here is computed
from the committed result artifacts; no dependency beyond the standard library.

    python bench/make_stats.py                 # text report
    python bench/make_stats.py --json          # machine-readable
"""
import argparse
import glob
import itertools
import json
import math
import random
from pathlib import Path

BENCH = Path(__file__).parent
RESULTS = BENCH / "results"

CONFIGS = [
    ("A — retrieval only", "A-20260808-114736-results.json"),
    ("B — no citation validation", "B-20260808-114752-results.json"),
    ("C — deployed default", "C-full-20260813-071439-results.json"),
    ("E1 — gpt-5.4, single call", "E1-gpt54-2*-results.json"),
    ("E2 — gpt-5.6, single call", "E2-gpt56-2*-results.json"),
    ("E3 — gpt-oss-120b, single call", "E3-gptoss120b-2*-results.json"),
]
HOLDOUT_CONFIGS = [
    ("C — deployed default (holdout)", "C-holdout-20260813-083740-results.json"),
    ("D — + calibration (holdout)", "D-20260813-091230-results.json"),
    ("E1 — gpt-5.4 (holdout)", "E1-gpt54-holdout-*-results.json"),
    ("E2 — gpt-5.6 (holdout)", "E2-gpt56-holdout-*-results.json"),
    ("E3 — gpt-oss-120b (holdout)", "E3-gptoss120b-holdout-*-results.json"),
]


def resolve(pattern):
    matches = sorted(glob.glob(str(RESULTS / pattern)))
    if not matches:
        raise SystemExit(f"missing results file for pattern {pattern}")
    return Path(matches[-1])


def wilson(hits: int, total: int, z: float = 1.96):
    """Wilson score interval — appropriate for proportions near 1, where the
    normal approximation gives a nonsensical zero-width interval."""
    if total == 0:
        return (None, None)
    p = hits / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def recall_counts(path: Path):
    rows = json.load(open(path))["cases"]
    violating = [r for r in rows if not r["compliant_control"]]
    hits = sum(len(r["provisions_matched"]) for r in violating)
    total = sum(r["gold_provision_count"] for r in violating)
    return hits, total


def per_campaign_unexpected(path: Path):
    return {r["id"]: len(r["provisions_unexpected"]) for r in json.load(open(path))["cases"]}


def wilcoxon_signed_rank(diffs):
    """Exact two-sided Wilcoxon signed-rank test (small samples, no scipy)."""
    nz = [d for d in diffs if d != 0]
    n = len(nz)
    if n == 0:
        return None, 1.0
    ranks = {}
    order = sorted(range(n), key=lambda i: abs(nz[i]))
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(nz[order[j + 1]]) == abs(nz[order[i]]):
            j += 1
        avg = (i + j + 2) / 2          # average rank for ties (1-based)
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    w_plus = sum(ranks[i] for i in range(n) if nz[i] > 0)
    w_minus = sum(ranks[i] for i in range(n) if nz[i] < 0)
    w = min(w_plus, w_minus)
    # exact null distribution over all sign assignments
    count = 0
    total = 2 ** n
    rank_list = [ranks[i] for i in range(n)]
    for signs in itertools.product((0, 1), repeat=n):
        s = sum(r for r, g in zip(rank_list, signs) if g)
        if min(s, sum(rank_list) - s) <= w:
            count += 1
    return w, min(1.0, count / total)


def bootstrap_mean_diff(pairs, iters=20000, seed=11):
    """Percentile bootstrap CI for the paired mean difference (before - after)."""
    rng = random.Random(seed)
    diffs = [a - b for a, b in pairs]
    n = len(diffs)
    means = []
    for _ in range(iters):
        means.append(sum(diffs[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    return (sum(diffs) / n, means[int(0.025 * iters)], means[int(0.975 * iters)])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    out = {"recall": [], "calibration_effect": {}, "model_comparison": {}}

    for label, pattern in CONFIGS + HOLDOUT_CONFIGS:
        hits, total = recall_counts(resolve(pattern))
        lo, hi = wilson(hits, total)
        out["recall"].append({"config": label, "hits": hits, "total": total,
                              "recall": round(hits / total, 3) if total else None,
                              "ci95": [round(lo, 3), round(hi, 3)]})

    # Calibration effect on the holdout: paired by campaign.
    c_hold = per_campaign_unexpected(resolve(HOLDOUT_CONFIGS[0][1]))
    d_hold = per_campaign_unexpected(resolve(HOLDOUT_CONFIGS[1][1]))
    shared = sorted(set(c_hold) & set(d_hold))
    pairs = [(c_hold[k], d_hold[k]) for k in shared]
    mean_diff, lo, hi = bootstrap_mean_diff(pairs)
    w, p = wilcoxon_signed_rank([a - b for a, b in pairs])
    improved = sum(1 for a, b in pairs if b < a)
    worsened = sum(1 for a, b in pairs if b > a)
    out["calibration_effect"] = {
        "campaigns": len(pairs),
        "unexpected_before": sum(a for a, _ in pairs),
        "unexpected_after": sum(b for _, b in pairs),
        "reduction_pct": round(100 * (1 - sum(b for _, b in pairs) / sum(a for a, _ in pairs)), 1),
        "mean_per_campaign_before": round(sum(a for a, _ in pairs) / len(pairs), 2),
        "mean_per_campaign_after": round(sum(b for _, b in pairs) / len(pairs), 2),
        "mean_reduction_per_campaign": round(mean_diff, 2),
        "bootstrap_ci95": [round(lo, 2), round(hi, 2)],
        "wilcoxon_W": w, "wilcoxon_p_exact": round(p, 5),
        "campaigns_improved": improved, "campaigns_worsened": worsened,
        "campaigns_unchanged": len(pairs) - improved - worsened,
    }

    # C vs the external single-call models on must-find recall (same campaigns).
    c_full = resolve(CONFIGS[2][1])
    for label, pattern in (CONFIGS[3], CONFIGS[4], CONFIGS[5]):
        rows_c = {r["id"]: r for r in json.load(open(c_full))["cases"]}
        rows_e = {r["id"]: r for r in json.load(open(resolve(pattern)))["cases"]}
        shared = sorted(set(rows_c) & set(rows_e))
        c_hits = sum(len(rows_c[k]["provisions_matched"]) for k in shared
                     if not rows_c[k]["compliant_control"])
        e_hits = sum(len(rows_e[k]["provisions_matched"]) for k in shared
                     if not rows_e[k]["compliant_control"])
        tot = sum(rows_c[k]["gold_provision_count"] for k in shared
                  if not rows_c[k]["compliant_control"])
        # McNemar on discordant must-find outcomes
        b = c = 0
        for k in shared:
            gold = set(rows_c[k]["provisions_matched"]) | set(rows_c[k]["provisions_missed"])
            for p_id in gold:
                in_c = p_id in rows_c[k]["provisions_matched"]
                in_e = p_id in rows_e[k]["provisions_matched"]
                if in_c and not in_e:
                    b += 1
                elif in_e and not in_c:
                    c += 1
        n = b + c
        # exact binomial two-sided p for McNemar
        if n:
            tail = sum(math.comb(n, k) for k in range(0, min(b, c) + 1)) / 2 ** n
            p_val = min(1.0, 2 * tail)
        else:
            p_val = 1.0
        out["model_comparison"][label] = {
            "must_finds": tot, "config_C_found": c_hits, "external_found": e_hits,
            "found_only_by_C": b, "found_only_by_external": c,
            "mcnemar_exact_p": float(f"{p_val:.3g}"),
        }

    if args.json:
        print(json.dumps(out, indent=2))
        return 0

    print("MUST-FIND RECALL WITH 95% WILSON INTERVALS")
    for r in out["recall"]:
        print(f"  {r['config']:34} {r['hits']:3}/{r['total']:<3} = {r['recall']:.3f}  "
              f"[{r['ci95'][0]:.3f}, {r['ci95'][1]:.3f}]")
    ce = out["calibration_effect"]
    print(f"\nCALIBRATION EFFECT ON THE HELD-OUT SPLIT (n={ce['campaigns']} campaigns, paired)")
    print(f"  unexpected findings: {ce['unexpected_before']} -> {ce['unexpected_after']} "
          f"({ce['reduction_pct']}% reduction)")
    print(f"  per campaign: {ce['mean_per_campaign_before']} -> {ce['mean_per_campaign_after']}")
    print(f"  mean reduction {ce['mean_reduction_per_campaign']} per campaign, "
          f"bootstrap 95% CI [{ce['bootstrap_ci95'][0]}, {ce['bootstrap_ci95'][1]}]")
    print(f"  campaigns improved {ce['campaigns_improved']}, worsened {ce['campaigns_worsened']}, "
          f"unchanged {ce['campaigns_unchanged']}")
    print(f"  Wilcoxon signed-rank W={ce['wilcoxon_W']}, exact two-sided p={ce['wilcoxon_p_exact']}")
    print("\nCONFIGURATION C vs EXTERNAL SINGLE-CALL MODELS (paired on must-find provisions)")
    for label, m in out["model_comparison"].items():
        print(f"  {label}")
        print(f"    must-finds {m['must_finds']} · found by C {m['config_C_found']} · "
              f"found by external {m['external_found']}")
        print(f"    found only by C: {m['found_only_by_C']} · only by external: "
              f"{m['found_only_by_external']} · McNemar exact p={m['mcnemar_exact_p']:.3g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
