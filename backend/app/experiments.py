"""Server-side runner for the Table 1 evaluation grid (configurations A-D).

Runs whole benchmark configurations as background jobs inside the deployed
service, so experiments survive browser disconnects and client crashes. The
durability contract:

- every completed case-run is appended to the job's ``outcomes.jsonl`` on the
  data volume and fsynced before progress advances — a restart loses at most
  the analyses that were in flight;
- jobs found in ``running`` state at startup are resumed automatically,
  skipping case-runs that already have stored outcomes;
- raw engine outputs are stored in the same format as the CLI harness's
  ``-reports.jsonl``, so ``bench/run.py --rescore`` works on them unchanged.

Configuration differences (credentials, citation validation, calibration)
are per-job orchestration parameters here — they never touch the environment
flags, so the production analysis path is unaffected by a running experiment.

Scoring is imported from ``bench/run.py`` — a single source of truth shared
with the CLI harness, so UI numbers and harness numbers agree by construction.
"""
import asyncio
import hashlib
import importlib.util
import itertools
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import config
from .agents.orchestrator import Orchestrator
from .models import AnalysisReport, CampaignSubmission

logger = logging.getLogger("experiments")

RUNS_PER_CASE = 3
CONCURRENCY = 2          # experiments share the service with real users
CASE_TIMEOUT_S = 900.0

CONFIGS: list[dict] = [
    {
        "id": "A",
        "label": "A — Retrieval-only",
        "description": "GraphRAG retrieval heuristic with no language model: what retrieval "
                       "alone contributes. Free and fast; runs the full case set.",
        "subset": "all", "force_heuristic": True, "skip_validation": False,
        "use_calibration": False, "needs_llm": False,
    },
    {
        "id": "B",
        "label": "B — No citation validation",
        "description": "Full agentic pipeline with post-hoc citation validation disabled for "
                       "this job only. The scorecard's invalid-citations count measures what "
                       "validation normally removes.",
        "subset": "all", "force_heuristic": False, "skip_validation": True,
        "use_calibration": False, "needs_llm": True,
    },
    {
        "id": "C-full",
        "label": "C — Deployed default (full set)",
        "description": "The pipeline as deployed — triage, specialists, synthesis, citation "
                       "validation — without calibration rules. The main Table 1 row.",
        "subset": "all", "force_heuristic": False, "skip_validation": False,
        "use_calibration": False, "needs_llm": True,
    },
    {
        "id": "C-holdout",
        "label": "C — Default on holdout (D baseline)",
        "description": "Configuration C restricted to the held-out cases. This is the baseline "
                       "configuration D is compared against — same cases, same protocol.",
        "subset": "holdout", "force_heuristic": False, "skip_validation": False,
        "use_calibration": False, "needs_llm": True,
    },
    {
        "id": "D",
        "label": "D — C + calibration (holdout)",
        "description": "Configuration C plus the versioned calibration rules "
                       "(knowledge/calibration.json), evaluated only on the held-out cases "
                       "that never informed rule-writing.",
        "subset": "holdout", "force_heuristic": False, "skip_validation": False,
        "use_calibration": True, "needs_llm": True,
    },
]
CONFIG_BY_ID = {c["id"]: c for c in CONFIGS}


