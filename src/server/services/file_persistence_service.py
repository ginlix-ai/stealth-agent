"""
File Persistence Service.

Syncs workspace files between Daytona sandboxes and PostgreSQL.

- Snapshots files to DB on workspace stop/delete
- Restores files to sandbox when sandbox is recreated
- Serves file metadata/content from DB when sandbox is stopped
"""

import asyncio
import hashlib
import logging
import mimetypes
import os
from datetime import datetime, timezone
from typing import Any

from src.server.database.workspace_file import (
    delete_removed_files,
    get_file as db_get_file,
    get_file_metadata_for_sync,
    get_files_for_workspace,
    get_workspace_total_size,
    update_file_mtime,
    upsert_file,
)

logger = logging.getLogger(__name__)

# Known binary file extensions (reused from workspace_files.py)
_BINARY_EXTENSIONS = frozenset(
    {
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".bmp",
        ".ico",
        ".tiff",
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".7z",
        ".rar",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".mp3",
        ".mp4",
        ".wav",
        ".avi",
        ".mov",
        ".mkv",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".sqlite",
        ".db",
        ".pickle",
        ".pkl",
    }
)

# Marker file written after restore to avoid duplicate restores
_SYNC_MARKER = "/home/daytona/.file_sync_marker"


def _is_binary_extension(file_path: str) -> bool:
    """Check if file extension indicates binary content."""
    _, ext = os.path.splitext(file_path)
    return ext.lower() in _BINARY_EXTENSIONS


def _detect_is_binary(file_path: str, content: bytes) -> bool:
    """Detect whether file content is binary."""
    if _is_binary_extension(file_path):
        return True
    try:
        content[:8192].decode("utf-8")
        return False
    except UnicodeDecodeError:
        return True


