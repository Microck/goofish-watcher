import logging
import random
from typing import TYPE_CHECKING

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import settings
from core.filter import filter_listings
from core.notifier import Notifier
from core.parser import normalize_listings
from core.scanner import goofish_client
from core.verifier import ai_verifier
from db.models import Query, ScanStatus
from db.store import store

if TYPE_CHECKING:
    from bot.main import GoofishBot

log = logging.getLogger(__name__)

CONSECUTIVE_FAILURE_THRESHOLD = 3
HEALTH_CHECK_INTERVAL_HOURS = 6
CLEANUP_INTERVAL_HOURS = 24
KEEP_ALIVE_INTERVAL_HOURS = 2


class WatcherCog:
    def __init__(self, bot: "GoofishBot"):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self.notifier = Notifier(bot)
        self._consecutive_failures = 0
        self._last_auth_alert = False

    async def start(self) -> None:
        queries = await store.get_all_queries(enabled_only=True)
        for query in queries:
            await self.schedule_query(query.id)

        self.scheduler.add_job(
            self._health_check_job,
            IntervalTrigger(hours=HEALTH_CHECK_INTERVAL_HOURS),
            id="health_check",
            replace_existing=True,
        )

        self.scheduler.add_job(
            self._cleanup_job,
            IntervalTrigger(hours=CLEANUP_INTERVAL_HOURS),
            id="cleanup",
            replace_existing=True,
        )

        self.scheduler.add_job(
            self._keep_alive_job,
            IntervalTrigger(hours=KEEP_ALIVE_INTERVAL_HOURS),
            id="keep_alive",
            replace_existing=True,
        )

        self.scheduler.start()
        log.info(f"Scheduler started with {len(queries)} queries")

    async def stop(self) -> None:
        self.scheduler.shutdown(wait=False)
        await goofish_client.close()
        await ai_verifier.close()

    async def schedule_query(self, query_id: int) -> None:
        query = await store.get_query(query_id)
        if not query or not query.enabled:
            return

        job_id = f"query_{query_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        jitter = random.randint(-settings.jitter_minutes, settings.jitter_minutes)
        interval = max(1, query.interval_minutes + jitter)

        self.scheduler.add_job(
            self._run_query_job,
            IntervalTrigger(minutes=interval),
            id=job_id,
            args=[query_id],
            replace_existing=True,
        )
        log.info(f"Scheduled query #{query_id} every {interval}m")

    def unschedule_query(self, query_id: int) -> None:
        job_id = f"query_{query_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            log.info(f"Unscheduled query #{query_id}")

    async def _run_query_job(self, query_id: int) -> None:
        query = await store.get_query(query_id)
        if not query or not query.enabled:
            return
        await self.run_scan(query)

    async def _health_check_job(self) -> None:
        log.info("Running health check")

        auth_ok = await goofish_client.check_auth()
        if not auth_ok and not self._last_auth_alert:
            await self._send_health_alert(
                "🔴 Cookie Expired",
                "Goofish authentication has expired. Update cookies.json and restart the bot.",
            )
            self._last_auth_alert = True
        elif auth_ok:
            self._last_auth_alert = False

        recent_failures = await store.get_recent_failures(hours=1)
        if recent_failures >= CONSECUTIVE_FAILURE_THRESHOLD:
            await self._send_health_alert(
                "⚠️ High Failure Rate",
                f"{recent_failures} scan failures in the last hour. Check logs for details.",
            )

    async def _cleanup_job(self) -> None:
        log.info("Running cleanup job")
        deleted = await store.cleanup_old_listings()
        log.info(f"Cleaned up {deleted} old listings")

    async def _keep_alive_job(self) -> None:
        log.debug("Running session keep-alive")
        await goofish_client.keep_alive()
        await goofish_client.refresh_cookies()

    async def _send_health_alert(self, title: str, message: str) -> None:
        try:
            user = await self.bot.fetch_user(settings.discord_user_id)
            embed = discord.Embed(
                title=title,
                description=message,
                color=discord.Color.red(),
            )
            await user.send(embed=embed)
        except Exception as e:
            log.error(f"Failed to send health alert: {e}")

    async def run_scan(self, query: Query) -> None:
        scan_id = await store.start_scan(query.id)  # type: ignore
        log.info(f"Starting scan #{scan_id} for query #{query.id}: {query.keyword}")

        try:
            all_listings = []
            page = 1
            max_pages = (settings.max_listings_per_scan // 50) + 1

            while len(all_listings) < settings.max_listings_per_scan and page <= max_pages:
                raw_listings = await goofish_client.search(
                    query.keyword,
                    page=page,
                    page_size=50,
                )
                if not raw_listings:
                    break
                all_listings.extend(raw_listings)
                page += 1

            if not all_listings:
                await store.finish_scan(scan_id, ScanStatus.COMPLETED, 0, 0, 0)
                self._consecutive_failures = 0
                return

            listings = normalize_listings(all_listings)
            listings = filter_listings(listings, query)

            listings_found = len(listings)
            listings_new = 0
            listings_notified = 0
            seen_streak = 0

            for listing in listings[: settings.max_listings_per_scan]:
                is_seen = await store.is_listing_seen(query.id, listing.id)  # type: ignore

                if is_seen:
                    seen_streak += 1
                    if seen_streak >= settings.seen_streak_stop:
                        log.info(f"Stopping scan: {seen_streak} consecutive seen listings")
                        break
                    continue

                seen_streak = 0
                listings_new += 1

                await store.mark_listing_seen(
                    query.id,  # type: ignore
                    listing.id,
                    listing.title,
                    listing.price,
                    listing.seller_id,
                )

                ai_result = await ai_verifier.verify(listing, query)

                if ai_result and query.ai_enabled:
                    if ai_result.confidence < query.ai_threshold:
                        log.debug(f"Skipping {listing.id}: confidence {ai_result.confidence}")
                        continue

                notification_id = await store.create_notification(
                    query.id,  # type: ignore
                    listing.id,
                    ai_relevance=ai_result.confidence if ai_result else None,
                    ai_reason=ai_result.reason if ai_result else None,
                )

                success = await self.notifier.send_listing(
                    listing,
                    query,
                    ai_confidence=ai_result.confidence if ai_result else None,
                    ai_reason=ai_result.reason if ai_result else None,
                )

                if success:
                    await store.mark_notification_sent(notification_id)
                    listings_notified += 1

            await store.finish_scan(
                scan_id,
                ScanStatus.COMPLETED,
                listings_found,
                listings_new,
                listings_notified,
            )
            self._consecutive_failures = 0
            log.info(
                f"Scan #{scan_id}: {listings_found} found, "
                f"{listings_new} new, {listings_notified} notified"
            )

        except Exception as e:
            log.exception(f"Scan #{scan_id} failed: {e}")
            await store.finish_scan(scan_id, ScanStatus.FAILED, error_message=str(e))
            self._consecutive_failures += 1

            if self._consecutive_failures >= CONSECUTIVE_FAILURE_THRESHOLD:
                msg = f"Query #{query.id} failed {self._consecutive_failures} times"
                await self._send_health_alert("⚠️ Consecutive Failures", msg)
