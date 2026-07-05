"""SQLite persistence for analysis reports.

SQLite keeps the deployment self-contained (attach a Railway volume at
DATA_DIR for persistence across deploys). Reports are stored as JSON blobs —
the schema is the Pydantic model, and access patterns are id-lookup and
recency listing only.
"""
import asyncio
import json
import sqlite3
from pathlib import Path

from .models import AnalysisReport


class ReportStore:
    def __init__(self, data_dir: Path):
        data_dir.mkdir(parents=True, exist_ok=True)
        self._path = data_dir / "reports.db"
        self._lock = asyncio.Lock()
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS reports ("
                " id TEXT PRIMARY KEY,"
                " created_at TEXT NOT NULL,"
                " overall_risk TEXT NOT NULL,"
                " status TEXT NOT NULL,"
                " title TEXT NOT NULL,"
                " payload TEXT NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    async def save(self, report: AnalysisReport) -> None:
        def _write():
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO reports (id, created_at, overall_risk, status, title, payload)"
                    " VALUES (?, ?, ?, ?, ?, ?)"
                    " ON CONFLICT(id) DO UPDATE SET"
                    " overall_risk=excluded.overall_risk, status=excluded.status, payload=excluded.payload",
                    (report.id, report.created_at, report.overall_risk, report.status,
                     report.campaign.title, report.model_dump_json()),
                )
        async with self._lock:
            await asyncio.to_thread(_write)

    async def get(self, report_id: str) -> AnalysisReport | None:
        def _read():
            with self._connect() as conn:
                row = conn.execute("SELECT payload FROM reports WHERE id = ?", (report_id,)).fetchone()
                return row[0] if row else None
        payload = await asyncio.to_thread(_read)
        return AnalysisReport(**json.loads(payload)) if payload else None

    async def list(self, limit: int = 50) -> list[dict]:
        def _read():
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT id, created_at, overall_risk, status, title FROM reports"
                    " ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
                return rows
        rows = await asyncio.to_thread(_read)
        return [
            {"id": r[0], "created_at": r[1], "overall_risk": r[2], "status": r[3], "title": r[4]}
            for r in rows
        ]
