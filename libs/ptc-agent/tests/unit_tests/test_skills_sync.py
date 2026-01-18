import json

from ptc_agent.core.sandbox import PTCSandbox


async def test_sync_skills_skips_when_no_local_files(sandbox_instance: PTCSandbox, monkeypatch):
    async def _compute(_roots):
        return {"version": "v1", "files": {}}

    monkeypatch.setattr(sandbox_instance, "_compute_skills_manifest", _compute)

    uploaded = False

    async def _upload(_dirs):
        nonlocal uploaded
        uploaded = True

    monkeypatch.setattr(sandbox_instance, "_upload_skills", _upload)

    async def _read(_path):
        return None

    monkeypatch.setattr(sandbox_instance, "aread_file_text", _read)

    did_upload = await sandbox_instance.sync_skills(
        [("/tmp/user", "/home/daytona/skills"), ("/tmp/project", "/home/daytona/skills")],
        reusing_sandbox=True,
    )

    assert did_upload is False
    assert uploaded is False


async def test_sync_skills_uploads_when_remote_missing(sandbox_instance: PTCSandbox, monkeypatch):
    async def _compute(_roots):
        return {"version": "v1", "files": {"a/SKILL.md": {"size": 1, "mtime_ns": 1}}}

    monkeypatch.setattr(sandbox_instance, "_compute_skills_manifest", _compute)

    async def _read(_path):
        return None

    monkeypatch.setattr(sandbox_instance, "aread_file_text", _read)

    calls: list[str] = []

    async def _upload(_dirs):
        calls.append("upload")

    monkeypatch.setattr(sandbox_instance, "_upload_skills", _upload)

    progress: list[str] = []

    did_upload = await sandbox_instance.sync_skills(
        [("/tmp/user", "/home/daytona/skills"), ("/tmp/project", "/home/daytona/skills")],
        reusing_sandbox=True,
        on_progress=progress.append,
    )

    assert did_upload is True
    assert calls == ["upload"]
    assert progress == ["Uploading skills..."]


async def test_sync_skills_skips_when_versions_match_and_reusing(sandbox_instance: PTCSandbox, monkeypatch):
    async def _compute(_roots):
        return {"version": "v1", "files": {"a/SKILL.md": {"size": 1, "mtime_ns": 1}}}

    monkeypatch.setattr(sandbox_instance, "_compute_skills_manifest", _compute)

    async def _read(_path):
        return json.dumps({"version": "v1"})

    monkeypatch.setattr(sandbox_instance, "aread_file_text", _read)

    uploaded = False

    async def _upload(_dirs):
        nonlocal uploaded
        uploaded = True

    monkeypatch.setattr(sandbox_instance, "_upload_skills", _upload)

    did_upload = await sandbox_instance.sync_skills(
        [("/tmp/user", "/home/daytona/skills"), ("/tmp/project", "/home/daytona/skills")],
        reusing_sandbox=True,
    )

    assert did_upload is False
    assert uploaded is False


async def test_sync_skills_uploads_when_versions_match_but_new_sandbox(sandbox_instance: PTCSandbox, monkeypatch):
    async def _compute(_roots):
        return {"version": "v1", "files": {"a/SKILL.md": {"size": 1, "mtime_ns": 1}}}

    monkeypatch.setattr(sandbox_instance, "_compute_skills_manifest", _compute)

    async def _read(_path):
        return json.dumps({"version": "v1"})

    monkeypatch.setattr(sandbox_instance, "aread_file_text", _read)

    calls: list[str] = []

    async def _upload(_dirs):
        calls.append("upload")

    monkeypatch.setattr(sandbox_instance, "_upload_skills", _upload)

    did_upload = await sandbox_instance.sync_skills(
        [("/tmp/user", "/home/daytona/skills"), ("/tmp/project", "/home/daytona/skills")],
        reusing_sandbox=False,
    )

    assert did_upload is True
    assert calls == ["upload"]
