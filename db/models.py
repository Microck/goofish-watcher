from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class QueryInterval(Enum):
    FAST = 60
    NORMAL = 180
    SLOW = 360


class ScanStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class NotificationStatus(Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


@dataclass
class Query:
    id: int | None
    keyword: str
    description: str | None
    include_terms: list[str]
    exclude_terms: list[str]
    min_price: float | None
    max_price: float | None
    interval_minutes: int
    ai_enabled: bool
    ai_threshold: float
    enabled: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class ListingSeen:
    id: int | None
    query_id: int
    listing_id: str
    title: str
    price: float
    seller_id: str
    first_seen_at: datetime
    last_seen_at: datetime


@dataclass
class Notification:
    id: int | None
    query_id: int
    listing_id: str
    status: NotificationStatus
    ai_relevance: float | None
    ai_reason: str | None
    sent_at: datetime | None
    created_at: datetime


@dataclass
class Scan:
    id: int | None
    query_id: int
    status: ScanStatus
    listings_found: int
    listings_new: int
    listings_notified: int
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None


@dataclass
class Label:
    id: int | None
    notification_id: int
    label: str
    created_at: datetime


SCHEMA = """
CREATE TABLE IF NOT EXISTS queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    description TEXT,
    include_terms TEXT DEFAULT '[]',
    exclude_terms TEXT DEFAULT '[]',
    min_price REAL,
    max_price REAL,
    interval_minutes INTEGER DEFAULT 60,
    ai_enabled INTEGER DEFAULT 1,
    ai_threshold REAL DEFAULT 0.7,
    enabled INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS listings_seen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id INTEGER NOT NULL,
    listing_id TEXT NOT NULL,
    title TEXT NOT NULL,
    price REAL NOT NULL,
    seller_id TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    FOREIGN KEY (query_id) REFERENCES queries(id) ON DELETE CASCADE,
    UNIQUE(query_id, listing_id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id INTEGER NOT NULL,
    listing_id TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    ai_relevance REAL,
    ai_reason TEXT,
    sent_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (query_id) REFERENCES queries(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',
    listings_found INTEGER DEFAULT 0,
    listings_new INTEGER DEFAULT 0,
    listings_notified INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    FOREIGN KEY (query_id) REFERENCES queries(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    notification_id INTEGER NOT NULL,
    label TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (notification_id) REFERENCES notifications(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_listings_seen_query_listing ON listings_seen(query_id, listing_id);
CREATE INDEX IF NOT EXISTS idx_listings_seen_last_seen ON listings_seen(last_seen_at);
CREATE INDEX IF NOT EXISTS idx_notifications_query ON notifications(query_id);
CREATE INDEX IF NOT EXISTS idx_scans_query ON scans(query_id);
"""
