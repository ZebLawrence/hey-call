import json


# ── format_transcript ──────────────────────────────────────────────────────────

def test_format_transcript_empty():
    from report import format_transcript
    assert format_transcript([]) == ""


def test_format_transcript_single_turn():
    from report import format_transcript
    turns = [{"role": "agent", "message": "Hi, this is Mac."}]
    assert format_transcript(turns) == "Agent: Hi, this is Mac."


def test_format_transcript_multi_turn():
    from report import format_transcript
    turns = [
        {"role": "agent", "message": "Hi, this is Mac."},
        {"role": "user", "message": "What do you want?"},
        {"role": "agent", "message": "Just checking your hours."},
    ]
    assert format_transcript(turns) == (
        "Agent: Hi, this is Mac.\n"
        "User: What do you want?\n"
        "Agent: Just checking your hours."
    )


def test_format_transcript_skips_null_messages():
    from report import format_transcript
    turns = [
        {"role": "agent", "message": "Hi."},
        {"role": "user", "message": None},
        {"role": "agent", "message": "Are you there?"},
    ]
    assert format_transcript(turns) == "Agent: Hi.\nAgent: Are you there?"


# ── save_artifacts ─────────────────────────────────────────────────────────────

def test_save_artifacts_creates_directory(tmp_path):
    from report import save_artifacts
    conversation_data = {"transcript": [{"role": "agent", "message": "Hello."}]}
    call_dir, _ = save_artifacts(
        calls_dir=tmp_path,
        to_number="+13035551234",
        goal="find hours",
        conversation_data=conversation_data,
        audio_bytes=None,
    )
    assert call_dir.exists()
    assert call_dir.name.endswith("1234")


def test_save_artifacts_writes_transcript_json(tmp_path):
    from report import save_artifacts
    conversation_data = {
        "status": "done",
        "transcript": [{"role": "agent", "message": "Hello."}],
    }
    call_dir, _ = save_artifacts(tmp_path, "+13035551234", "goal", conversation_data, None)
    saved = json.loads((call_dir / "transcript.json").read_text())
    assert saved["status"] == "done"
    assert saved["transcript"][0]["message"] == "Hello."


def test_save_artifacts_writes_transcript_txt(tmp_path):
    from report import save_artifacts
    conversation_data = {
        "transcript": [
            {"role": "agent", "message": "Hi."},
            {"role": "user", "message": "Hello."},
        ]
    }
    call_dir, transcript_text = save_artifacts(
        tmp_path, "+13035551234", "goal", conversation_data, None
    )
    saved = (call_dir / "transcript.txt").read_text()
    assert saved == "Agent: Hi.\nUser: Hello."
    assert transcript_text == "Agent: Hi.\nUser: Hello."


def test_save_artifacts_writes_recording_when_provided(tmp_path):
    from report import save_artifacts
    conversation_data = {"transcript": []}
    call_dir, _ = save_artifacts(
        tmp_path, "+13035551234", "goal", conversation_data, b"fake_audio"
    )
    assert (call_dir / "recording.mp3").read_bytes() == b"fake_audio"


def test_save_artifacts_skips_recording_when_none(tmp_path):
    from report import save_artifacts
    conversation_data = {"transcript": []}
    call_dir, _ = save_artifacts(
        tmp_path, "+13035551234", "goal", conversation_data, None
    )
    assert not (call_dir / "recording.mp3").exists()
