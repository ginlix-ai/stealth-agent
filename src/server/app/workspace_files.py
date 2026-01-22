"""Workspace Files API Router.

Provides live file operations against a workspace's Daytona sandbox.

Design goals:
- Proxy all file access through the backend (UI clients never talk to Daytona directly).
- Auto-start stopped workspaces.
- Support both virtual paths ("results/foo.txt") and absolute sandbox paths
  ("/home/daytona/results/foo.txt").
- Return virtual paths to clients for a consistent UX.

Endpoints:
- GET  /api/v1/workspaces/{workspace_id}/files
- GET  /api/v1/workspaces/{workspace_id}/files/read
- GET  /api/v1/workspaces/{workspace_id}/files/download
- POST /api/v1/workspaces/{workspace_id}/files/upload
"""

from __future__ import annotations

import mimetypes
from typing import Any

from fastapi import APIRouter, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import Response, StreamingResponse

from src.server.database.workspace_db import get_workspace as db_get_workspace
from src.server.services.workspace_manager import WorkspaceManager

router = APIRouter(prefix="/api/v1/workspaces", tags=["Workspace Files"])

_SYSTEM_DIR_PREFIXES = ("code/", "tools/", "mcp_servers/", "skills/")

# Generous but bounded defaults.
DEFAULT_READ_LIMIT_LINES = 20_000
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50MB


def _require_workspace_owner(workspace: dict[str, Any] | None, *, user_id: str, workspace_id: str) -> None:
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if workspace.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    if workspace.get("status") == "deleted":
        raise HTTPException(status_code=404, detail="Workspace not found")


def _to_client_path(sandbox: Any, absolute_path: str) -> str:
    """Convert an absolute sandbox path into a virtual client path.

    The CLI and web UX prefer paths like "results/foo.txt" (no leading slash),
    while still preserving true absolute /tmp paths.
    """

    virtual_path = sandbox.virtualize_path(absolute_path)

    # Keep /tmp paths absolute.
    if virtual_path.startswith("/tmp/"):
        return virtual_path

    # Strip the leading slash for working-directory paths.
    if virtual_path.startswith("/"):
        return virtual_path[1:]

    return virtual_path


def _is_system_path(client_path: str) -> bool:
    return any(client_path.startswith(prefix) for prefix in _SYSTEM_DIR_PREFIXES)


@router.get("/{workspace_id}/files")
async def list_workspace_files(
    workspace_id: str,
    x_user_id: str = Header(..., alias="X-User-Id", description="User ID"),
    path: str = Query(".", description="Directory to list (virtual or absolute)."),
    include_system: bool = Query(False, description="Include system directories (code/, tools/, mcp_servers/, skills/)."),
    pattern: str = Query("**/*", description="Glob pattern (evaluated in the sandbox)."),
) -> dict[str, Any]:
    """List files in a workspace's live sandbox."""

    workspace = await db_get_workspace(workspace_id)
    _require_workspace_owner(workspace, user_id=x_user_id, workspace_id=workspace_id)

    manager = WorkspaceManager.get_instance()
    session = await manager.get_session_for_workspace(workspace_id)

    sandbox = getattr(session, "sandbox", None)
    if sandbox is None:
        raise HTTPException(status_code=503, detail="Sandbox not available")

    # aglob_files returns absolute sandbox paths.
    absolute_paths: list[str] = await sandbox.aglob_files(pattern, path=path)

    files: list[str] = []
    for absolute_path in absolute_paths:
        client_path = _to_client_path(sandbox, absolute_path)
        if not include_system and _is_system_path(client_path):
            continue
        files.append(client_path)

    return {"workspace_id": workspace_id, "path": path, "files": files}


