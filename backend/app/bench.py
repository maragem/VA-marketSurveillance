"""Benchmark gold-set editing.

The repo ships the seed dataset at bench/cases.jsonl. The editable working
copy lives in DATA_DIR (the Railway volume), created from the seed on first
access, so label corrections made through the UI survive redeploys. The
export endpoint returns the working copy as JSONL, ready to be committed
back to the repository as the new seed.
"""
import asyncio
import json
import shutil
from pathlib import Path

from pydantic import ValidationError

from .models import CampaignSubmission

REGULATIONS = ("AI_ACT", "GDPR", "DSA", "UCPD")
RISKS = ("critical", "high", "medium", "low", "compliant")


def validate_case(case: dict, graph) -> list[str]:
    """Return human-readable validation errors ([] = valid)."""
    errors: list[str] = []
    case_id = case.get("id")
    if not isinstance(case_id, str) or not case_id.strip():
        errors.append("Case id must be a non-empty string.")
    if case.get("tier") not in (1, 2, 3):
        errors.append("tier must be 1 (enforcement-inspired), 2 (dataset-adapted) or 3 (synthetic).")
    try:
        CampaignSubmission(**(case.get("campaign") or {}))
    except ValidationError as exc:
        errors.extend(f"campaign.{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())

    gold = case.get("gold")
    if not isinstance(gold, dict):
        return errors + ["gold labels are missing."]
    for reg in gold.get("relevant") or []:
        if reg not in REGULATIONS:
            errors.append(f"Unknown regulation in relevant: {reg}")
    if gold.get("min_risk") not in RISKS:
        errors.append(f"min_risk must be one of {', '.join(RISKS)}.")
    for field in ("provisions", "acceptable_extra"):
        for pid in gold.get(field) or []:
            node = graph.get(pid)
            if not node or node.get("type") != "provision":
                errors.append(f"Unknown provision id in {field}: {pid}")
            elif field == "provisions" and node.get("regulation") not in (gold.get("relevant") or []):
                errors.append(
                    f"Must-find provision {pid} belongs to {node.get('regulation')}, "
                    "which is not listed in relevant.")
    if gold.get("compliant") and gold.get("provisions"):
        errors.append("A compliant control cannot have must-find provisions.")
    return errors


class BenchStore:
    def __init__(self, seed_path: Path, data_dir: Path):
        self._seed = seed_path
        self._working = data_dir / "bench-cases.jsonl"
        self._lock = asyncio.Lock()

    def _ensure_working(self) -> None:
        if not self._working.exists() and self._seed.exists():
            self._working.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(self._seed, self._working)

    def _read(self) -> list[dict]:
        self._ensure_working()
        if not self._working.exists():
            return []
        return [json.loads(line) for line in self._working.read_text().splitlines() if line.strip()]

    def _write(self, cases: list[dict]) -> None:
        self._working.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._working.with_suffix(".tmp")
        tmp.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases))
        tmp.replace(self._working)

    async def list(self) -> list[dict]:
        async with self._lock:
            return await asyncio.to_thread(self._read)

    async def upsert(self, case: dict, *, create: bool) -> None:
        """Insert (create=True) or replace (create=False) one case, atomically."""
        async with self._lock:
            def _apply():
                cases = self._read()
                index = {c["id"]: i for i, c in enumerate(cases)}
                if create and case["id"] in index:
                    raise KeyError(f"Case id already exists: {case['id']}")
                if not create and case["id"] not in index:
                    raise KeyError(f"Unknown case id: {case['id']}")
                if case["id"] in index:
                    cases[index[case["id"]]] = case
                else:
                    cases.append(case)
                self._write(cases)
            await asyncio.to_thread(_apply)

    async def delete(self, case_id: str) -> None:
        async with self._lock:
            def _apply():
                cases = self._read()
                remaining = [c for c in cases if c["id"] != case_id]
                if len(remaining) == len(cases):
                    raise KeyError(f"Unknown case id: {case_id}")
                self._write(remaining)
            await asyncio.to_thread(_apply)

    async def export_text(self) -> str:
        cases = await self.list()
        return "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases)
