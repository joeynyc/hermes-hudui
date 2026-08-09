import json
from datetime import datetime
from subprocess import CompletedProcess

from backend.collectors.models import SessionInfo
from backend.services.replay_normalizer import normalize_session, replay_id_for_session


def _session() -> SessionInfo:
    return SessionInfo(
        id="session-1",
        source="cli",
        title="Replay test",
        started_at=datetime.fromtimestamp(100),
        ended_at=datetime.fromtimestamp(160),
        message_count=2,
        tool_call_count=0,
        input_tokens=10,
        output_tokens=20,
        estimated_cost_usd=0.02,
        model="gpt-test",
    )


def test_normalize_session_generates_stable_replay_and_receipt_hashes() -> None:
    messages = [
        {"id": 1, "role": "user", "content": "Build it", "timestamp": 101},
        {"id": 2, "role": "assistant", "content": "Done", "timestamp": 102},
    ]

    first = normalize_session(_session(), messages)
    second = normalize_session(_session(), messages)

    assert first.run.replay_id == replay_id_for_session("session-1")
    assert first.run.replay_id == second.run.replay_id
    assert first.run.hashes.redacted_replay_hash == second.run.hashes.redacted_replay_hash
    assert first.receipt is not None
    assert first.receipt.hashes.receipt_hash is not None


def test_normalize_session_classifies_tool_calls_separately() -> None:
    detail = normalize_session(
        _session(),
        [
            {
                "id": 1,
                "role": "assistant",
                "content": "I will inspect files.",
                "timestamp": 101,
                "tool_calls": '[{"function": {"name": "exec_command", "arguments": "{\\"cmd\\": \\"ls\\"}"}}]',
            }
        ],
    )

    event_types = [event.type for event in detail.events]

    assert "assistant_message" in event_types
    assert "terminal_command" in event_types
    assert detail.run.counts.tool_calls == 1
    assert any(artifact.type == "tool_call_list" for artifact in detail.artifacts)
    grouping = next(artifact for artifact in detail.artifacts if artifact.type == "tool_call_grouping")
    assert "- exec_command: 1" in grouping.content


def test_normalize_session_groups_repeated_tool_calls() -> None:
    detail = normalize_session(
        _session(),
        [
            {
                "id": 1,
                "role": "assistant",
                "content": "I will inspect files.",
                "timestamp": 101,
                "tool_calls": (
                    '[{"function": {"name": "exec_command", "arguments": "{\\"cmd\\": \\"ls\\"}"}},'
                    '{"function": {"name": "exec_command", "arguments": "{\\"cmd\\": \\"pwd\\"}"}},'
                    '{"function": {"name": "browser", "arguments": "{\\"url\\": \\"http://localhost\\"}"}}]'
                ),
            }
        ],
    )

    grouping = next(artifact for artifact in detail.artifacts if artifact.type == "tool_call_grouping")

    assert "- browser: 1" in grouping.content
    assert "- exec_command: 2" in grouping.content
    assert grouping.summary == "2 distinct tools used across 3 calls."


def test_normalize_session_turns_unknown_roles_into_warning_events() -> None:
    detail = normalize_session(
        _session(),
        [{"id": 1, "role": "alien", "content": "???", "timestamp": "bad-timestamp"}],
    )

    assert detail.events[0].type == "error"
    assert detail.events[0].status == "warning"
    assert detail.events[0].summary == "Unsupported role: alien"


def test_normalize_session_builds_mvp_proof_artifacts_and_test_counts() -> None:
    detail = normalize_session(
        _session(),
        [
            {"id": 1, "role": "user", "content": "Run tests", "timestamp": 101},
            {"id": 2, "role": "assistant", "content": "Running pytest.", "timestamp": 102},
            {"id": 3, "role": "tool", "content": "================ 12 passed, 1 failed in 0.5s ================", "timestamp": 103},
        ],
    )

    artifact_types = {artifact.type for artifact in detail.artifacts}

    assert {"transcript_summary", "cost_summary", "test_output", "terminal_output"}.issubset(artifact_types)
    assert detail.run.counts.tests_passed == 12
    assert detail.run.counts.tests_failed == 1
    assert detail.receipt.tests == {"passed": 12, "failed": 1, "command": None}
    terminal_artifact = next(artifact for artifact in detail.artifacts if artifact.type == "terminal_output")
    assert terminal_artifact.content == "[REDACTED_TERMINAL_OUTPUT]"


