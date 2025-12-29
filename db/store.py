import json
from datetime import datetime, timedelta
from pathlib import Path

import aiosqlite

from config import settings
from db.models import (
    SCHEMA,
    Label,
    Notification,
    NotificationStatus,
    Query,
    Scan,
    ScanStatus,
)


class Store:
    def __init__(self, db_path: Path | str | None = None):
        path = db_path or settings.database_path
        self.db_path = Path(path) if isinstance(path, str) else path
        self._connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.executescript(SCHEMA)
        await self._migrate()
        await self._connection.commit()

    async def _migrate(self) -> None:
        cursor = await self.conn.execute("PRAGMA table_info(queries)")
        columns = {row[1] for row in await cursor.fetchall()}
        if "description" not in columns:
            await self.conn.execute("ALTER TABLE queries ADD COLUMN description TEXT")

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()
            self._connection = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if not self._connection:
            raise RuntimeError("Database not connected")
        return self._connection

    # === Queries ===

    async def add_query(
        self,
        keyword: str,
        description: str | None = None,
        include_terms: list[str] | None = None,
        exclude_terms: list[str] | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        interval_minutes: int = 60,
        ai_enabled: bool = True,
        ai_threshold: float = 0.7,
    ) -> int:
        now = datetime.utcnow().isoformat()
        cursor = await self.conn.execute(
            """
            INSERT INTO queries
            (keyword, description, include_terms, exclude_terms, min_price, max_price,
             interval_minutes, ai_enabled, ai_threshold, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                keyword,
                description,
                json.dumps(include_terms or []),
                json.dumps(exclude_terms or []),
                min_price,
                max_price,
                interval_minutes,
                int(ai_enabled),
                ai_threshold,
                now,
                now,
            ),
        )
        await self.conn.commit()
        return cursor.lastrowid  # type: ignore

    async def get_query(self, query_id: int) -> Query | None:
        cursor = await self.conn.execute("SELECT * FROM queries WHERE id = ?", (query_id,))
        row = await cursor.fetchone()
        return self._row_to_query(row) if row else None

    async def get_all_queries(self, enabled_only: bool = False) -> list[Query]:
        sql = "SELECT * FROM queries"
        if enabled_only:
            sql += " WHERE enabled = 1"
        cursor = await self.conn.execute(sql)
        rows = await cursor.fetchall()
        return [self._row_to_query(row) for row in rows]

    async def update_query(self, query_id: int, **kwargs) -> bool:
        if not kwargs:
            return False

        allowed = {
            "keyword", "description", "include_terms", "exclude_terms", "min_price", "max_price",
            "interval_minutes", "ai_enabled", "ai_threshold", "enabled"
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False

        if "include_terms" in updates:
            updates["include_terms"] = json.dumps(updates["include_terms"])
        if "exclude_terms" in updates:
            updates["exclude_terms"] = json.dumps(updates["exclude_terms"])
        if "ai_enabled" in updates:
            updates["ai_enabled"] = int(updates["ai_enabled"])
        if "enabled" in updates:
            updates["enabled"] = int(updates["enabled"])

        updates["updated_at"] = datetime.utcnow().isoformat()

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [query_id]

        cursor = await self.conn.execute(
            f"UPDATE queries SET {set_clause} WHERE id = ?", values
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def delete_query(self, query_id: int) -> bool:
        cursor = await self.conn.execute("DELETE FROM queries WHERE id = ?", (query_id,))
        await self.conn.commit()
        return cursor.rowcount > 0

    def _row_to_query(self, row: aiosqlite.Row) -> Query:
        return Query(
            id=row["id"],
            keyword=row["keyword"],
            description=row["description"],
            include_terms=json.loads(row["include_terms"]),
            exclude_terms=json.loads(row["exclude_terms"]),
            min_price=row["min_price"],
            max_price=row["max_price"],
            interval_minutes=row["interval_minutes"],
            ai_enabled=bool(row["ai_enabled"]),
            ai_threshold=row["ai_threshold"],
            enabled=bool(row["enabled"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # === Listings Seen ===

    async def mark_listing_seen(
        self,
        query_id: int,
        listing_id: str,
        title: str,
        price: float,
        seller_id: str,
    ) -> bool:
        now = datetime.utcnow().isoformat()
        cursor = await self.conn.execute(
            """
            INSERT INTO listings_seen
                (query_id, listing_id, title, price, seller_id, first_seen_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(query_id, listing_id) DO UPDATE SET last_seen_at = ?
            """,
            (query_id, listing_id, title, price, seller_id, now, now, now),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def is_listing_seen(self, query_id: int, listing_id: str) -> bool:
        cursor = await self.conn.execute(
            "SELECT 1 FROM listings_seen WHERE query_id = ? AND listing_id = ?",
            (query_id, listing_id),
        )
        return await cursor.fetchone() is not None

    async def cleanup_old_listings(self, days: int | None = None) -> int:
        cutoff = datetime.utcnow() - timedelta(days=days or settings.dedupe_retention_days)
        cursor = await self.conn.execute(
            "DELETE FROM listings_seen WHERE last_seen_at < ?",
            (cutoff.isoformat(),),
        )
        await self.conn.commit()
        return cursor.rowcount

    # === Notifications ===

    async def create_notification(
        self,
        query_id: int,
        listing_id: str,
        ai_relevance: float | None = None,
        ai_reason: str | None = None,
    ) -> int:
        now = datetime.utcnow().isoformat()
        cursor = await self.conn.execute(
            """
            INSERT INTO notifications
                (query_id, listing_id, status, ai_relevance, ai_reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (query_id, listing_id, NotificationStatus.PENDING.value, ai_relevance, ai_reason, now),
        )
        await self.conn.commit()
        return cursor.lastrowid  # type: ignore

    async def mark_notification_sent(self, notification_id: int) -> bool:
        now = datetime.utcnow().isoformat()
        cursor = await self.conn.execute(
            "UPDATE notifications SET status = ?, sent_at = ? WHERE id = ?",
            (NotificationStatus.SENT.value, now, notification_id),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def get_pending_notifications(self, query_id: int | None = None) -> list[Notification]:
        sql = "SELECT * FROM notifications WHERE status = ?"
        params: list = [NotificationStatus.PENDING.value]
        if query_id:
            sql += " AND query_id = ?"
            params.append(query_id)
        cursor = await self.conn.execute(sql, params)
        rows = await cursor.fetchall()
        return [self._row_to_notification(row) for row in rows]

    def _row_to_notification(self, row: aiosqlite.Row) -> Notification:
        return Notification(
            id=row["id"],
            query_id=row["query_id"],
            listing_id=row["listing_id"],
            status=NotificationStatus(row["status"]),
            ai_relevance=row["ai_relevance"],
            ai_reason=row["ai_reason"],
            sent_at=datetime.fromisoformat(row["sent_at"]) if row["sent_at"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    # === Scans ===

    async def start_scan(self, query_id: int) -> int:
        now = datetime.utcnow().isoformat()
        cursor = await self.conn.execute(
            "INSERT INTO scans (query_id, status, started_at) VALUES (?, ?, ?)",
            (query_id, ScanStatus.RUNNING.value, now),
        )
        await self.conn.commit()
        return cursor.lastrowid  # type: ignore

    async def finish_scan(
        self,
        scan_id: int,
        status: ScanStatus,
        listings_found: int = 0,
        listings_new: int = 0,
        listings_notified: int = 0,
        error_message: str | None = None,
    ) -> bool:
        now = datetime.utcnow().isoformat()
        cursor = await self.conn.execute(
            """
            UPDATE scans SET status = ?, listings_found = ?, listings_new = ?,
            listings_notified = ?, error_message = ?, finished_at = ?
            WHERE id = ?
            """,
            (
                status.value, listings_found, listings_new,
                listings_notified, error_message, now, scan_id
            ),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def get_recent_scans(self, query_id: int, limit: int = 10) -> list[Scan]:
        cursor = await self.conn.execute(
            "SELECT * FROM scans WHERE query_id = ? ORDER BY started_at DESC LIMIT ?",
            (query_id, limit),
        )
        rows = await cursor.fetchall()
        return [self._row_to_scan(row) for row in rows]

    async def get_all_recent_scans(self, limit: int = 10) -> list[Scan]:
        cursor = await self.conn.execute(
            "SELECT * FROM scans ORDER BY started_at DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_scan(row) for row in rows]

    def _row_to_scan(self, row: aiosqlite.Row) -> Scan:
        return Scan(
            id=row["id"],
            query_id=row["query_id"],
            status=ScanStatus(row["status"]),
            listings_found=row["listings_found"],
            listings_new=row["listings_new"],
            listings_notified=row["listings_notified"],
            error_message=row["error_message"],
            started_at=datetime.fromisoformat(row["started_at"]),
            finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
        )

    # === Labels ===

    async def add_label(self, notification_id: int, label: str) -> int:
        now = datetime.utcnow().isoformat()
        cursor = await self.conn.execute(
            "INSERT INTO labels (notification_id, label, created_at) VALUES (?, ?, ?)",
            (notification_id, label, now),
        )
        await self.conn.commit()
        return cursor.lastrowid  # type: ignore

    async def get_notification_by_id(self, notification_id: int) -> Notification | None:
        cursor = await self.conn.execute(
            "SELECT * FROM notifications WHERE id = ?", (notification_id,)
        )
        row = await cursor.fetchone()
        return self._row_to_notification(row) if row else None

    async def get_labels(self, notification_id: int) -> list[Label]:
        cursor = await self.conn.execute(
            "SELECT * FROM labels WHERE notification_id = ? ORDER BY created_at",
            (notification_id,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_label(row) for row in rows]

    def _row_to_label(self, row: aiosqlite.Row) -> Label:
        return Label(
            id=row["id"],
            notification_id=row["notification_id"],
            label=row["label"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    # === Stats ===

    async def get_global_stats(self) -> dict:
        now = datetime.utcnow()
        day_ago = (now - timedelta(days=1)).isoformat()

        cursor = await self.conn.execute(
            "SELECT COUNT(*) FROM scans WHERE started_at > ?", (day_ago,)
        )
        scans_24h = (await cursor.fetchone())[0]

        cursor = await self.conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE created_at > ?", (day_ago,)
        )
        notifications_24h = (await cursor.fetchone())[0]

        cursor = await self.conn.execute("SELECT COUNT(*) FROM listings_seen")
        listings_tracked = (await cursor.fetchone())[0]

        return {
            "scans_24h": scans_24h,
            "notifications_24h": notifications_24h,
            "listings_tracked": listings_tracked,
        }

    async def get_recent_failures(self, hours: int = 1) -> int:
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        cursor = await self.conn.execute(
            "SELECT COUNT(*) FROM scans WHERE status = ? AND started_at > ?",
            (ScanStatus.FAILED.value, cutoff),
        )
        return (await cursor.fetchone())[0]


store = Store()
