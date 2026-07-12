"""Engine calibration: human-approved rules distilled from benchmark review.

Approved rules are injected into the specialist agents' system prompts so the
engine stops repeating mistakes the benchmark exposed (e.g. citing DSA
platform duties against advertisers). The versioned seed lives at
knowledge/calibration.json; the editable working copy lives in DATA_DIR so
approvals made through the UI survive redeploys and can be exported back into
the repository.

Rules must be GENERAL legal principles. They deliberately never reference
benchmark case ids, brand names or campaign facts — otherwise the benchmark
would stop being an honest measurement of the engine it calibrates.
"""
import asyncio
import json
import shutil
from pathlib import Path
from uuid import uuid4

from . import config

SECTIONS = ("GLOBAL", "AI_ACT", "GDPR", "DSA", "UCPD")
MAX_RULE_CHARS = 700
MAX_RULES_TOTAL = 40


class CalibrationStore:
    def __init__(self, seed_path: Path, data_dir: Path):
        self._seed = seed_path
        self._working = data_dir / "calibration.json"
        self._lock = asyncio.Lock()

    def _ensure_working(self) -> None:
        if not self._working.exists() and self._seed.exists():
            self._working.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(self._seed, self._working)

    def _read(self) -> dict:
        self._ensure_working()
        if not self._working.exists():
            return {section: [] for section in SECTIONS}
        data = json.loads(self._working.read_text())
        return {section: data.get(section, []) for section in SECTIONS}

    def _write(self, data: dict) -> None:
        self._working.parent.mkdir(parents=True, exist_ok=True)
        payload = {"_comment": "Working copy — export and commit to knowledge/calibration.json to version."}
        payload.update({section: data.get(section, []) for section in SECTIONS})
        tmp = self._working.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        tmp.replace(self._working)

    async def all(self) -> dict:
        async with self._lock:
            return await asyncio.to_thread(self._read)

    async def rules_for(self, regulation: str) -> list[str]:
        """Rule texts a given specialist must apply: GLOBAL + its own section."""
        data = await self.all()
        return [r["rule"] for r in data.get("GLOBAL", []) + data.get(regulation, [])]

    async def add(self, regulation: str, rule: str, origin: str) -> dict:
        rule = " ".join(rule.split())
        if regulation not in SECTIONS:
            raise ValueError(f"Unknown section: {regulation}")
        if not (20 <= len(rule) <= MAX_RULE_CHARS):
            raise ValueError(f"Rule must be 20-{MAX_RULE_CHARS} characters.")
        async with self._lock:
            def _apply():
                data = self._read()
                if sum(len(v) for v in data.values()) >= MAX_RULES_TOTAL:
                    raise ValueError(f"Rule limit reached ({MAX_RULES_TOTAL}) — prune before adding more.")
                if any(r["rule"] == rule for section in data.values() for r in section):
                    raise ValueError("An identical rule already exists.")
                entry = {"id": uuid4().hex[:8], "rule": rule, "origin": origin}
                data[regulation].append(entry)
                self._write(data)
                return entry
            return await asyncio.to_thread(_apply)

    async def remove(self, rule_id: str) -> None:
        async with self._lock:
            def _apply():
                data = self._read()
                for section in SECTIONS:
                    kept = [r for r in data[section] if r.get("id") != rule_id]
                    if len(kept) != len(data[section]):
                        data[section] = kept
                        self._write(data)
                        return
                raise KeyError(f"Unknown rule id: {rule_id}")
            await asyncio.to_thread(_apply)

    async def export_text(self) -> str:
        data = await self.all()
        payload = {"_comment": "Human-approved calibration rules injected into the specialist agents' "
                               "prompts. General legal principles only — never case-specific facts."}
        payload.update(data)
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


# ---------------------------------------------------------------------------
# Lesson proposals: distil benchmark deviations into candidate rules
# ---------------------------------------------------------------------------

