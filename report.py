import json
from datetime import datetime
from pathlib import Path


def format_transcript(transcript_array: list) -> str:
    """Convert ElevenLabs transcript array to human-readable turn-by-turn text.

    Each turn becomes 'Role: message' on its own line. Null messages are skipped.
    """
    lines = []
    for turn in transcript_array:
        message = turn.get("message")
        if message is None:
            continue
        role = turn.get("role", "unknown").capitalize()
        lines.append(f"{role}: {message}")
    return "\n".join(lines)


def save_artifacts(
    calls_dir,
    to_number: str,
    goal: str,
    conversation_data: dict,
    audio_bytes: bytes | None,
) -> tuple:
    """Create call directory and save transcript.json, transcript.txt, and recording.mp3.

    Returns (call_dir: Path, transcript_text: str).
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    digits_only = "".join(c for c in to_number if c.isdigit())
    last4 = digits_only[-4:] if len(digits_only) >= 4 else digits_only
    call_dir = Path(calls_dir) / f"{timestamp}_{last4}"
    call_dir.mkdir(parents=True, exist_ok=True)

    (call_dir / "transcript.json").write_text(
        json.dumps(conversation_data, indent=2), encoding="utf-8"
    )

    transcript_array = conversation_data.get("transcript", [])
    transcript_text = format_transcript(transcript_array)
    (call_dir / "transcript.txt").write_text(transcript_text, encoding="utf-8")

    if audio_bytes is not None:
        (call_dir / "recording.mp3").write_bytes(audio_bytes)

    return call_dir, transcript_text