class FilePersistenceService:
    """Sync workspace files between Daytona sandbox and PostgreSQL."""

    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB per file
    MAX_WORKSPACE_SIZE = 1024 * 1024 * 1024  # 1GB total per workspace

    # Directories to exclude from sync (relative to /home/daytona/)
    EXCLUDE_DIRS = {
        "node_modules",
        ".venv",
        "__pycache__",
        ".git",
        "_internal",
        ".agent",
        "code",
        "tools",
        "mcp_servers",
        "skills",
        ".cache",
        ".npm",
        ".local",
        ".config",
        ".ipython",
    }

    # File extensions to exclude
    EXCLUDE_EXTENSIONS = {".pyc", ".pyo", ".so", ".dylib", ".o"}

    # Basenames to exclude
    EXCLUDE_BASENAMES = {".DS_Store", "Thumbs.db", "__init__.py"}

    @classmethod
    async def list_sandbox_files(cls, sandbox: Any) -> dict[str, dict[str, Any]]:
        """List user files in sandbox with metadata.

        Returns:
            Dict mapping virtual_path to {abs_path, file_name, file_size, mtime}.
            Empty dict if no files found.
        """
        exclude_flags = []
        for d in cls.EXCLUDE_DIRS:
            exclude_flags.append(f"-not -path '*/{d}/*'")
        for ext in cls.EXCLUDE_EXTENSIONS:
            exclude_flags.append(f"-not -name '*{ext}'")
        for name in cls.EXCLUDE_BASENAMES:
            exclude_flags.append(f"-not -name '{name}'")

        find_cmd = (
            f"find /home/daytona -type f "
            f"{' '.join(exclude_flags)} "
            f"-printf '%s\\t%T@\\t%p\\n' 2>/dev/null"
        )

        find_result = await sandbox.execute_bash_command(find_cmd, timeout=30)
        if not find_result.get("success") or not find_result.get("stdout", "").strip():
            return {}

        result: dict[str, dict[str, Any]] = {}
        for line in find_result["stdout"].strip().split("\n"):
            parts = line.split("\t", 2)
            if len(parts) != 3:
                continue

            size_str, mtime_str, abs_path = parts
            try:
                file_size = int(size_str)
            except ValueError:
                continue

            if file_size > cls.MAX_FILE_SIZE:
                continue

            virtual_path = abs_path
            if virtual_path.startswith("/home/daytona/"):
                virtual_path = virtual_path[len("/home/daytona/") :]
            elif virtual_path == "/home/daytona":
                continue

            if abs_path == _SYNC_MARKER:
                continue

            try:
                mtime = float(mtime_str)
            except ValueError:
                mtime = 0.0

            result[virtual_path] = {
                "abs_path": abs_path,
                "file_name": os.path.basename(abs_path),
                "file_size": file_size,
                "mtime": mtime,
            }

        return result

    @classmethod
    async def sync_to_db(cls, workspace_id: str, sandbox: Any) -> dict[str, Any]:
        """
        Snapshot workspace files from sandbox to PostgreSQL.

        Args:
            workspace_id: Workspace UUID
            sandbox: Sandbox instance with file access methods

        Returns:
            Sync result summary
        """
        result = {"synced": 0, "skipped": 0, "deleted": 0, "errors": 0, "total_size": 0}

        try:
            # 1. List files in sandbox
            sandbox_meta = await cls.list_sandbox_files(sandbox)

            if not sandbox_meta:
                logger.info(f"No files found for workspace {workspace_id}")
                deleted = await delete_removed_files(workspace_id, set())
                result["deleted"] = deleted
                return result

            sandbox_files = [
                {"virtual_path": vp, **info} for vp, info in sandbox_meta.items()
            ]
            total_size = sum(f["file_size"] for f in sandbox_files)

            # Check total workspace size limit
            if total_size > cls.MAX_WORKSPACE_SIZE:
                logger.warning(
                    f"Workspace {workspace_id} total size ({total_size}) exceeds limit "
                    f"({cls.MAX_WORKSPACE_SIZE}). Syncing anyway but this may be slow."
                )

            # 3. Get existing metadata from DB for incremental sync
            existing_meta = await get_file_metadata_for_sync(workspace_id)
            active_paths: set[str] = set()

            # 4. Pre-filter: skip files where size + mtime are unchanged
            changed_files: list[dict[str, Any]] = []
            for file_info in sandbox_files:
                virtual_path = file_info["virtual_path"]
                active_paths.add(virtual_path)

                db_meta = existing_meta.get(virtual_path)
                if db_meta is not None:
                    # Compare size and mtime — if both match, skip download
                    size_match = db_meta["file_size"] == file_info["file_size"]
                    mtime_match = (
                        db_meta["mtime_epoch"] is not None
                        and file_info["mtime"] > 0
                        and abs(db_meta["mtime_epoch"] - file_info["mtime"]) < 1.0
                    )
                    if size_match and mtime_match:
                        result["skipped"] += 1
                        continue

                changed_files.append(file_info)

            # 5. Download changed files in parallel batches
            batch_size = 10

            async def _process_file(file_info: dict[str, Any]) -> None:
                virtual_path = file_info["virtual_path"]
                try:
                    content = await sandbox.adownload_file_bytes(file_info["abs_path"])
                    if content is None:
                        result["errors"] += 1
                        return

                    content_hash = hashlib.sha256(content).hexdigest()

                    # Skip if hash matches despite size/mtime difference
                    db_meta = existing_meta.get(virtual_path)
                    if db_meta is not None and db_meta["content_hash"] == content_hash:
                        # Update DB mtime to match sandbox (e.g. after file restore)
                        if file_info["mtime"] > 0 and (
                            db_meta["mtime_epoch"] is None
                            or abs(db_meta["mtime_epoch"] - file_info["mtime"]) >= 1.0
                        ):
                            await update_file_mtime(
                                workspace_id,
                                virtual_path,
                                datetime.fromtimestamp(
                                    file_info["mtime"], tz=timezone.utc
                                ),
                            )
                        result["skipped"] += 1
                        return

                    is_binary = _detect_is_binary(virtual_path, content)

                    content_text = None
                    content_binary = None
                    if is_binary:
                        content_binary = content
                    else:
                        try:
                            content_text = content.decode("utf-8")
                        except UnicodeDecodeError:
                            is_binary = True
                            content_binary = content

                    mime, _ = mimetypes.guess_type(virtual_path)

                    sandbox_modified_at = None
                    if file_info["mtime"] > 0:
                        sandbox_modified_at = datetime.fromtimestamp(
                            file_info["mtime"], tz=timezone.utc
                        )

                    await upsert_file(
                        workspace_id=workspace_id,
                        file_path=virtual_path,
                        file_name=file_info["file_name"],
                        file_size=file_info["file_size"],
                        content_hash=content_hash,
                        content_text=content_text,
                        content_binary=content_binary,
                        mime_type=mime,
                        is_binary=is_binary,
                        permissions=None,
                        sandbox_modified_at=sandbox_modified_at,
                    )
                    result["synced"] += 1

                except Exception as e:
                    logger.warning(
                        f"Error syncing file {virtual_path} "
                        f"for workspace {workspace_id}: {e}"
                    )
                    result["errors"] += 1

            for i in range(0, len(changed_files), batch_size):
                batch = changed_files[i : i + batch_size]
                await asyncio.gather(
                    *[_process_file(f) for f in batch],
                    return_exceptions=False,
                )

            # 6. Delete files from DB that no longer exist in sandbox
            deleted = await delete_removed_files(workspace_id, active_paths)
            result["deleted"] = deleted

            result["total_size"] = await get_workspace_total_size(workspace_id)

            logger.info(
                f"File sync completed for workspace {workspace_id}: "
                f"synced={result['synced']}, skipped={result['skipped']}, "
                f"deleted={result['deleted']}, errors={result['errors']}"
            )

        except Exception as e:
            logger.error(f"File sync failed for workspace {workspace_id}: {e}")
            raise

        return result

    @classmethod
    async def restore_to_sandbox(
        cls, workspace_id: str, sandbox: Any
    ) -> dict[str, Any]:
        """
        Restore workspace files from DB to sandbox.

        Args:
            workspace_id: Workspace UUID
            sandbox: Sandbox instance

        Returns:
            Restore result summary
        """
        result = {"restored": 0, "errors": 0}

        try:
            files = await get_files_for_workspace(workspace_id, include_content=True)

            if not files:
                logger.info(f"No files to restore for workspace {workspace_id}")
                return result

            logger.info(f"Restoring {len(files)} files for workspace {workspace_id}")

            # Process in batches for parallel upload
            batch_size = 10
            for i in range(0, len(files), batch_size):
                batch = files[i : i + batch_size]
                tasks = [
                    cls._restore_single_file(sandbox, file_record)
                    for file_record in batch
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for j, res in enumerate(results):
                    if isinstance(res, Exception):
                        logger.warning(
                            f"Failed to restore {batch[j]['file_path']}: {res}"
                        )
                        result["errors"] += 1
                    elif res:
                        result["restored"] += 1
                    else:
                        result["errors"] += 1

            # Write sync marker
            try:
                marker_content = datetime.now(timezone.utc).isoformat().encode("utf-8")
                await sandbox.aupload_file_bytes(_SYNC_MARKER, marker_content)
            except Exception:
                pass  # Non-critical

            # Update DB mtimes to match restored files' new sandbox mtimes
            if result["restored"] > 0:
                try:
                    sandbox_meta = await cls.list_sandbox_files(sandbox)
                    for vpath, info in sandbox_meta.items():
                        if info["mtime"] > 0:
                            await update_file_mtime(
                                workspace_id,
                                vpath,
                                datetime.fromtimestamp(
                                    info["mtime"], tz=timezone.utc
                                ),
                            )
                except Exception as e:
                    logger.warning(
                        f"Mtime sync after restore failed for {workspace_id}: {e}"
                    )

            logger.info(
                f"File restore completed for workspace {workspace_id}: "
                f"restored={result['restored']}, errors={result['errors']}"
            )

        except Exception as e:
            logger.error(f"File restore failed for workspace {workspace_id}: {e}")
            raise

        return result

    @classmethod
    async def _restore_single_file(cls, sandbox: Any, file_record: dict) -> bool:
        """Restore a single file to sandbox."""
        abs_path = f"/home/daytona/{file_record['file_path']}"

        # Ensure parent directory exists
        parent_dir = os.path.dirname(abs_path)
        if parent_dir and parent_dir != "/home/daytona":
            await sandbox.acreate_directory(parent_dir)

        # Get content
        if file_record.get("is_binary") and file_record.get("content_binary"):
            content = file_record["content_binary"]
            if isinstance(content, memoryview):
                content = bytes(content)
        elif file_record.get("content_text") is not None:
            content = file_record["content_text"].encode("utf-8")
        else:
            return False

        return await sandbox.aupload_file_bytes(abs_path, content)

    @classmethod
    async def maybe_restore(cls, workspace_id: str, sandbox: Any) -> None:
        """
        Restore files from DB if sandbox was recreated (files lost).

        Checks for sync marker file. If absent, files were lost and need restore.
        """
        try:
            marker = await sandbox.adownload_file_bytes(_SYNC_MARKER)
            if marker is not None:
                # Marker exists — sandbox still has its files
                return

            # Check if we have any files in DB to restore
            files = await get_files_for_workspace(workspace_id, include_content=False)
            if not files:
                # No files saved — write marker and skip
                try:
                    marker_content = (
                        datetime.now(timezone.utc).isoformat().encode("utf-8")
                    )
                    await sandbox.aupload_file_bytes(_SYNC_MARKER, marker_content)
                except Exception:
                    pass
                return

            logger.info(
                f"Sync marker missing for workspace {workspace_id}. "
                f"Restoring {len(files)} files from DB."
            )
            await cls.restore_to_sandbox(workspace_id, sandbox)

        except Exception as e:
            logger.warning(f"Error in maybe_restore for workspace {workspace_id}: {e}")

    @classmethod
    async def get_file_tree(cls, workspace_id: str) -> list[dict[str, Any]]:
        """
        Get file metadata from DB for offline UI browsing.

        Returns flat list of file metadata (no content).
        """
        files = await get_files_for_workspace(workspace_id, include_content=False)
        return [
            {
                "path": f["file_path"],
                "name": f["file_name"],
                "size": f["file_size"],
                "mime_type": f.get("mime_type"),
                "is_binary": f.get("is_binary", False),
                "modified_at": f.get("sandbox_modified_at"),
            }
            for f in files
        ]

    @classmethod
    async def get_file_content(
        cls, workspace_id: str, file_path: str
    ) -> dict[str, Any] | None:
        """
        Get file content from DB for offline access.

        Returns file record with content, or None if not found.
        """
        return await db_get_file(workspace_id, file_path, include_content=True)