def test_normalize_session_detects_skill_names_without_inventing_hashes() -> None:
    detail = normalize_session(
        _session(),
        [
            {"id": 1, "role": "assistant", "content": "Using skill auth-helper to inspect login.", "timestamp": 101},
        ],
    )

    assert detail.run.counts.skills_used == 1
    assert detail.receipt is not None
    assert detail.receipt.skills_used == [{"name": "auth-helper", "version": None, "hash": None}]
    assert any(artifact.type == "skill_card" for artifact in detail.artifacts)


def test_normalize_session_detects_explicit_skill_mutation_events() -> None:
    detail = normalize_session(
        _session(),
        [
            {"id": 1, "role": "assistant", "content": "Created skill auth-helper and modified skill docs-helper.", "timestamp": 101},
        ],
    )

    events = {event.type: event for event in detail.events if event.type.startswith("skill_")}
    skills = {skill["name"] for skill in detail.receipt.skills_used}

    assert "skill_created" in events
    assert "skill_modified" in events
    assert events["skill_created"].metadata["skill_name"] == "auth-helper"
    assert events["skill_modified"].metadata["skill_name"] == "docs-helper"
    assert skills == {"auth-helper", "docs-helper"}


def test_normalize_session_detects_screenshot_and_browser_recording_paths() -> None:
    detail = normalize_session(
        _session(),
        [
            {
                "id": 1,
                "role": "assistant",
                "content": "Captured screenshot /tmp/replay-shot.png and browser recording /tmp/replay.webm.",
                "timestamp": 101,
            },
            {
                "id": 2,
                "role": "assistant",
                "content": "Captured from browser.",
                "timestamp": 102,
                "tool_calls": '[{"function": {"name": "browser", "arguments": "{\\"screenshot_path\\": \\"/tmp/other-shot.jpg\\", \\"recording_path\\": \\"/tmp/other-recording.mp4\\"}"}}]',
            },
        ],
    )

    screenshots = [artifact for artifact in detail.artifacts if artifact.type == "screenshot"]
    recordings = [artifact for artifact in detail.artifacts if artifact.type == "browser_recording"]

    assert {artifact.path for artifact in screenshots} == {"/tmp/replay-shot.png", "/tmp/other-shot.jpg"}
    assert {artifact.path for artifact in recordings} == {"/tmp/replay.webm", "/tmp/other-recording.mp4"}
    assert all(artifact.content.startswith(artifact.type) for artifact in screenshots + recordings)
    assert all("File not found locally" in artifact.summary for artifact in screenshots + recordings)


def test_normalize_session_adds_git_diff_summary_when_project_path_is_known(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()

    def fake_run(cmd, **kwargs):
        assert kwargs["cwd"] == str(repo)
        if cmd[:3] == ["git", "status", "--short"]:
            return CompletedProcess(cmd, 0, stdout=" M frontend/app.tsx\n?? README.md\n", stderr="")
        if cmd[:3] == ["git", "diff", "--shortstat"]:
            return CompletedProcess(cmd, 0, stdout=" 1 file changed, 4 insertions(+)\n", stderr="")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr("backend.services.replay_normalizer.subprocess.run", fake_run)

    tool_calls = json.dumps(
        [
            {
                "function": {
                    "name": "exec_command",
                    "arguments": json.dumps({"cmd": "git diff", "cwd": str(repo)}),
                }
            }
        ]
    )
    detail = normalize_session(
        _session(),
        [
            {
                "id": 1,
                "role": "assistant",
                "content": "Inspecting project path.",
                "timestamp": 101,
                "tool_calls": tool_calls,
            }
        ],
    )

    artifact = next(artifact for artifact in detail.artifacts if artifact.type == "git_diff")
    artifact_types = {artifact.type for artifact in detail.artifacts}

    assert detail.run.counts.files_changed == 2
    assert detail.receipt.files_changed == 2
    assert artifact.title == "Git diff summary"
    assert "1 file changed" in artifact.content
    assert {"modified_file", "generated_file"}.issubset(artifact_types)
