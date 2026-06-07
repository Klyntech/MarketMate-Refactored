"""
marketmate.backup.gdrive
─────────────────────────
Google Drive backup via service account.

Exports all MongoDB collections as JSON, compresses to .tar.gz,
and uploads to a specified Google Drive folder.

Authentication:
  Uses a Google service account JSON key file.
  Set GOOGLE_DRIVE_SERVICE_ACCOUNT_PATH in environment.
  Set GOOGLE_DRIVE_BACKUP_FOLDER_ID in environment.

The service account must have access to the target Drive folder.

Flow:
  1. Export all collections as JSON files to /tmp/marketmate_backup/
  2. Compress to marketmate_backup_YYYYMMDD_HHMM.tar.gz
  3. Upload to Google Drive
  4. Clean up temporary files
  5. Rotate old backups (keep last 30)
"""

from __future__ import annotations

import io
import json
import os
import tarfile
import tempfile
from datetime import datetime, timezone
from typing import Optional

from marketmate.core.logger import get_logger
from marketmate.db.core import mongo_manager

log = get_logger("backup.gdrive")

# Collections to export (in order)
BACKUP_COLLECTIONS = [
    "signal_archive",
    "trade_events",
    "subscribers",
    "trading_accounts",
    "training_data",
    "signal_state",
    "virtual_account_events",
    "virtual_account_snapshots",
    "virtual_account_metrics",
    "virtual_account_config",
    "candles",
    "trade_proximity",
    "subscriber_events",
    "payments",
    "signal_deliveries",
    "terms_acceptance",
    "admin_actions",
    "messages_sent",
]

# Maximum number of backups to keep on Drive
MAX_BACKUPS = 30


class GoogleDriveBackup:
    """
    Google Drive backup manager using service account authentication.

    Requirements:
      - google-api-python-client
      - google-auth
      - Service account JSON key file
    """

    def __init__(self) -> None:
        self._service_account_path = os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_PATH", "")
        self._folder_id = os.getenv("GOOGLE_DRIVE_BACKUP_FOLDER_ID", "")
        self._enabled = bool(self._service_account_path and self._folder_id)

    async def export_and_upload(self) -> Optional[str]:
        """
        Export all collections, compress, and upload to Google Drive.

        Returns the Drive file ID of the uploaded backup, or None on failure.
        """
        if not self._enabled:
            log.info("gdrive_backup_skipped", reason="not configured")
            return None

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
        backup_name = f"marketmate_backup_{timestamp}"

        try:
            # Step 1: Export collections to JSON
            json_dir = await self._export_collections(backup_name)
            if json_dir is None:
                return None

            # Step 2: Compress to .tar.gz
            tar_path = self._compress(json_dir, backup_name)
            if tar_path is None:
                return None

            # Step 3: Upload to Google Drive
            file_id = await self._upload(tar_path, backup_name)

            # Step 4: Clean up temp files
            self._cleanup(json_dir, tar_path)

            # Step 5: Rotate old backups
            if file_id:
                await self._rotate_backups()

            log.info("gdrive_backup_complete",
                     backup_name=backup_name,
                     file_id=file_id)
            return file_id

        except Exception as exc:
            log.error("gdrive_backup_failed", error=str(exc))
            return None

    async def _export_collections(self, backup_name: str) -> Optional[str]:
        """Export all MongoDB collections as JSON files."""
        db = await mongo_manager.get_db()
        if db is None:
            log.warning("gdrive_export_failed", reason="MongoDB unavailable")
            return None

        temp_dir = tempfile.mkdtemp(prefix="marketmate_backup_")

        for col_name in BACKUP_COLLECTIONS:
            try:
                docs = await db[col_name].find({}).to_list(length=None)
                file_path = os.path.join(temp_dir, f"{col_name}.json")
                with open(file_path, "w") as f:
                    json.dump(docs, f, default=str, indent=2)
                log.debug("gdrive_collection_exported",
                          collection=col_name, docs=len(docs))
            except Exception as exc:
                log.warning("gdrive_collection_export_failed",
                            collection=col_name, error=str(exc))

        # Add metadata
        metadata = {
            "backup_name": backup_name,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "collections": BACKUP_COLLECTIONS,
            "version": "6.2.0",
        }
        with open(os.path.join(temp_dir, "_metadata.json"), "w") as f:
            json.dump(metadata, f, indent=2)

        return temp_dir

    def _compress(self, source_dir: str, backup_name: str) -> Optional[str]:
        """Compress a directory into a .tar.gz file."""
        try:
            tar_path = os.path.join(
                tempfile.gettempdir(), f"{backup_name}.tar.gz"
            )
            with tarfile.open(tar_path, "w:gz") as tar:
                tar.add(source_dir, arcname=backup_name)
            log.info("gdrive_backup_compressed",
                     path=tar_path,
                     size_mb=round(os.path.getsize(tar_path) / 1024 / 1024, 2))
            return tar_path
        except Exception as exc:
            log.error("gdrive_compress_failed", error=str(exc))
            return None

    async def _upload(self, tar_path: str, backup_name: str) -> Optional[str]:
        """Upload the compressed backup to Google Drive."""
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload

            credentials = service_account.Credentials.from_service_account_file(
                self._service_account_path,
                scopes=["https://www.googleapis.com/auth/drive.file"],
            )
            service = build("drive", "v3", credentials=credentials)

            file_metadata = {
                "name": f"{backup_name}.tar.gz",
                "parents": [self._folder_id],
            }
            media = MediaFileUpload(tar_path, mimetype="application/gzip")

            result = service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id",
            ).execute()

            file_id = result.get("id")
            log.info("gdrive_upload_success", file_id=file_id)
            return file_id

        except ImportError:
            log.warning("gdrive_upload_skipped",
                        reason="google-api-python-client not installed")
            return None
        except Exception as exc:
            log.error("gdrive_upload_failed", error=str(exc))
            return None

    def _cleanup(self, json_dir: str, tar_path: str) -> None:
        """Remove temporary files."""
        import shutil
        try:
            if os.path.isdir(json_dir):
                shutil.rmtree(json_dir)
            if os.path.isfile(tar_path):
                os.remove(tar_path)
        except Exception as exc:
            log.warning("gdrive_cleanup_failed", error=str(exc))

    async def _rotate_backups(self) -> None:
        """Delete old backups beyond MAX_BACKUPS."""
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            credentials = service_account.Credentials.from_service_account_file(
                self._service_account_path,
                scopes=["https://www.googleapis.com/auth/drive.file"],
            )
            service = build("drive", "v3", credentials=credentials)

            # List all backup files in the folder
            results = service.files().list(
                q=f"'{self._folder_id}' in parents and name contains 'marketmate_backup_'",
                orderBy="createdTime",
                fields="files(id, name, createdTime)",
            ).execute()

            files = results.get("files", [])
            if len(files) <= MAX_BACKUPS:
                return

            # Delete oldest files beyond the limit
            to_delete = files[:len(files) - MAX_BACKUPS]
            for f in to_delete:
                try:
                    service.files().delete(fileId=f["id"]).execute()
                    log.info("gdrive_backup_rotated",
                             name=f["name"], file_id=f["id"])
                except Exception as exc:
                    log.warning("gdrive_rotation_delete_failed",
                                name=f["name"], error=str(exc))

        except ImportError:
            pass
        except Exception as exc:
            log.warning("gdrive_rotation_failed", error=str(exc))


# ─── Singleton ────────────────────────────────────────────────────────────────

gdrive_backup = GoogleDriveBackup()