PROPOSE_TOOL = {
    "name": "submit_lesson_proposals",
    "description": "Submit the calibration rules you propose. Call exactly once.",
    "input_schema": {
        "type": "object",
        "properties": {
            "proposals": {
                "type": "array",
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": {
                        "regulation": {"type": "string", "enum": list(SECTIONS),
                                       "description": "GLOBAL for cross-cutting rules, otherwise the specialist the rule should reach."},
                        "rule": {"type": "string",
                                 "description": "The calibration rule, 1-3 sentences, imperative voice, a GENERAL legal principle. Never mention benchmark cases, brands or campaign facts."},
                        "why": {"type": "string", "description": "1-2 sentences: the recurring error pattern this corrects."},
                        "evidence_case_ids": {"type": "array", "items": {"type": "string"},
                                              "description": "Benchmark case ids exhibiting the pattern."},
                    },
                    "required": ["regulation", "rule", "why", "evidence_case_ids"],
                },
            },
        },
        "required": ["proposals"],
    },
}

PROPOSER_SYSTEM = """You distil systematic errors of an EU marketing-compliance engine into calibration \
rules. You receive benchmark deviations: provisions the engine cited that human reviewers refused \
(over-citation), provisions it missed (under-citation), adjudicator verdicts, and false positives on \
compliant campaigns.

Propose at most 5 rules, and only for RECURRING or clearly systematic patterns — a one-off wobble does \
not deserve a rule. Each rule must be:
- a GENERAL legal principle (scope, addressee, specificity, severity discipline) that transfers to unseen \
campaigns — never a memorised case answer;
- free of benchmark case ids, brand names, product names or campaign-specific facts;
- not already covered by the existing rules provided;
- imperative and concrete enough to change behaviour.

If the deviations show no systematic pattern, submit an empty proposals list. \
Call submit_lesson_proposals exactly once."""


async def propose_lessons(graph, cases: list[dict], runs: dict, existing: dict) -> list[dict]:
    """Draft candidate calibration rules from benchmark deviations (human approves)."""
    client = config.make_async_client()
    if client is None:
        raise RuntimeError("Lesson proposals require LLM credentials.")

    def ref(pid: str) -> str:
        node = graph.get(pid)
        return f"{node['ref']} ({node['title']})" if node else pid

    lines: list[str] = []
    for case in cases:
        run = runs.get(case["id"])
        if not run:
            continue
        gold = case["gold"]
        deviations: list[str] = []
        for u in run.get("unexpected", []):
            adj = u.get("adjudication") or {}
            verdict = f" [adjudicated {adj['verdict']}: {adj.get('reasoning', '')[:200]}]" if adj else ""
            deviations.append(f"  over-cited: {ref(u['id'])} at {u.get('severity')}{verdict}")
        for pid in run.get("missed", []):
            deviations.append(f"  missed must-find: {ref(pid)}")
        if run.get("falsePositive"):
            deviations.append("  false positive: flagged a campaign the reviewer marked compliant")
        if not deviations:
            continue
        lines.append(
            f"Case {case['id']} (tier {case['tier']}; relevant: {', '.join(gold.get('relevant') or []) or '—'}; "
            f"gold must-find: {', '.join(ref(p) for p in gold.get('provisions') or []) or 'none (compliant control)'}):\n"
            + "\n".join(deviations))
    if not lines:
        return []

    existing_rules = [r["rule"] for section in existing.values()
                      if isinstance(section, list) for r in section]
    prompt = (
        "EXISTING CALIBRATION RULES (do not duplicate):\n"
        + ("\n".join(f"- {r}" for r in existing_rules) or "- none")
        + "\n\nBENCHMARK DEVIATIONS (engine output vs human-reviewed gold labels):\n"
        + "\n\n".join(lines[:40])
        + "\n\nPropose calibration rules for the systematic patterns you see."
    )
    response = await client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=3000,
        system=PROPOSER_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        tools=[PROPOSE_TOOL],
        tool_choice={"type": "tool", "name": "submit_lesson_proposals"},
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_lesson_proposals":
            proposals = block.input.get("proposals", [])
            return [p for p in proposals
                    if p.get("regulation") in SECTIONS and isinstance(p.get("rule"), str)]
    raise RuntimeError("The proposer did not return proposals.")
