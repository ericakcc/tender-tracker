"""SQLite storage layer for tender data persistence."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from loguru import logger

from tender_tracker.models import Tender, TenderEvaluation

DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "tenders.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tenders (
    tender_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    org_name TEXT DEFAULT '',
    procurement_type TEXT DEFAULT '',
    tender_method TEXT DEFAULT '',
    budget_amount REAL,
    deadline TEXT,
    open_date TEXT,
    url TEXT DEFAULT '',
    category TEXT DEFAULT '',
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evaluations (
    tender_id TEXT PRIMARY KEY REFERENCES tenders(tender_id),
    suitable INTEGER NOT NULL,
    relevance_score REAL NOT NULL,
    reasoning TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    matched_capabilities TEXT NOT NULL,
    evaluated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    synced_at TEXT NOT NULL,
    record_count INTEGER NOT NULL,
    status TEXT NOT NULL
);
"""


class TenderStorage:
    """SQLite-based storage for tender data."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or DEFAULT_DB_PATH
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_conn()
        conn.executescript(_SCHEMA)
        conn.commit()
        logger.debug("Database initialized at {}", self._db_path)

    def close(self) -> None:
        """Close database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def upsert_tender(self, tender: Tender) -> bool:
        """Insert or update a tender record.

        Args:
            tender: Tender to upsert.

        Returns:
            True if a new record was inserted, False if updated.
        """
        conn = self._get_conn()
        existing = conn.execute(
            "SELECT tender_id FROM tenders WHERE tender_id = ?",
            (tender.tender_id,),
        ).fetchone()

        data = {
            "tender_id": tender.tender_id,
            "title": tender.title,
            "org_name": tender.org_name,
            "procurement_type": tender.procurement_type,
            "tender_method": tender.tender_method,
            "budget_amount": tender.budget_amount,
            "deadline": tender.deadline.isoformat() if tender.deadline else None,
            "open_date": tender.open_date.isoformat() if tender.open_date else None,
            "url": tender.url,
            "category": tender.category,
            "source": tender.source,
            "fetched_at": tender.fetched_at.isoformat(),
        }

        if existing:
            set_clause = ", ".join(f"{k} = ?" for k in data if k != "tender_id")
            values = [v for k, v in data.items() if k != "tender_id"]
            values.append(data["tender_id"])
            conn.execute(
                f"UPDATE tenders SET {set_clause} WHERE tender_id = ?",  # noqa: S608
                values,
            )
            conn.commit()
            return False

        columns = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        conn.execute(
            f"INSERT INTO tenders ({columns}) VALUES ({placeholders})",
            list(data.values()),
        )
        conn.commit()
        return True

    def upsert_tenders(self, tenders: list[Tender]) -> int:
        """Bulk upsert tenders.

        Args:
            tenders: List of tenders to upsert.

        Returns:
            Number of new records inserted.
        """
        new_count = 0
        for tender in tenders:
            if self.upsert_tender(tender):
                new_count += 1
        return new_count

    def get_tender(self, tender_id: str) -> Tender | None:
        """Get a tender by ID.

        Args:
            tender_id: The tender ID to look up.

        Returns:
            Tender if found, None otherwise.
        """
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM tenders WHERE tender_id = ?", (tender_id,)).fetchone()
        if not row:
            return None
        return _row_to_tender(row)

    def list_tenders(
        self,
        *,
        days: int | None = None,
        limit: int = 100,
        evaluated_only: bool = False,
    ) -> list[Tender]:
        """List tenders with optional filters.

        Args:
            days: Only return tenders fetched within this many days.
            limit: Maximum number of results.
            evaluated_only: Only return tenders that have evaluations.

        Returns:
            List of matching tenders.
        """
        conn = self._get_conn()
        conditions: list[str] = []
        params: list[str | int] = []

        if days is not None:
            conditions.append("fetched_at >= ?")
            from datetime import timedelta

            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            params.append(cutoff)

        if evaluated_only:
            conditions.append("tender_id IN (SELECT tender_id FROM evaluations)")

        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT * FROM tenders{where} ORDER BY fetched_at DESC LIMIT ?"  # noqa: S608
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [_row_to_tender(row) for row in rows]

    def save_evaluation(self, tender_id: str, evaluation: TenderEvaluation) -> None:
        """Save an AI evaluation for a tender.

        Args:
            tender_id: The tender this evaluation is for.
            evaluation: The evaluation result.
        """
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO evaluations
            (tender_id, suitable, relevance_score, reasoning,
             recommended_action, matched_capabilities, evaluated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                tender_id,
                int(evaluation.suitable),
                evaluation.relevance_score,
                evaluation.reasoning,
                evaluation.recommended_action,
                json.dumps(evaluation.matched_capabilities, ensure_ascii=False),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()

    def get_evaluation(self, tender_id: str) -> TenderEvaluation | None:
        """Get the evaluation for a tender.

        Args:
            tender_id: The tender ID.

        Returns:
            Evaluation if found, None otherwise.
        """
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM evaluations WHERE tender_id = ?", (tender_id,)).fetchone()
        if not row:
            return None
        return TenderEvaluation(
            suitable=bool(row["suitable"]),
            relevance_score=row["relevance_score"],
            reasoning=row["reasoning"],
            recommended_action=row["recommended_action"],
            matched_capabilities=json.loads(row["matched_capabilities"]),
        )

    def get_unevaluated_tender_ids(self) -> list[str]:
        """Get IDs of tenders that haven't been evaluated yet.

        Returns:
            List of tender IDs without evaluations.
        """
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT t.tender_id FROM tenders t
            LEFT JOIN evaluations e ON t.tender_id = e.tender_id
            WHERE e.tender_id IS NULL
            ORDER BY t.fetched_at DESC"""
        ).fetchall()
        return [row["tender_id"] for row in rows]

    def log_sync(self, source: str, record_count: int, status: str) -> None:
        """Log a sync operation.

        Args:
            source: The data source name.
            record_count: Number of records processed.
            status: Sync status (success/error).
        """
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO sync_log (source, synced_at, record_count, status) VALUES (?, ?, ?, ?)",
            (source, datetime.now().isoformat(), record_count, status),
        )
        conn.commit()

    def get_stats(self) -> dict[str, int]:
        """Get summary statistics.

        Returns:
            Dictionary with counts for tenders, evaluations, etc.
        """
        conn = self._get_conn()
        total = conn.execute("SELECT COUNT(*) FROM tenders").fetchone()[0]
        evaluated = conn.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0]
        suitable = conn.execute("SELECT COUNT(*) FROM evaluations WHERE suitable = 1").fetchone()[0]
        return {
            "total_tenders": total,
            "evaluated": evaluated,
            "suitable": suitable,
            "unevaluated": total - evaluated,
        }


def _row_to_tender(row: sqlite3.Row) -> Tender:
    """Convert a database row to a Tender model."""
    return Tender(
        tender_id=row["tender_id"],
        title=row["title"],
        org_name=row["org_name"],
        procurement_type=row["procurement_type"],
        tender_method=row["tender_method"],
        budget_amount=row["budget_amount"],
        deadline=datetime.fromisoformat(row["deadline"]) if row["deadline"] else None,
        open_date=datetime.fromisoformat(row["open_date"]) if row["open_date"] else None,
        url=row["url"],
        category=row["category"],
        source=row["source"],
        fetched_at=datetime.fromisoformat(row["fetched_at"]),
    )