def _load_scoring():
    """Import the CLI harness (bench/run.py) as a module for its scoring code."""
    spec = importlib.util.spec_from_file_location("bench_run_scoring", config.BENCH_DIR / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _SeedCalibration:
    """Read-only calibration source pinned to the VERSIONED rule file, so
    configuration D measures exactly the rule set committed to the repository
    (reproducible from git), independent of the deployment's working copy."""

    def __init__(self, path: Path):
        self._data = json.loads(path.read_text()) if path.exists() else {}

    def rule_count(self) -> int:
        return sum(len(v) for v in self._data.values() if isinstance(v, list))

    async def rules_for(self, regulation: str) -> list[str]:
        return [r["rule"] for r in
                (self._data.get("GLOBAL") or []) + (self._data.get(regulation) or [])]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _noop_emit(_: dict) -> None:
    return None


class ExperimentManager:
    def __init__(self, graph, retriever, bench, data_dir: Path):
        self.graph = graph
        self.retriever = retriever
        self.bench = bench
        self.root = data_dir / "experiments"
        self.root.mkdir(parents=True, exist_ok=True)
        self._task: asyncio.Task | None = None
        self._cancel = asyncio.Event()
        self._lock = asyncio.Lock()

    # ---- storage ----------------------------------------------------------

    def _job_dir(self, job_id: str) -> Path:
        safe = "".join(c for c in job_id if c.isalnum() or c in "-_")
        path = (self.root / safe).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError("bad job id")
        return path

    def _read_job(self, job_id: str) -> Optional[dict]:
        path = self._job_dir(job_id) / "job.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def _write_job(self, job: dict) -> None:
        job["updated_at"] = _now()
        path = self._job_dir(job["id"]) / "job.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(job, ensure_ascii=False, indent=2))
        tmp.replace(path)

    def _append_outcome(self, job_id: str, entry: dict) -> None:
        """Durable checkpoint: append + flush + fsync before progress counts."""
        path = self._job_dir(job_id) / "outcomes.jsonl"
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def _read_outcomes(self, job_id: str) -> list[dict]:
        path = self._job_dir(job_id) / "outcomes.jsonl"
        if not path.exists():
            return []
        entries = []
        for line in path.read_text().splitlines():
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except ValueError:
                    continue  # a torn write from a crash mid-append; safe to retry that run
        return entries

    # ---- public API -------------------------------------------------------

    def running_job_id(self) -> Optional[str]:
        if self._task and not self._task.done():
            return getattr(self._task, "_experiment_job_id", None)
        return None

    async def configs_status(self) -> dict:
        cases = await self.bench.list()
        holdout = self.bench.holdout_ids()
        seed_cal = _SeedCalibration(config.KNOWLEDGE_DIR / "calibration.json")
        items = []
        for cfg in CONFIGS:
            n_cases = len([c for c in cases if c["id"] in holdout]) if cfg["subset"] == "holdout" else len(cases)
            blocked = None
            if cfg["needs_llm"] and not config.llm_available():
                blocked = "LLM credentials are not configured on this deployment."
            if cfg["subset"] == "holdout" and not holdout:
                blocked = "bench/holdout.json is missing or empty."
            if cfg["use_calibration"] and seed_cal.rule_count() == 0:
                blocked = "No calibration rules in knowledge/calibration.json — commit the approved set first."
            items.append({**{k: cfg[k] for k in ("id", "label", "description")},
                          "cases": n_cases, "runs": RUNS_PER_CASE,
                          "total_analyses": n_cases * RUNS_PER_CASE,
                          "calibration_rules": seed_cal.rule_count() if cfg["use_calibration"] else 0,
                          "blocked": blocked})
        return {"configs": items, "model": config.CLAUDE_MODEL if config.llm_available() else None,
                "running_job": self.running_job_id()}

    def list_jobs(self) -> list[dict]:
        jobs = []
        for entry in sorted(self.root.iterdir(), reverse=True):
            if (entry / "job.json").exists():
                try:
                    jobs.append(json.loads((entry / "job.json").read_text()))
                except ValueError:
                    continue
        return jobs

    def get_job(self, job_id: str) -> Optional[dict]:
        return self._read_job(job_id)

    def job_file(self, job_id: str, name: str) -> Optional[Path]:
        if name not in ("scorecard.md", "results.json", "outcomes.jsonl"):
            return None
        path = self._job_dir(job_id) / name
        return path if path.exists() else None

    def reports_jsonl(self, job_id: str) -> str:
        """Raw outputs in the CLI harness's -reports.jsonl format (--rescore compatible).

        Outcomes are stored in completion order (case-runs interleave under
        concurrency); emit them sorted by (case, run) so downstream consumers
        that rely on file order pick the same "first run" the scorer did."""
        entries = sorted(self._read_outcomes(job_id), key=lambda e: (e["case_id"], e["run"]))
        lines = [json.dumps({"case_id": e["case_id"], "run": e["run"], "report": e["report"]},
                            ensure_ascii=False) for e in entries]
        return "\n".join(lines) + ("\n" if lines else "")

    async def start(self, config_id: str) -> dict:
        cfg = CONFIG_BY_ID.get(config_id)
        if not cfg:
            raise ValueError(f"Unknown configuration: {config_id}")
        async with self._lock:
            if self.running_job_id():
                raise RuntimeError("Another experiment job is already running — one at a time.")
            status = await self.configs_status()
            blocked = next(c["blocked"] for c in status["configs"] if c["id"] == config_id)
            if blocked:
                raise RuntimeError(blocked)
            cases = await self._cases_for(cfg)
            payload = json.dumps(cases, sort_keys=True, ensure_ascii=False)
            job = {
                "id": f"{config_id}-{time.strftime('%Y%m%d-%H%M%S')}",
                "config": config_id,
                "label": cfg["label"],
                "status": "running",
                "created_at": _now(),
                "model": config.CLAUDE_MODEL if (config.llm_available() and not cfg["force_heuristic"]) else None,
                "runs": RUNS_PER_CASE,
                "case_ids": [c["id"] for c in cases],
                "cases_sha256": hashlib.sha256(payload.encode()).hexdigest()[:16],
                "total": len(cases) * RUNS_PER_CASE,
                "done": 0,
                "failures": [],
                "resumed": 0,
                "summary": None,
                "error": None,
            }
            self._job_dir(job["id"]).mkdir(parents=True, exist_ok=True)
            self._write_job(job)
            self._launch(job)
            return job

    async def cancel(self, job_id: str) -> dict:
        job = self._read_job(job_id)
        if not job:
            raise KeyError(job_id)
        if self.running_job_id() == job_id:
            self._cancel.set()
        elif job["status"] == "running":
            # stale "running" job that is not actually executing (e.g. resume failed)
            job["status"] = "cancelled"
            self._score_job(job)
            self._write_job(job)
        return self._read_job(job_id)

    def delete(self, job_id: str) -> None:
        if self.running_job_id() == job_id:
            raise RuntimeError("Cancel the job before deleting it.")
        job_dir = self._job_dir(job_id)
        if not (job_dir / "job.json").exists():
            raise KeyError(job_id)
        for child in job_dir.iterdir():
            child.unlink()
        job_dir.rmdir()

    def resume_pending(self) -> None:
        """Called at startup: pick up jobs interrupted by a restart/redeploy."""
        for job in self.list_jobs():
            if job["status"] == "running":
                if self.running_job_id():
                    logger.warning("experiment %s left running but another job is active", job["id"])
                    continue
                job["resumed"] = job.get("resumed", 0) + 1
                self._write_job(job)
                logger.info("resuming interrupted experiment job %s", job["id"])
                self._launch(job)

    # ---- runner -----------------------------------------------------------

    async def _cases_for(self, cfg: dict) -> list[dict]:
        cases = await self.bench.list()
        if cfg["subset"] == "holdout":
            holdout = self.bench.holdout_ids()
            cases = [c for c in cases if c["id"] in holdout]
        return cases

    def _launch(self, job: dict) -> None:
        self._cancel = asyncio.Event()
        self._task = asyncio.create_task(self._run_job(job["id"]))
        self._task._experiment_job_id = job["id"]

    async def _run_job(self, job_id: str) -> None:
        try:
            await self._run_job_inner(job_id)
        except Exception as exc:
            logger.exception("experiment job %s failed", job_id)
            job = self._read_job(job_id)
            if job:
                job["status"] = "failed"
                job["error"] = str(exc)
                try:
                    self._score_job(job)
                except Exception:
                    pass
                self._write_job(job)

    async def _run_job_inner(self, job_id: str) -> None:
        job = self._read_job(job_id)
        cfg = CONFIG_BY_ID[job["config"]]
        cases = await self._cases_for(cfg)
        cases = [c for c in cases if c["id"] in set(job["case_ids"])]
        by_id = {c["id"]: c for c in cases}

        done_keys = {(e["case_id"], e["run"]) for e in self._read_outcomes(job_id)}
        pending = [(cid, run) for cid in job["case_ids"] for run in range(1, job["runs"] + 1)
                   if (cid, run) not in done_keys and cid in by_id]
        job["done"] = len(done_keys)
        self._write_job(job)

        calibration = (_SeedCalibration(config.KNOWLEDGE_DIR / "calibration.json")
                       if cfg["use_calibration"] else None)
        orchestrator = Orchestrator(self.graph, self.retriever, calibration,
                                    force_heuristic=cfg["force_heuristic"],
                                    skip_validation=cfg["skip_validation"])
        if cfg["force_heuristic"] or not config.llm_available():
            engine = "heuristic"
        elif cfg["skip_validation"]:
            engine = "agentic-unvalidated"
        else:
            engine = "agentic"

        semaphore = asyncio.Semaphore(CONCURRENCY)
        write_lock = asyncio.Lock()

        async def one(case_id: str, run: int) -> None:
            async with semaphore:
                if self._cancel.is_set():
                    return
                started = time.monotonic()
                report = AnalysisReport(campaign=CampaignSubmission(**by_id[case_id]["campaign"]),
                                        status="running")
                try:
                    result = await asyncio.wait_for(
                        orchestrator.run(report, _noop_emit), timeout=CASE_TIMEOUT_S)
                except Exception as exc:
                    async with write_lock:
                        job = self._read_job(job_id)
                        job["failures"].append({"case_id": case_id, "run": run,
                                                "error": str(exc)[:300], "at": _now()})
                        self._write_job(job)
                    logger.warning("experiment %s: %s run %s failed: %s", job_id, case_id, run, exc)
                    return
                elapsed = round(time.monotonic() - started, 1)
                payload = json.loads(result.model_dump_json())
                payload["_engine"] = engine
                async with write_lock:
                    self._append_outcome(job_id, {"case_id": case_id, "run": run,
                                                  "report": payload, "elapsed_s": elapsed,
                                                  "at": _now()})
                    job = self._read_job(job_id)
                    job["done"] = job.get("done", 0) + 1
                    self._write_job(job)

        logger.info("experiment %s: %d case-run(s) to execute (engine=%s)",
                    job_id, len(pending), engine)
        await asyncio.gather(*(one(cid, run) for cid, run in pending))

        job = self._read_job(job_id)
        job["status"] = "cancelled" if self._cancel.is_set() else "completed"
        outcomes = self._read_outcomes(job_id)
        covered = {e["case_id"] for e in outcomes}
        missing = [cid for cid in job["case_ids"] if cid not in covered]
        if job["status"] == "completed" and missing:
            job["status"] = "completed_with_errors"
            job["error"] = f"No output for: {', '.join(missing)}"
        self._score_job(job)
        self._write_job(job)
        logger.info("experiment %s finished: %s", job_id, job["status"])

    # ---- scoring (shared with the CLI harness) ----------------------------

    def _score_job(self, job: dict) -> None:
        outcomes = self._read_outcomes(job["id"])
        if not outcomes:
            return
        scoring = _load_scoring()
        provisions = scoring.load_provisions()

        # bench.list() is async; scoring runs in sync context — read the store
        # working copy directly through the bench store's sync reader.
        cases_list = self.bench._read()  # noqa: SLF001 — same-package accessor
        case_by_id = {c["id"]: c for c in cases_list}

        reports: dict[str, list] = {}
        latencies: dict[str, list[float]] = {}
        engines: set[str] = set()
        for entry in outcomes:
            cid = entry["case_id"]
            reports.setdefault(cid, [None] * job["runs"])
            if 1 <= entry["run"] <= job["runs"]:
                reports[cid][entry["run"] - 1] = entry["report"]
            if entry.get("elapsed_s") is not None:
                latencies.setdefault(cid, []).append(entry["elapsed_s"])
            engines.add(entry["report"].get("_engine") or "unknown")

        rows, stability = [], {}
        for cid in job["case_ids"]:
            runs = [r for r in reports.get(cid, []) if r is not None]
            if not runs or cid not in case_by_id:
                continue
            row = scoring.score_case(case_by_id[cid], scoring.extract_predictions(runs[0], provisions))
            if latencies.get(cid):
                row["latency_s"] = round(sum(latencies[cid]) / len(latencies[cid]), 1)
            rows.append(row)
            if len(runs) > 1:
                sets = [scoring.extract_predictions(r, provisions)["found_any"] for r in runs]
                pairs = list(itertools.combinations(sets, 2))
                jaccard = [len(a & b) / len(a | b) if (a | b) else 1.0 for a, b in pairs]
                stability[cid] = round(sum(jaccard) / len(jaccard), 3)
        if not rows:
            return

        summary = scoring.aggregate(rows)
        summary["engine"] = ", ".join(sorted(engines)) or "unknown"
        all_lat = [s for values in latencies.values() for s in values]
        if all_lat:
            summary["mean_latency_s"] = round(sum(all_lat) / len(all_lat), 1)
        if stability:
            summary["stability_mean"] = round(sum(stability.values()) / len(stability), 3)

        scorecard = scoring.markdown_scorecard(summary, rows, stability or None)
        header = (f"Configuration: {job['label']} · job {job['id']} · model: {job.get('model') or '—'} "
                  f"· cases sha256: {job.get('cases_sha256')}\n\n")
        job_dir = self._job_dir(job["id"])
        (job_dir / "scorecard.md").write_text(header + scorecard + "\n")
        (job_dir / "results.json").write_text(json.dumps(
            {"job": {k: job[k] for k in ("id", "config", "label", "model", "runs", "cases_sha256")},
             "summary": summary, "cases": rows, "stability": stability}, indent=2) + "\n")
        job["summary"] = summary
