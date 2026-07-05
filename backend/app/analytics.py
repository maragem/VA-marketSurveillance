"""Aggregations over stored reports for the analytics dashboard.

Everything is computed in memory from the report payloads — the corpus is a
single-team decision-support store (thousands of small JSON documents), so a
full scan per request is simpler and fast enough; swap for SQL aggregates if
the store ever moves to Postgres.
"""
from collections import Counter, defaultdict

from . import config

RISK_ORDER = ["compliant", "low", "medium", "high", "critical", "unknown"]
SEVERITY_ORDER = ["info", "low", "medium", "high", "critical"]


def build_analytics(reports: list[dict]) -> dict:
    completed = [r for r in reports if r.get("status") == "completed"]

    risk_counts: Counter = Counter()
    findings_by_regulation: Counter = Counter()
    severity_by_regulation: dict[str, Counter] = defaultdict(Counter)
    provision_counts: Counter = Counter()
    provision_titles: dict[str, str] = {}
    channel_counts: Counter = Counter()
    channel_high_risk: Counter = Counter()
    by_day: dict[str, Counter] = defaultdict(Counter)
    engine_counts: Counter = Counter()
    total_findings = 0

    for report in completed:
        risk = report.get("overall_risk", "unknown")
        risk_counts[risk] += 1
        engine_counts[report.get("engine", "agentic")] += 1

        day = (report.get("created_at") or "")[:10]
        if day:
            by_day[day]["count"] += 1
            if risk in ("high", "critical"):
                by_day[day]["high"] += 1

        for channel in report.get("campaign", {}).get("channels", []):
            channel = channel.strip().lower()
            if not channel:
                continue
            channel_counts[channel] += 1
            if risk in ("high", "critical"):
                channel_high_risk[channel] += 1

        for verdict in report.get("verdicts", []):
            regulation = verdict.get("regulation", "?")
            for finding in verdict.get("findings", []):
                total_findings += 1
                findings_by_regulation[regulation] += 1
                severity_by_regulation[regulation][finding.get("severity", "medium")] += 1
                ref = finding.get("provision_ref", "?")
                provision_counts[ref] += 1
                provision_titles.setdefault(ref, finding.get("title", ""))

    n = len(completed)
    high_or_critical = risk_counts.get("high", 0) + risk_counts.get("critical", 0)

    return {
        "totals": {
            "reports": n,
            "findings": total_findings,
            "high_or_critical_pct": round(100 * high_or_critical / n) if n else 0,
            "agentic_pct": round(100 * engine_counts.get("agentic", 0) / n) if n else 0,
        },
        "risk_distribution": [
            {"risk": risk, "count": risk_counts.get(risk, 0)}
            for risk in RISK_ORDER
            if risk_counts.get(risk, 0) or risk != "unknown"
        ],
        "findings_by_regulation": [
            {
                "regulation": regulation,
                "label": config.REGULATION_LABELS.get(regulation, regulation).split("(")[0].strip(),
                "count": findings_by_regulation.get(regulation, 0),
                "severities": {
                    severity: severity_by_regulation[regulation].get(severity, 0)
                    for severity in SEVERITY_ORDER
                },
            }
            for regulation in config.REGULATIONS
        ],
        "top_provisions": [
            {"ref": ref, "title": provision_titles.get(ref, ""), "count": count}
            for ref, count in provision_counts.most_common(8)
        ],
        "timeline": [
            {"date": day, "count": counters["count"], "high": counters["high"]}
            for day, counters in sorted(by_day.items())
        ][-30:],
        "channels": [
            {"channel": channel, "count": count, "high": channel_high_risk.get(channel, 0)}
            for channel, count in channel_counts.most_common(8)
        ],
    }
