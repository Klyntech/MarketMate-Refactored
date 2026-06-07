"""
marketmate/platform/academy_repo.py
───────────────────────────────────
AcademyRepo — MongoDB-only MMAcademy data access.

Migrated from db/academy.py. Student progress, badges, certificates,
module CMS with versioning, and interactive chart storage.

Collections:
  user_progress         → per-module completion state, quiz scores, exercise feedback
  user_badges           → badges earned per student
  academy_certificates  → issued certificate IDs for public verification
  academy_modules       → live & draft module content with versioning (CMS)
  academy_charts        → interactive chart data storage
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from marketmate.core.logger import get_logger
from marketmate.db.core import mongo_manager

log = get_logger("platform.academy_repo")


class AcademyRepo:
    """
    MongoDB-only repository for MMAcademy data.

    Covers student progress, badges, certificates, module CMS,
    and interactive chart storage.
    """

    def __init__(self) -> None:
        self._manager = mongo_manager

    async def _db(self):
        """Return the Motor database or None. Always safe."""
        try:
            return await self._manager.get_db()
        except Exception as exc:
            log.warning("academy_db_unavailable", error=str(exc))
            return None

    # ═════════════════════════════════════════════════════════════════════════
    # user_progress
    # ═════════════════════════════════════════════════════════════════════════

    async def get_progress(self, google_id: str) -> list[dict]:
        """Return all progress records for a student."""
        database = await self._db()
        if database is None:
            return []
        try:
            cursor = database["user_progress"].find(
                {"google_id": google_id}, {"_id": 0}
            )
            return await cursor.to_list(length=1_000)
        except Exception as exc:
            log.error("get_progress_failed", google_id=google_id, error=str(exc))
            return []

    async def get_course_progress(self, google_id: str, course_id: str) -> list[dict]:
        """Return all progress records for a student within a specific course."""
        database = await self._db()
        if database is None:
            return []
        try:
            cursor = database["user_progress"].find(
                {"google_id": google_id, "course_id": course_id}, {"_id": 0}
            )
            return await cursor.to_list(length=500)
        except Exception as exc:
            log.error("get_course_progress_failed", google_id=google_id,
                      course_id=course_id, error=str(exc))
            return []

    async def mark_started(self, google_id: str, course_id: str, module_id: str) -> None:
        """Mark a module as started (idempotent — won't overwrite completed status)."""
        database = await self._db()
        if database is None:
            return
        try:
            await database["user_progress"].update_one(
                {"google_id": google_id, "course_id": course_id, "module_id": module_id},
                {
                    "$setOnInsert": {
                        "status":     "in_progress",
                        "started_at": datetime.now(timezone.utc),
                    }
                },
                upsert=True,
            )
        except Exception as exc:
            log.error("mark_started_failed", google_id=google_id,
                      module_id=module_id, error=str(exc))

    async def mark_completed(
        self,
        google_id: str,
        course_id: str,
        module_id: str,
        quiz_score: Optional[float] = None,
    ) -> None:
        """Mark a module as completed and optionally store quiz score."""
        database = await self._db()
        if database is None:
            return
        try:
            now = datetime.now(timezone.utc)
            set_payload: dict = {"completed_at": now}
            if quiz_score is not None:
                set_payload["quiz_score"] = round(quiz_score, 2)

            existing = await database["user_progress"].find_one(
                {"google_id": google_id, "course_id": course_id, "module_id": module_id}
            )
            if existing and existing.get("status") == "completed":
                if quiz_score is not None:
                    old_score = existing.get("quiz_score", 0) or 0
                    if quiz_score > old_score:
                        set_payload["quiz_score"] = round(quiz_score, 2)
            else:
                set_payload["status"] = "completed"

            await database["user_progress"].update_one(
                {"google_id": google_id, "course_id": course_id, "module_id": module_id},
                {
                    "$set": set_payload,
                    "$inc": {"quiz_attempts": 1},
                    "$setOnInsert": {"started_at": now},
                },
                upsert=True,
            )
            log.info("module_completed", google_id=google_id, module_id=module_id,
                     quiz_score=quiz_score)
        except Exception as exc:
            log.error("mark_completed_failed", google_id=google_id,
                      module_id=module_id, error=str(exc))

    async def submit_exercise(
        self,
        google_id:  str,
        course_id:  str,
        module_id:  str,
        submission: str,
        feedback:   str,
    ) -> None:
        """Store exercise submission and AI-generated feedback."""
        database = await self._db()
        if database is None:
            return
        try:
            await database["user_progress"].update_one(
                {"google_id": google_id, "course_id": course_id, "module_id": module_id},
                {"$set": {
                    "exercise": {
                        "submission": submission,
                        "feedback":   feedback,
                        "graded_at":  datetime.now(timezone.utc),
                    }
                }},
                upsert=True,
            )
        except Exception as exc:
            log.error("submit_exercise_failed", google_id=google_id,
                      module_id=module_id, error=str(exc))

    # ═════════════════════════════════════════════════════════════════════════
    # user_badges
    # ═════════════════════════════════════════════════════════════════════════

    async def get_badges(self, google_id: str) -> list[dict]:
        """Return all badges earned by a student."""
        database = await self._db()
        if database is None:
            return []
        try:
            cursor = database["user_badges"].find(
                {"google_id": google_id}, {"_id": 0}
            ).sort("earned_at", -1)
            return await cursor.to_list(length=500)
        except Exception as exc:
            log.error("get_badges_failed", google_id=google_id, error=str(exc))
            return []

    async def award_badge(self, google_id: str, badge_id: str) -> None:
        """Award a badge (idempotent — won't duplicate if already awarded)."""
        database = await self._db()
        if database is None:
            return
        try:
            existing = await database["user_badges"].find_one(
                {"google_id": google_id, "badge_id": badge_id}
            )
            if existing:
                return
            await database["user_badges"].insert_one({
                "google_id": google_id,
                "badge_id":  badge_id,
                "earned_at": datetime.now(timezone.utc),
            })
            log.info("badge_awarded", google_id=google_id, badge_id=badge_id)
        except Exception as exc:
            log.error("award_badge_failed", google_id=google_id,
                      badge_id=badge_id, error=str(exc))

    # ═════════════════════════════════════════════════════════════════════════
    # academy_certificates
    # ═════════════════════════════════════════════════════════════════════════

    async def issue_certificate(
        self,
        google_id: str,
        full_name: str,
        course_id: str,
    ) -> str:
        """Issue a certificate and return the cert_id."""
        database = await self._db()
        if database is None:
            return ""
        try:
            existing = await database["academy_certificates"].find_one(
                {"google_id": google_id, "course_id": course_id}
            )
            if existing:
                return existing["cert_id"]

            cert_id = str(uuid.uuid4()).replace("-", "")[:24]
            await database["academy_certificates"].insert_one({
                "cert_id":   cert_id,
                "google_id": google_id,
                "full_name": full_name,
                "course_id": course_id,
                "issued_at": datetime.now(timezone.utc),
            })
            log.info("certificate_issued", google_id=google_id,
                     course_id=course_id, cert_id=cert_id)
            return cert_id
        except Exception as exc:
            log.error("issue_certificate_failed", google_id=google_id, error=str(exc))
            return ""

    async def get_certificate(self, google_id: str, course_id: str) -> Optional[dict]:
        """Return a student's certificate for a specific course, or None."""
        database = await self._db()
        if database is None:
            return None
        try:
            return await database["academy_certificates"].find_one(
                {"google_id": google_id, "course_id": course_id}, {"_id": 0}
            )
        except Exception as exc:
            log.error("get_certificate_failed", google_id=google_id, error=str(exc))
            return None

    async def verify_certificate(self, cert_id: str) -> Optional[dict]:
        """Public endpoint — verify a certificate by cert_id."""
        database = await self._db()
        if database is None:
            return None
        try:
            return await database["academy_certificates"].find_one(
                {"cert_id": cert_id}, {"_id": 0}
            )
        except Exception as exc:
            log.error("verify_certificate_failed", cert_id=cert_id, error=str(exc))
            return None

    # ═════════════════════════════════════════════════════════════════════════
    # academy_modules — CMS with versioning
    # ═════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _parse_course_id(module_id: str) -> str:
        """Extract course_id from module_id like '1-3' -> '1'."""
        parts = module_id.split("-", 1)
        return parts[0] if parts else "1"

    async def save_module_draft(
        self,
        module_id: str,
        title: str,
        num: str,
        dur: str,
        exc: str,
        body: str,
        brief: str = "",
        draft_text: str = "",
        quiz: Optional[list] = None,
        chart_ref: Optional[str] = None,
    ) -> str:
        """Save a module as draft. Returns the module_id."""
        database = await self._db()
        if database is None:
            return ""
        try:
            course_id = self._parse_course_id(module_id)
            now = datetime.now(timezone.utc)

            existing = await database["academy_modules"].find_one(
                {"module_id": module_id, "status": "draft"}
            )

            doc: dict = {
                "module_id": module_id,
                "course_id": course_id,
                "title": title,
                "num": num,
                "dur": dur,
                "exc": exc,
                "body": body,
                "quiz": quiz or [],
                "brief": brief,
                "draft_text": draft_text,
                "reviews": [],
                "updated_at": now,
            }

            if chart_ref is not None:
                doc["chart_ref"] = chart_ref

            if existing:
                await database["academy_modules"].update_one(
                    {"module_id": module_id, "status": "draft"},
                    {"$set": doc}
                )
                log.info("module_draft_updated", module_id=module_id)
            else:
                doc["status"] = "draft"
                doc["version"] = 0
                doc["created_at"] = now
                doc["published_at"] = None
                doc["published_by"] = ""
                doc["previous_version"] = None
                if chart_ref is None:
                    doc["chart_ref"] = ""
                await database["academy_modules"].insert_one(doc)
                log.info("module_draft_created", module_id=module_id)

            return module_id
        except Exception as exc:
            log.error("save_module_draft_failed", module_id=module_id, error=str(exc))
            return ""

    async def publish_module(self, module_id: str, published_by: str = "admin") -> bool:
        """Publish a draft module — immediately replaces any live version."""
        database = await self._db()
        if database is None:
            return False
        try:
            now = datetime.now(timezone.utc)

            draft = await database["academy_modules"].find_one(
                {"module_id": module_id, "status": "draft"}
            )
            if not draft:
                log.error("publish_module_no_draft", module_id=module_id)
                return False

            # Archive any existing live version
            live = await database["academy_modules"].find_one(
                {"module_id": module_id, "status": "live"}
            )
            prev_version = 0
            if live:
                prev_version = live.get("version", 0)
                await database["academy_modules"].update_one(
                    {"module_id": module_id, "status": "live"},
                    {"$set": {"status": "archived", "archived_at": now}}
                )

            # Promote draft to live
            new_version = prev_version + 1
            await database["academy_modules"].update_one(
                {"module_id": module_id, "status": "draft"},
                {"$set": {
                    "status": "live",
                    "version": new_version,
                    "published_at": now,
                    "published_by": published_by,
                    "previous_version": prev_version,
                }}
            )

            log.info("module_published", module_id=module_id, version=new_version,
                     published_by=published_by)
            return True
        except Exception as exc:
            log.error("publish_module_failed", module_id=module_id, error=str(exc))
            return False

    async def get_live_modules(self) -> list[dict]:
        """Return all live modules — public Academy page data."""
        database = await self._db()
        if database is None:
            return []
        try:
            cursor = database["academy_modules"].find(
                {"status": "live"}, {"_id": 0}
            ).sort([("course_id", 1), ("module_id", 1)])
            return await cursor.to_list(length=500)
        except Exception as exc:
            log.error("get_live_modules_failed", error=str(exc))
            return []

    async def get_all_modules_admin(self) -> list[dict]:
        """Return all modules (live + draft) for the admin dashboard."""
        database = await self._db()
        if database is None:
            return []
        try:
            cursor = database["academy_modules"].find(
                {"status": {"$in": ["live", "draft"]}}, {"_id": 0}
            ).sort([("course_id", 1), ("module_id", 1)])
            return await cursor.to_list(length=500)
        except Exception as exc:
            log.error("get_all_modules_admin_failed", error=str(exc))
            return []

    async def get_module(self, module_id: str, status: Optional[str] = None) -> Optional[dict]:
        """Get a specific module by ID. Prefers live, then draft."""
        database = await self._db()
        if database is None:
            return None
        try:
            if status:
                return await database["academy_modules"].find_one(
                    {"module_id": module_id, "status": status}, {"_id": 0}
                )
            # Prefer live, then draft
            live = await database["academy_modules"].find_one(
                {"module_id": module_id, "status": "live"}, {"_id": 0}
            )
            if live:
                return live
            return await database["academy_modules"].find_one(
                {"module_id": module_id, "status": "draft"}, {"_id": 0}
            )
        except Exception as exc:
            log.error("get_module_failed", module_id=module_id, error=str(exc))
            return None

    async def delete_module(self, module_id: str) -> bool:
        """Delete a draft module. Live modules cannot be deleted."""
        database = await self._db()
        if database is None:
            return False
        try:
            result = await database["academy_modules"].delete_one(
                {"module_id": module_id, "status": "draft"}
            )
            if result.deleted_count > 0:
                log.info("module_draft_deleted", module_id=module_id)
                return True
            log.warning("module_delete_failed_not_draft", module_id=module_id)
            return False
        except Exception as exc:
            log.error("delete_module_failed", module_id=module_id, error=str(exc))
            return False

    async def rollback_module(self, module_id: str) -> bool:
        """Rollback a live module to its previous archived version."""
        database = await self._db()
        if database is None:
            return False
        try:
            now = datetime.now(timezone.utc)

            live = await database["academy_modules"].find_one(
                {"module_id": module_id, "status": "live"}
            )
            if not live:
                log.warning("rollback_no_live", module_id=module_id)
                return False

            prev_version = live.get("previous_version", 0)
            if prev_version == 0:
                log.warning("rollback_no_previous", module_id=module_id)
                return False

            archived = await database["academy_modules"].find_one(
                {"module_id": module_id, "status": "archived", "version": prev_version}
            )
            if not archived:
                log.warning("rollback_archived_not_found",
                            module_id=module_id, version=prev_version)
                return False

            # Archive current live
            await database["academy_modules"].update_one(
                {"module_id": module_id, "status": "live"},
                {"$set": {"status": "archived", "archived_at": now}}
            )

            # Restore previous version as live
            await database["academy_modules"].update_one(
                {"module_id": module_id, "status": "archived", "version": prev_version},
                {"$set": {"status": "live", "republished_at": now}}
            )

            log.info("module_rolled_back", module_id=module_id,
                     from_version=live.get("version"), to_version=prev_version)
            return True
        except Exception as exc:
            log.error("rollback_module_failed", module_id=module_id, error=str(exc))
            return False

    async def update_module_reviews(self, module_id: str, reviews: list) -> None:
        """Store review results on the draft module."""
        database = await self._db()
        if database is None:
            return
        try:
            await database["academy_modules"].update_one(
                {"module_id": module_id, "status": "draft"},
                {"$set": {"reviews": reviews}}
            )
        except Exception as exc:
            log.error("update_module_reviews_failed", module_id=module_id, error=str(exc))

    async def update_module_chart_ref(self, module_id: str, chart_ref: str) -> bool:
        """Update chart_ref on both live and draft versions."""
        database = await self._db()
        if database is None:
            return False
        try:
            now = datetime.now(timezone.utc)
            updated = 0

            result = await database["academy_modules"].update_one(
                {"module_id": module_id, "status": "live"},
                {"$set": {"chart_ref": chart_ref, "updated_at": now}}
            )
            updated += result.modified_count

            result = await database["academy_modules"].update_one(
                {"module_id": module_id, "status": "draft"},
                {"$set": {"chart_ref": chart_ref, "updated_at": now}}
            )
            updated += result.modified_count

            if updated > 0:
                log.info("module_chart_ref_updated", module_id=module_id,
                         chart_ref=chart_ref, versions_updated=updated)
            return updated > 0
        except Exception as exc:
            log.error("update_module_chart_ref_failed", module_id=module_id,
                      chart_ref=chart_ref, error=str(exc))
            return False

    async def seed_modules_from_courses(self, courses_data: list[dict]) -> int:
        """One-time migration: seed academy_modules from hardcoded courses data."""
        database = await self._db()
        if database is None:
            return 0
        try:
            now = datetime.now(timezone.utc)
            count = 0

            for course in courses_data:
                course_id = str(course.get("id", ""))
                for mod in course.get("mods", []):
                    module_id = mod.get("id", "")
                    if not module_id:
                        continue

                    existing = await database["academy_modules"].find_one(
                        {"module_id": module_id, "status": "live"}
                    )
                    if existing:
                        continue

                    doc = {
                        "module_id": module_id,
                        "course_id": course_id,
                        "title": mod.get("title", ""),
                        "num": mod.get("num", ""),
                        "dur": mod.get("dur", ""),
                        "exc": mod.get("exc", ""),
                        "body": mod.get("body", ""),
                        "quiz": mod.get("quiz", []),
                        "version": 1,
                        "status": "live",
                        "brief": "",
                        "draft_text": "",
                        "reviews": [],
                        "created_at": now,
                        "published_at": now,
                        "published_by": "seed_migration",
                        "previous_version": None,
                        "updated_at": now,
                    }
                    await database["academy_modules"].insert_one(doc)
                    count += 1

            log.info("modules_seeded", count=count)
            return count
        except Exception as exc:
            log.error("seed_modules_failed", error=str(exc))
            return 0

    # ═════════════════════════════════════════════════════════════════════════
    # academy_charts
    # ═════════════════════════════════════════════════════════════════════════

    async def save_chart(
        self,
        chart_id: str,
        module_id: str,
        concept: str,
        title: str,
        subtitle: str,
        candles: list,
        annotations: list,
        png_url: str,
    ) -> bool:
        """Upsert a chart document. Returns True on success."""
        database = await self._db()
        if database is None:
            return False
        try:
            now = datetime.now(timezone.utc)
            doc = {
                "chart_id": chart_id,
                "module_id": module_id,
                "concept": concept,
                "title": title,
                "subtitle": subtitle,
                "candles": candles,
                "annotations": annotations,
                "png_url": png_url,
                "updated_at": now,
            }
            await database["academy_charts"].update_one(
                {"chart_id": chart_id},
                {"$set": doc, "$setOnInsert": {"created_at": now}},
                upsert=True,
            )
            log.info("chart_saved", chart_id=chart_id, module_id=module_id)
            return True
        except Exception as exc:
            log.error("save_chart_failed", chart_id=chart_id, error=str(exc))
            return False

    async def get_chart(self, chart_id: str) -> Optional[dict]:
        """Return a chart document by chart_id, or None."""
        database = await self._db()
        if database is None:
            return None
        try:
            return await database["academy_charts"].find_one(
                {"chart_id": chart_id}, {"_id": 0}
            )
        except Exception as exc:
            log.error("get_chart_failed", chart_id=chart_id, error=str(exc))
            return None

    async def list_charts(self) -> list[dict]:
        """Return all charts (summary only — annotations replaced by count)."""
        database = await self._db()
        if database is None:
            return []
        try:
            charts = []
            cursor = database["academy_charts"].find(
                {},
                {"chart_id": 1, "module_id": 1, "concept": 1,
                 "title": 1, "timeframe": 1, "annotations": 1, "updated_at": 1},
            ).sort("updated_at", -1)
            async for doc in cursor:
                doc.pop("_id", None)
                ann_count = len(doc.get("annotations", []))
                doc["annotations"] = ann_count
                charts.append(doc)
            return charts
        except Exception as exc:
            log.error("list_charts_failed", error=str(exc))
            return []

    async def find_chart_by_module_id(self, module_id: str) -> Optional[dict]:
        """Return a chart document by module_id, or None."""
        database = await self._db()
        if database is None:
            return None
        try:
            return await database["academy_charts"].find_one(
                {"module_id": module_id}, {"_id": 0}
            )
        except Exception as exc:
            log.error("find_chart_by_module_id_failed", module_id=module_id, error=str(exc))
            return None

    # ═════════════════════════════════════════════════════════════════════════
    # Indexes
    # ═════════════════════════════════════════════════════════════════════════

    async def ensure_indexes(self) -> None:
        """Create indexes on all academy collections."""
        database = await self._db()
        if database is None:
            return

        from pymongo import ASCENDING

        try:
            # user_progress
            await database["user_progress"].create_index(
                [("google_id", ASCENDING), ("course_id", ASCENDING),
                 ("module_id", ASCENDING)],
                unique=True, name="progress_unique",
            )

            # user_badges
            await database["user_badges"].create_index(
                [("google_id", ASCENDING), ("badge_id", ASCENDING)],
                unique=True, name="badge_unique",
            )
            await database["user_badges"].create_index([("google_id", ASCENDING)])

            # academy_certificates
            await database["academy_certificates"].create_index(
                [("cert_id", ASCENDING)], unique=True, name="cert_id_unique"
            )
            await database["academy_certificates"].create_index(
                [("google_id", ASCENDING), ("course_id", ASCENDING)]
            )

            # academy_modules
            await database["academy_modules"].create_index(
                [("module_id", ASCENDING), ("status", ASCENDING)],
                unique=True, name="module_id_status_unique",
            )
            await database["academy_modules"].create_index(
                [("status", ASCENDING), ("course_id", ASCENDING)],
                name="status_course_idx",
            )
            await database["academy_modules"].create_index(
                [("course_id", ASCENDING), ("module_id", ASCENDING)],
                name="course_module_idx",
            )

            # academy_charts
            await database["academy_charts"].create_index(
                [("chart_id", ASCENDING)], unique=True, name="chart_id_unique",
            )
            await database["academy_charts"].create_index(
                [("module_id", ASCENDING)], name="chart_module_idx",
            )

            log.info("academy_indexes_ensured")
        except Exception as exc:
            log.error("academy_ensure_indexes_failed", error=str(exc))
