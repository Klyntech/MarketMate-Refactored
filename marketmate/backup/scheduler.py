"""
marketmate.backup.scheduler
────────────────────────────
Backup scheduler — runs daily at 2 AM (configurable).

Orchestrates:
  1. Google Drive backup (JSON export + upload)
  2. Dual-write full sync (if replica recovered)
  3. Backup health reporting

Integrates with the Scheduler in core/scheduler.py via add_task().
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger
from marketmate.backup.gdrive import gdrive_backup
from marketmate.backup.dual_write import dual_write_manager

log = get_logger("backup.scheduler")

# Default: 2 AM UTC
DEFAULT_BACKUP_HOUR = 2
DEFAULT_BACKUP_MINUTE = 0


class BackupScheduler:
    """
    Daily backup scheduler.

    Checks every 60 seconds; fires backup at the configured time.
    Integrates with the main Scheduler via add_task().
    """

    def __init__(
        self,
        backup_hour: int = DEFAULT_BACKUP_HOUR,
        backup_minute: int = DEFAULT_BACKUP_MINUTE,
    ) -> None:
        self._backup_hour = backup_hour
        self._backup_minute = backup_minute
        self._last_backup_date: Optional[str] = None
        self._backup_count: int = 0
        self._fail_count: int = 0

    async def run_loop(self) -> None:
        """
        Main loop — check every 60 seconds and fire backup at scheduled time.

        This is the coro_fn passed to scheduler.add_task().
        """
        log.info(
            "backup_scheduler_started",
            scheduled_time=f"{self._backup_hour:02d}:{self._backup_minute:02d} UTC",
        )

        while True:
            try:
                now = datetime.now(timezone.utc)
                today_str = now.strftime("%Y-%m-%d")

                # Fire backup at the scheduled time, once per day
                if (now.hour == self._backup_hour and
                    now.minute == self._backup_minute and
                    self._last_backup_date != today_str):

                    log.info("backup_scheduler_firing", date=today_str)
                    await self._run_backup()
                    self._last_backup_date = today_str

                await asyncio.sleep(60)

            except asyncio.CancelledError:
                log.info("backup_scheduler_cancelled")
                break
            except Exception as exc:
                log.error("backup_scheduler_error", error=str(exc))
                await asyncio.sleep(60)

    async def _run_backup(self) -> None:
        """Execute the backup sequence."""
        self._backup_count += 1

        # 1. Google Drive backup
        try:
            file_id = await gdrive_backup.export_and_upload()
            if file_id:
                log.info("backup_gdrive_success", file_id=file_id)
            else:
                log.warning("backup_gdrive_skipped")
        except Exception as exc:
            self._fail_count += 1
            log.error("backup_gdrive_failed", error=str(exc))

        # 2. Dual-write full sync (catch-up any missed replica writes)
        try:
            from marketmate.db.core import mongo_manager as mm
            db = await mm.get_db()
            if db and dual_write_manager.status["connected"]:
                results = await dual_write_manager.full_sync(db)
                log.info("backup_dual_write_sync_complete",
                         collections_synced=len([v for v in results.values() if v >= 0]))
        except Exception as exc:
            log.warning("backup_dual_write_sync_failed", error=str(exc))

        log.info("backup_run_complete",
                 total_runs=self._backup_count,
                 failures=self._fail_count)

    @property
    def status(self) -> dict:
        """Return backup scheduler status."""
        return {
            "scheduled_time": f"{self._backup_hour:02d}:{self._backup_minute:02d} UTC",
            "last_backup_date": self._last_backup_date,
            "total_backups": self._backup_count,
            "failures": self._fail_count,
            "dual_write": dual_write_manager.status,
        }


# ─── Singleton ────────────────────────────────────────────────────────────────

backup_scheduler = BackupScheduler()
