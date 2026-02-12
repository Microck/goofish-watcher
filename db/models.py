from dataclasses import dataclass, field
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
    id: int | None = None
    keyword: str = field(default="")
    description: str | None = None
    include_terms: list = field(default_factory=list)
    exclude_terms: list = field(default_factory=list)
    min_price: float | None = None
    max_price: float | None = None
    interval_minutes: int = 60
    ai_enabled: bool = True
    ai_threshold: float = 0.7
    enabled: bool = True
    free_shipping: bool = False
    new_publish_hours: int | None = None
    region: str | None = None
    cron_expression: str | None = None
    account_state_file: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ListingSeen:
    id: int | None = None
    query_id: int = 0
    listing_id: str = ""
    title: str = ""
    price: float = 0.0
    seller_id: str = ""
    first_seen_at: datetime = field(default_factory=datetime.utcnow)
    last_seen_at: datetime = field(default_factory=datetime.utcnow)
    seller_rating: float = 0.0
    seller_registration_days: int = 0
    wants_count: int = 0
    original_price: str | None = None
    tags: str | None = None


@dataclass
class Notification:
    id: int | None = None
    query_id: int = 0
    listing_id: str = ""
    status: NotificationStatus = NotificationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    ai_relevance: float | None = None
    ai_reason: str | None = None
    sent_at: datetime | None = None
    channels_sent: str | None = None


@dataclass
class Scan:
    id: int | None = None
    query_id: int = 0
    status: ScanStatus = ScanStatus.PENDING
    listings_found: int = 0
    listings_new: int = 0
    listings_notified: int = 0
    error_message: str | None = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None


@dataclass
class Label:
    id: int | None = None
    notification_id: int = 0
    label: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)


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
    free_shipping INTEGER DEFAULT 0,
    new_publish_hours INTEGER,
    region TEXT,
    cron_expression TEXT,
    account_state_file TEXT,
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
    seller_rating REAL DEFAULT 0.0,
    seller_registration_days INTEGER DEFAULT 0,
    wants_count INTEGER DEFAULT 0,
    original_price TEXT,
    tags TEXT,
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
    created_at TEXT NOT NULL,
    ai_relevance REAL,
    ai_reason TEXT,
    sent_at TEXT,
    channels_sent TEXT
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
