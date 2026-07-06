"""Diff between a re-analysis and its parent report.

Findings are matched by (regulation, provision_id): a provision cited in the
parent but not in the child is resolved; cited in both, remaining (severity
may still have moved); cited only in the child, new.
"""
from .models import AnalysisReport, Finding


def _findings_by_key(report: AnalysisReport) -> dict[tuple[str, str], Finding]:
    result: dict[tuple[str, str], Finding] = {}
    for verdict in report.verdicts:
        for finding in verdict.findings:
            key = (finding.regulation, finding.provision_id)
            # keep the most severe citation of a provision
            order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
            existing = result.get(key)
            if existing is None or order.get(finding.severity, 9) < order.get(existing.severity, 9):
                result[key] = finding
    return result


def build_diff(parent: AnalysisReport, current: AnalysisReport) -> dict:
    parent_findings = _findings_by_key(parent)
    current_findings = _findings_by_key(current)

    resolved = [
        parent_findings[key].model_dump()
        for key in sorted(parent_findings.keys() - current_findings.keys())
    ]
    new = [
        current_findings[key].model_dump()
        for key in sorted(current_findings.keys() - parent_findings.keys())
    ]
    remaining = []
    for key in sorted(parent_findings.keys() & current_findings.keys()):
        entry = current_findings[key].model_dump()
        entry["previous_severity"] = parent_findings[key].severity
        remaining.append(entry)

    return {
        "parent": {
            "id": parent.id,
            "created_at": parent.created_at,
            "overall_risk": parent.overall_risk,
            "findings": len(parent_findings),
        },
        "current": {
            "id": current.id,
            "created_at": current.created_at,
            "overall_risk": current.overall_risk,
            "findings": len(current_findings),
        },
        "resolved": resolved,
        "remaining": remaining,
        "new": new,
    }
