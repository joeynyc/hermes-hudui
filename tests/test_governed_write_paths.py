from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import yaml
from fastapi import HTTPException

import backend.api.memory as memory_api
import backend.api.profiles as profiles_api
import backend.governance.action_adapter as action_adapter
from backend.api.memory import AddBody
from backend.api.profiles import ProfileEditBody, ProfileModelEdit
from backend.governance import FileObservation, FilePresence


def _unknown(path: str | Path) -> FileObservation:
    return FileObservation(
        path=Path(path),
        presence=FilePresence.UNKNOWN,
        reason="test_observer_failure",
    )


def test_memory_write_rejects_unknown_without_creating_target(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setattr(action_adapter, "observe_file", _unknown)

    with pytest.raises(HTTPException) as exc:
        memory_api.add_entry(AddBody(target="memory", content="must not write"))

    assert exc.value.status_code == 503
    assert "test_observer_failure" in exc.value.detail
    assert not (tmp_path / "memories" / "MEMORY.md").exists()


def test_profile_write_rejects_unknown_without_changing_config(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    profile_dir = tmp_path / "profiles" / "work"
    profile_dir.mkdir(parents=True)
    config_path = profile_dir / "config.yaml"
    original = yaml.safe_dump({"model": {"default": "before"}})
    config_path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(action_adapter, "observe_file", _unknown)

    with pytest.raises(HTTPException) as exc:
        profiles_api.update_profile_edit(
            "work",
            ProfileEditBody(model=ProfileModelEdit(default="after")),
        )

    assert exc.value.status_code == 503
    assert "test_observer_failure" in exc.value.detail
    assert config_path.read_text(encoding="utf-8") == original
    assert not (profile_dir / "SOUL.md").exists()


def test_memory_lock_serializes_concurrent_writers(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    facts = [f"concurrent fact {index}" for index in range(8)]

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda fact: memory_api.add_entry(
                    AddBody(target="memory", content=fact)
                ),
                facts,
            )
        )

    assert all(result["ok"] is True for result in results)
    assert set(memory_api._read_entries("memory")) == set(facts)