@router.get("/{workspace_id}/files/read")
async def read_workspace_file(
    workspace_id: str,
    path: str = Query(..., description="File path (virtual or absolute)."),
    offset: int = Query(0, ge=0, description="Line offset (0-based)."),
    limit: int = Query(DEFAULT_READ_LIMIT_LINES, ge=1, le=DEFAULT_READ_LIMIT_LINES, description="Max lines."),
    x_user_id: str = Header(..., alias="X-User-Id", description="User ID"),
) -> dict[str, Any]:
    """Read a file from the workspace's live sandbox."""

    workspace = await db_get_workspace(workspace_id)
    _require_workspace_owner(workspace, user_id=x_user_id, workspace_id=workspace_id)

    manager = WorkspaceManager.get_instance()
    session = await manager.get_session_for_workspace(workspace_id)

    sandbox = getattr(session, "sandbox", None)
    if sandbox is None:
        raise HTTPException(status_code=503, detail="Sandbox not available")

    normalized, error = sandbox.validate_and_normalize_path(path)
    if error:
        raise HTTPException(status_code=403, detail=error)

    # Range read keeps payloads bounded.
    content = await sandbox.aread_file_range(normalized, offset=offset, limit=limit)
    if content is None:
        raise HTTPException(status_code=404, detail="File not found")

    client_path = _to_client_path(sandbox, normalized)
    mime, _enc = mimetypes.guess_type(client_path)

    return {
        "workspace_id": workspace_id,
        "path": client_path,
        "offset": offset,
        "limit": limit,
        "content": content,
        "mime": mime or "text/plain",
        "truncated": False,  # limit is enforced; UI can request more with offset.
    }


@router.get("/{workspace_id}/files/download")
async def download_workspace_file(
    workspace_id: str,
    path: str = Query(..., description="File path (virtual or absolute)."),
    x_user_id: str = Header(..., alias="X-User-Id", description="User ID"),
) -> Response:
    """Download raw bytes from the workspace's live sandbox."""

    workspace = await db_get_workspace(workspace_id)
    _require_workspace_owner(workspace, user_id=x_user_id, workspace_id=workspace_id)

    manager = WorkspaceManager.get_instance()
    session = await manager.get_session_for_workspace(workspace_id)

    sandbox = getattr(session, "sandbox", None)
    if sandbox is None:
        raise HTTPException(status_code=503, detail="Sandbox not available")

    normalized, error = sandbox.validate_and_normalize_path(path)
    if error:
        raise HTTPException(status_code=403, detail=error)

    content = await sandbox.adownload_file_bytes(normalized)
    if content is None:
        raise HTTPException(status_code=404, detail="File not found")

    client_path = _to_client_path(sandbox, normalized)
    filename = client_path.split("/")[-1] if client_path else "download"
    mime, _enc = mimetypes.guess_type(filename)

    return StreamingResponse(
        iter([content]),
        media_type=mime or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{workspace_id}/files/upload")
async def upload_workspace_file(
    workspace_id: str,
    x_user_id: str = Header(..., alias="X-User-Id", description="User ID"),
    path: str | None = Query(None, description="Destination path (virtual or absolute). Defaults to filename."),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """Upload a file to the workspace's live sandbox."""

    workspace = await db_get_workspace(workspace_id)
    _require_workspace_owner(workspace, user_id=x_user_id, workspace_id=workspace_id)

    manager = WorkspaceManager.get_instance()
    session = await manager.get_session_for_workspace(workspace_id)

    sandbox = getattr(session, "sandbox", None)
    if sandbox is None:
        raise HTTPException(status_code=503, detail="Sandbox not available")

    dest = path or file.filename
    if not dest:
        raise HTTPException(status_code=400, detail="Destination path is required")

    normalized, error = sandbox.validate_and_normalize_path(dest)
    if error:
        raise HTTPException(status_code=403, detail=error)

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large")

    ok = await sandbox.aupload_file_bytes(normalized, content)
    if not ok:
        raise HTTPException(status_code=500, detail="Upload failed")

    client_path = _to_client_path(sandbox, normalized)
    return {
        "workspace_id": workspace_id,
        "path": client_path,
        "size": len(content),
        "filename": file.filename,
    }
