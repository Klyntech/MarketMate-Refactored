"""
marketmate.backup
─────────────────
Backup & Replication System for MarketMate.

Dual-write to MONGODB_URI + MONGODB_REPLICA_URI simultaneously,
with automated daily Google Drive backups (cron 2 AM, service account).

Components:
  1. DualWriteManager   — writes to primary + replica MongoDB on every operation
  2. GoogleDriveBackup  — daily JSON export to Google Drive via service account
  3. BackupScheduler    — cron-based backup orchestration (2 AM daily)

Architecture:
  ┌─────────────────────────────────────────────────────────────┐
  │ Application Code                                           │
  │   └── marketmate.db.repositories.*                          │
  │         └── DualWriteManager.write(collection, doc)        │
  │               ├── Primary:   MONGODB_URI                   │
  │               └── Replica:   MONGODB_REPLICA_URI           │
  │                                                             │
  │ BackupScheduler (cron 2 AM)                                │
  │   └── GoogleDriveBackup.export_and_upload()                │
  │         ├── Export all collections as JSON                  │
  │         ├── Compress to .tar.gz                             │
  │         └── Upload to Google Drive (service account)        │
  └─────────────────────────────────────────────────────────────┘
"""

from marketmate.backup.dual_write import DualWriteManager
from marketmate.backup.gdrive import GoogleDriveBackup
from marketmate.backup.scheduler import BackupScheduler

__all__ = [
    "DualWriteManager",
    "GoogleDriveBackup",
    "BackupScheduler",
]
