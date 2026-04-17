# AI Phone Caller Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI tool that lets Mac initiate outbound AI phone calls via ElevenLabs + Twilio, then save the transcript, recording, and a Claude-generated summary to `workspace/calls/`.

**Architecture:** A single CLI script (`call.py`) orchestrates three focused modules: `config.py` loads env vars, `elevenlabs_client.py` wraps the ElevenLabs API (initiate → poll → fetch audio), and `report.py` formats the transcript and generates a summary via Claude. All artifacts land in a timestamped directory under `workspace/calls/`.

**Tech Stack:** Python 3.11+, `requests` (HTTP), `anthropic` SDK (summary generation), `python-dotenv` (env loading), `pytest` + `unittest.mock` (tests)

---

## File Map

| File | Create / Modify | Responsibility |
|------|-----------------|----------------|
| `workspace/phone-agent/requirements.txt` | Modify | Add `pytest` |
| `workspace/phone-agent/.env.example` | Create | Template for required env vars |
| `workspace/phone-agent/.gitignore` | Create | Ignore `.env`, `__pycache__`, `*.pyc` |
| `workspace/phone-agent/conftest.py` | Create | Add phone-agent dir to sys.path for pytest |
| `workspace/phone-agent/tests/` | Create dir | Test files |
| `workspace/phone-agent/config.py` | Create | Load and validate env vars |
| `workspace/phone-agent/elevenlabs_client.py` | Create | Initiate call, poll status, fetch audio |
| `workspace/phone-agent/report.py` | Create | Format transcript, generate summary, save artifacts |
| `workspace/phone-agent/call.py` | Create | CLI entry point — wires everything together |
| `workspace/calls/` | Create dir | Output directory for call artifacts |

---

## Task 1: Bootstrap

**Files:**
- Modify: `workspace/phone-agent/requirements.txt`
- Create: `workspace/phone-agent/.env.example`
- Create: `workspace/phone-agent/.gitignore`
- Create: `workspace/phone-agent/conftest.py`
- Create: `workspace/phone-agent/tests/` (empty dir)
- Create: `workspace/calls/` (empty dir)

- [ ] **Step 1: Add pytest to requirements.txt**

Replace the contents of `workspace/phone-agent/requirements.txt` with:

```
anthropic>=0.40.0
requests>=2.31.0
python-dotenv>=1.0.0
pytest>=8.0.0
```

- [ ] **Step 2: Create .env.example**

Create `workspace/phone-agent/.env.example`:

```bash
# ElevenLabs account API key — https://elevenlabs.io/app/settings/api-keys
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here

# ID of the pre-configured EL agent (Conversational AI → your agent → copy ID)
ELEVENLABS_AGENT_ID=your_agent_id_here

# ID of the Twilio phone number registered in ElevenLabs (Settings → Phone Numbers)
ELEVENLABS_PHONE_NUMBER_ID=your_phone_number_id_here

# Anthropic API key — for generating call summaries
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

- [ ] **Step 3: Create .gitignore**

Create `workspace/phone-agent/.gitignore`:

```
.env
__pycache__/
*.pyc
*.pyo
.pytest_cache/
```

- [ ] **Step 4: Create conftest.py**

Create `workspace/phone-agent/conftest.py`:

```python
import sys
from pathlib import Path

# Make phone-agent modules importable when pytest runs from this directory
sys.path.insert(0, str(Path(__file__).parent))
```

- [ ] **Step 5: Create directories**

```bash
mkdir workspace/phone-agent/tests
mkdir workspace/calls
```

- [ ] **Step 6: Install dependencies**

Run from `workspace/phone-agent/`:

```bash
cd workspace/phone-agent && pip install -r requirements.txt
```

Expected: packages install without errors. `pytest --version` should show 8.x.

---

## Task 2: config.py

**Files:**
- Create: `workspace/phone-agent/tests/test_config.py`
- Create: `workspace/phone-agent/config.py`

- [ ] **Step 1: Write failing tests**

Create `workspace/phone-agent/tests/test_config.py`:

```python
import os
import pytest
from unittest.mock import patch


def test_load_config_raises_when_all_missing():
    """All required env vars missing → ValueError listing them."""
    with patch.dict(os.environ, {}, clear=True):
        from config import load_config
        with pytest.raises(ValueError) as exc:
            load_config()
        msg = str(exc.value)
        assert "ELEVENLABS_API_KEY" in msg
        assert "ELEVENLABS_AGENT_ID" in msg
        assert "ELEVENLABS_PHONE_NUMBER_ID" in msg
        assert "ANTHROPIC_API_KEY" in msg


def test_load_config_raises_when_one_missing():
    """One missing var → ValueError mentioning that var."""
    env = {
        "ELEVENLABS_API_KEY": "el_key",
        "ELEVENLABS_AGENT_ID": "agent_id",
        "ELEVENLABS_PHONE_NUMBER_ID": "phone_id",
        # ANTHROPIC_API_KEY intentionally omitted
    }
    with patch.dict(os.environ, env, clear=True):
        from config import load_config
        with pytest.raises(ValueError) as exc:
            load_config()
        assert "ANTHROPIC_API_KEY" in str(exc.value)


def test_load_config_returns_dict_when_all_present():
    """All vars set → returns dict with all four keys."""
    env = {
        "ELEVENLABS_API_KEY": "el_key",
        "ELEVENLABS_AGENT_ID": "agent_id",
        "ELEVENLABS_PHONE_NUMBER_ID": "phone_id",
        "ANTHROPIC_API_KEY": "ant_key",
    }
    with patch.dict(os.environ, env, clear=True):
        from config import load_config
        config = load_config()
    assert config["ELEVENLABS_API_KEY"] == "el_key"
    assert config["ELEVENLABS_AGENT_ID"] == "agent_id"
    assert config["ELEVENLABS_PHONE_NUMBER_ID"] == "phone_id"
    assert config["ANTHROPIC_API_KEY"] == "ant_key"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd workspace/phone-agent && python -m pytest tests/test_config.py -v
```

Expected: 3 failures — `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 3: Implement config.py**

Create `workspace/phone-agent/config.py`:

```python
import os
from dotenv import load_dotenv

load_dotenv()

REQUIRED_VARS = [
    "ELEVENLABS_API_KEY",
    "ELEVENLABS_AGENT_ID",
    "ELEVENLABS_PHONE_NUMBER_ID",
    "ANTHROPIC_API_KEY",
]


def load_config() -> dict:
    """Load and validate required environment variables.

    Returns a dict of all required vars.
    Raises ValueError listing any missing vars.
    """
    config = {}
    missing = []
    for key in REQUIRED_VARS:
        val = os.environ.get(key)
        if not val:
            missing.append(key)
        else:
            config[key] = val
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    return config
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd workspace/phone-agent && python -m pytest tests/test_config.py -v
```

Expected:
```
tests/test_config.py::test_load_config_raises_when_all_missing PASSED
tests/test_config.py::test_load_config_raises_when_one_missing PASSED
tests/test_config.py::test_load_config_returns_dict_when_all_present PASSED
3 passed
```

---

## Task 3: elevenlabs_client.py

**Files:**
- Create: `workspace/phone-agent/tests/test_elevenlabs_client.py`
- Create: `workspace/phone-agent/elevenlabs_client.py`

- [ ] **Step 1: Write failing tests**

Create `workspace/phone-agent/tests/test_elevenlabs_client.py`:

```python
import pytest
from unittest.mock import patch, MagicMock, call


# ── initiate_call ─────────────────────────────────────────────────────────────

def test_initiate_call_sends_correct_payload():
    """initiate_call POSTs the right body and returns conversation_id."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "success": True,
        "conversation_id": "conv_abc123",
        "callSid": "CA123",
        "message": "ok",
    }

    with patch("requests.post", return_value=mock_response) as mock_post:
        from elevenlabs_client import initiate_call
        conv_id = initiate_call(
            api_key="el_key",
            agent_id="agent_id",
            phone_number_id="phone_id",
            to_number="+13035551234",
            system_prompt="Your goal: find out the hours.",
            first_message="Hi, this is Mac.",
        )

    assert conv_id == "conv_abc123"
    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    body = kwargs["json"]
    assert body["agent_id"] == "agent_id"
    assert body["agent_phone_number_id"] == "phone_id"
    assert body["to_number"] == "+13035551234"
    assert body["call_recording_enabled"] is True
    override = body["conversation_initiation_client_data"]["conversation_config_override"]
    assert override["prompt"]["prompt"] == "Your goal: find out the hours."
    assert override["first_message"] == "Hi, this is Mac."


def test_initiate_call_raises_on_api_failure():
    """initiate_call raises RuntimeError when success is False."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "success": False,
        "message": "Invalid agent_id",
        "conversation_id": None,
        "callSid": None,
    }

    with patch("requests.post", return_value=mock_response):
        from elevenlabs_client import initiate_call
        with pytest.raises(RuntimeError, match="Invalid agent_id"):
            initiate_call("k", "a", "p", "+1", "prompt", "hello")


# ── poll_conversation ──────────────────────────────────────────────────────────

def test_poll_conversation_returns_data_when_done():
    """poll_conversation returns conversation data when status is 'done'."""
    done_response = MagicMock()
    done_response.json.return_value = {
        "status": "done",
        "conversation_id": "conv_abc123",
        "transcript": [{"role": "agent", "message": "Hi!"}],
    }

    with patch("requests.get", return_value=done_response):
        with patch("time.sleep"):  # don't actually sleep in tests
            from elevenlabs_client import poll_conversation
            data = poll_conversation("el_key", "conv_abc123")

    assert data["status"] == "done"
    assert data["conversation_id"] == "conv_abc123"


def test_poll_conversation_polls_until_done():
    """poll_conversation retries while in-progress then returns on done."""
    in_progress = MagicMock()
    in_progress.json.return_value = {"status": "in-progress"}
    done = MagicMock()
    done.json.return_value = {
        "status": "done",
        "transcript": [],
        "conversation_id": "conv_abc123",
    }

    with patch("requests.get", side_effect=[in_progress, in_progress, done]):
        with patch("time.sleep"):
            from elevenlabs_client import poll_conversation
            data = poll_conversation("el_key", "conv_abc123")

    assert data["status"] == "done"


def test_poll_conversation_raises_on_failed_status():
    """poll_conversation raises RuntimeError when status is 'failed'."""
    failed_response = MagicMock()
    failed_response.json.return_value = {"status": "failed"}

    with patch("requests.get", return_value=failed_response):
        with patch("time.sleep"):
            from elevenlabs_client import poll_conversation
            with pytest.raises(RuntimeError, match="failed"):
                poll_conversation("el_key", "conv_abc123")


def test_poll_conversation_raises_on_timeout():
    """poll_conversation raises TimeoutError after POLL_TIMEOUT seconds."""
    in_progress = MagicMock()
    in_progress.json.return_value = {"status": "in-progress"}

    # Simulate time advancing past the timeout
    import time as time_module
    start_time = 0.0
    times = [start_time, start_time + 601]  # first call returns start, second exceeds timeout

    with patch("requests.get", return_value=in_progress):
        with patch("time.sleep"):
            with patch("time.time", side_effect=times):
                from elevenlabs_client import poll_conversation
                with pytest.raises(TimeoutError):
                    poll_conversation("el_key", "conv_abc123")


# ── fetch_audio ────────────────────────────────────────────────────────────────

def test_fetch_audio_returns_bytes_on_success():
    """fetch_audio returns audio bytes when recording is available."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"fake_mp3_bytes"

    with patch("requests.get", return_value=mock_response):
        from elevenlabs_client import fetch_audio
        result = fetch_audio("el_key", "conv_abc123")

    assert result == b"fake_mp3_bytes"


def test_fetch_audio_returns_none_on_404():
    """fetch_audio returns None when recording is not available (404)."""
    mock_response = MagicMock()
    mock_response.status_code = 404

    with patch("requests.get", return_value=mock_response):
        from elevenlabs_client import fetch_audio
        result = fetch_audio("el_key", "conv_abc123")

    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd workspace/phone-agent && python -m pytest tests/test_elevenlabs_client.py -v
```

Expected: 8 failures — `ModuleNotFoundError: No module named 'elevenlabs_client'`

- [ ] **Step 3: Implement elevenlabs_client.py**

Create `workspace/phone-agent/elevenlabs_client.py`:

```python
import time
import requests

BASE_URL = "https://api.elevenlabs.io/v1"
POLL_INTERVAL = 5   # seconds between status checks
POLL_TIMEOUT = 600  # 10 minutes max


def initiate_call(
    api_key: str,
    agent_id: str,
    phone_number_id: str,
    to_number: str,
    system_prompt: str,
    first_message: str,
) -> str:
    """Initiate an outbound call via ElevenLabs.

    Returns the conversation_id for polling.
    Raises RuntimeError if the API reports failure.
    """
    url = f"{BASE_URL}/convai/twilio/outbound-call"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }
    body = {
        "agent_id": agent_id,
        "agent_phone_number_id": phone_number_id,
        "to_number": to_number,
        "call_recording_enabled": True,
        "conversation_initiation_client_data": {
            "conversation_config_override": {
                "prompt": {"prompt": system_prompt},
                "first_message": first_message,
            }
        },
    }
    resp = requests.post(url, headers=headers, json=body, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"ElevenLabs call initiation failed: {data.get('message')}")
    return data["conversation_id"]


def poll_conversation(api_key: str, conversation_id: str) -> dict:
    """Poll GET /v1/convai/conversations/{id} until status is 'done'.

    Returns the full conversation response dict.
    Raises TimeoutError after POLL_TIMEOUT seconds.
    Raises RuntimeError if status is 'failed'.
    """
    url = f"{BASE_URL}/convai/conversations/{conversation_id}"
    headers = {"xi-api-key": api_key}
    start = time.time()

    while True:
        if time.time() - start > POLL_TIMEOUT:
            raise TimeoutError(
                f"Call timed out after {POLL_TIMEOUT}s (conversation_id: {conversation_id})"
            )

        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")

        if status == "done":
            return data
        if status == "failed":
            raise RuntimeError(f"Call failed (conversation_id: {conversation_id})")

        time.sleep(POLL_INTERVAL)


def fetch_audio(api_key: str, conversation_id: str) -> bytes | None:
    """Download the call recording.

    Returns audio bytes if available, None if the recording is not present (404).
    Raises for other HTTP errors.
    """
    url = f"{BASE_URL}/convai/conversations/{conversation_id}/audio"
    headers = {"xi-api-key": api_key}
    resp = requests.get(url, headers=headers, timeout=60)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.content
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd workspace/phone-agent && python -m pytest tests/test_elevenlabs_client.py -v
```

Expected:
```
tests/test_elevenlabs_client.py::test_initiate_call_sends_correct_payload PASSED
tests/test_elevenlabs_client.py::test_initiate_call_raises_on_api_failure PASSED
tests/test_elevenlabs_client.py::test_poll_conversation_returns_data_when_done PASSED
tests/test_elevenlabs_client.py::test_poll_conversation_polls_until_done PASSED
tests/test_elevenlabs_client.py::test_poll_conversation_raises_on_failed_status PASSED
tests/test_elevenlabs_client.py::test_poll_conversation_raises_on_timeout PASSED
tests/test_elevenlabs_client.py::test_fetch_audio_returns_bytes_on_success PASSED
tests/test_elevenlabs_client.py::test_fetch_audio_returns_none_on_404 PASSED
8 passed
```

---

## Task 4: report.py — transcript formatting and artifact saving

**Files:**
- Create: `workspace/phone-agent/tests/test_report.py` (partial — formatting + artifacts)
- Create: `workspace/phone-agent/report.py` (partial — format_transcript + save_artifacts)

- [ ] **Step 1: Write failing tests for format_transcript and save_artifacts**

Create `workspace/phone-agent/tests/test_report.py`:

```python
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ── format_transcript ──────────────────────────────────────────────────────────

def test_format_transcript_empty():
    """Empty transcript array → empty string."""
    from report import format_transcript
    assert format_transcript([]) == ""


def test_format_transcript_single_turn():
    """Single turn formats as 'Role: message'."""
    from report import format_transcript
    turns = [{"role": "agent", "message": "Hi, this is Mac."}]
    result = format_transcript(turns)
    assert result == "Agent: Hi, this is Mac."


def test_format_transcript_multi_turn():
    """Multiple turns joined with newlines, roles capitalized."""
    from report import format_transcript
    turns = [
        {"role": "agent", "message": "Hi, this is Mac."},
        {"role": "user", "message": "What do you want?"},
        {"role": "agent", "message": "Just checking your hours."},
    ]
    result = format_transcript(turns)
    assert result == (
        "Agent: Hi, this is Mac.\n"
        "User: What do you want?\n"
        "Agent: Just checking your hours."
    )


# ── save_artifacts ─────────────────────────────────────────────────────────────

def test_save_artifacts_creates_directory(tmp_path):
    """save_artifacts creates a timestamped directory under calls_dir."""
    from report import save_artifacts
    conversation_data = {
        "transcript": [{"role": "agent", "message": "Hello."}],
    }
    call_dir, _ = save_artifacts(
        calls_dir=tmp_path,
        to_number="+13035551234",
        goal="find hours",
        conversation_data=conversation_data,
        audio_bytes=None,
    )
    assert call_dir.exists()
    # Directory name ends with last 4 digits of number
    assert call_dir.name.endswith("1234")


def test_save_artifacts_writes_transcript_json(tmp_path):
    """save_artifacts writes transcript.json with full conversation data."""
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
    """save_artifacts writes human-readable transcript.txt."""
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
    """save_artifacts writes recording.mp3 when audio_bytes is not None."""
    from report import save_artifacts
    conversation_data = {"transcript": []}
    call_dir, _ = save_artifacts(
        tmp_path, "+13035551234", "goal", conversation_data, b"fake_audio"
    )
    assert (call_dir / "recording.mp3").read_bytes() == b"fake_audio"


def test_save_artifacts_skips_recording_when_none(tmp_path):
    """save_artifacts does not create recording.mp3 when audio_bytes is None."""
    from report import save_artifacts
    conversation_data = {"transcript": []}
    call_dir, _ = save_artifacts(
        tmp_path, "+13035551234", "goal", conversation_data, None
    )
    assert not (call_dir / "recording.mp3").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd workspace/phone-agent && python -m pytest tests/test_report.py -v
```

Expected: 8 failures — `ModuleNotFoundError: No module named 'report'`

- [ ] **Step 3: Implement format_transcript and save_artifacts in report.py**

Create `workspace/phone-agent/report.py`:

```python
import json
from datetime import datetime
from pathlib import Path


def format_transcript(transcript_array: list) -> str:
    """Convert ElevenLabs transcript array to human-readable turn-by-turn text.

    Each turn becomes 'Role: message' on its own line.
    Returns empty string for empty input.
    """
    lines = []
    for turn in transcript_array:
        role = turn.get("role", "unknown").capitalize()
        message = turn.get("message", "")
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

    # Raw JSON
    (call_dir / "transcript.json").write_text(
        json.dumps(conversation_data, indent=2), encoding="utf-8"
    )

    # Human-readable transcript
    transcript_array = conversation_data.get("transcript", [])
    transcript_text = format_transcript(transcript_array)
    (call_dir / "transcript.txt").write_text(transcript_text, encoding="utf-8")

    # Audio (optional)
    if audio_bytes is not None:
        (call_dir / "recording.mp3").write_bytes(audio_bytes)

    return call_dir, transcript_text


def generate_summary(
    anthropic_api_key: str,
    goal: str,
    to_number: str,
    transcript_text: str,
) -> str:
    """Send transcript to Claude and return a structured summary markdown string."""
    raise NotImplementedError("Implemented in Task 5")


def write_summary(call_dir, summary_text: str) -> None:
    """Write summary markdown to summary.md in call_dir."""
    raise NotImplementedError("Implemented in Task 5")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd workspace/phone-agent && python -m pytest tests/test_report.py -v
```

Expected:
```
tests/test_report.py::test_format_transcript_empty PASSED
tests/test_report.py::test_format_transcript_single_turn PASSED
tests/test_report.py::test_format_transcript_multi_turn PASSED
tests/test_report.py::test_save_artifacts_creates_directory PASSED
tests/test_report.py::test_save_artifacts_writes_transcript_json PASSED
tests/test_report.py::test_save_artifacts_writes_transcript_txt PASSED
tests/test_report.py::test_save_artifacts_writes_recording_when_provided PASSED
tests/test_report.py::test_save_artifacts_skips_recording_when_none PASSED
8 passed
```

---

## Task 5: report.py — summary generation

**Files:**
- Modify: `workspace/phone-agent/tests/test_report.py` (add tests at end of file)
- Modify: `workspace/phone-agent/report.py` (replace NotImplementedError stubs)

- [ ] **Step 1: Add failing tests for generate_summary and write_summary**

Append to the bottom of `workspace/phone-agent/tests/test_report.py`:

```python
# ── generate_summary ───────────────────────────────────────────────────────────

def test_generate_summary_calls_claude_with_correct_structure():
    """generate_summary sends goal, number, and transcript to Claude."""
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="## Call Outcome\nachieved")]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message

    with patch("anthropic.Anthropic", return_value=mock_client):
        from report import generate_summary
        result = generate_summary(
            anthropic_api_key="ant_key",
            goal="find out the hours",
            to_number="+13035551234",
            transcript_text="Agent: Hi.\nUser: We open at 9.",
        )

    assert result == "## Call Outcome\nachieved"
    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["model"] == "claude-sonnet-4-6"
    # Goal and transcript appear in the user message content
    user_content = call_kwargs["messages"][0]["content"]
    assert "find out the hours" in user_content
    assert "Agent: Hi." in user_content


def test_generate_summary_uses_sonnet_model():
    """generate_summary always uses claude-sonnet-4-6."""
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="summary")]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message

    with patch("anthropic.Anthropic", return_value=mock_client):
        from report import generate_summary
        generate_summary("key", "goal", "+1", "Agent: Hi.")

    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["model"] == "claude-sonnet-4-6"


# ── write_summary ──────────────────────────────────────────────────────────────

def test_write_summary_creates_file(tmp_path):
    """write_summary writes the summary text to summary.md."""
    from report import write_summary
    write_summary(tmp_path, "## Call Outcome\nachieved")
    assert (tmp_path / "summary.md").read_text() == "## Call Outcome\nachieved"
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
cd workspace/phone-agent && python -m pytest tests/test_report.py::test_generate_summary_calls_claude_with_correct_structure tests/test_report.py::test_generate_summary_uses_sonnet_model tests/test_report.py::test_write_summary_creates_file -v
```

Expected: 3 failures — `NotImplementedError`

- [ ] **Step 3: Replace NotImplementedError stubs in report.py**

In `workspace/phone-agent/report.py`, add `import anthropic` at the top, then replace the two stub functions:

```python
import anthropic
```

Replace `generate_summary`:

```python
def generate_summary(
    anthropic_api_key: str,
    goal: str,
    to_number: str,
    transcript_text: str,
) -> str:
    """Send transcript to Claude and return a structured summary markdown string."""
    client = anthropic.Anthropic(api_key=anthropic_api_key)

    system = (
        "You are Mac, an AI assistant. You just completed a phone call on behalf of "
        "Zeb Lawrence. Analyze the call transcript and produce a structured report."
    )
    user = (
        f"Call goal: {goal}\n"
        f"Target number: {to_number}\n\n"
        f"Transcript:\n{transcript_text}\n\n"
        "Produce a structured report using exactly these sections:\n\n"
        "## Call Outcome\n"
        "[achieved / partially achieved / not achieved / no answer / voicemail]\n\n"
        "## Key Facts Learned\n"
        "[bullet list, or 'None']\n\n"
        "## Follow-Up Actions\n"
        "[bullet list, or 'None']\n\n"
        "## Notable Moments\n"
        "[anything surprising, useful, or worth flagging — or 'None']\n\n"
        "## Raw Transcript Summary\n"
        "[2-3 sentence narrative of how the call went]"
    )

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text
```

Replace `write_summary`:

```python
def write_summary(call_dir, summary_text: str) -> None:
    """Write summary markdown to summary.md in call_dir."""
    Path(call_dir) / "summary.md"
    (Path(call_dir) / "summary.md").write_text(summary_text, encoding="utf-8")
```

- [ ] **Step 4: Run all report tests**

```bash
cd workspace/phone-agent && python -m pytest tests/test_report.py -v
```

Expected: 11 passed

---

## Task 6: call.py — wire everything together

**Files:**
- Create: `workspace/phone-agent/call.py`

No automated tests for this task — it's the CLI entry point and is covered by Tasks 2–5. Verify manually.

- [ ] **Step 1: Create call.py**

Create `workspace/phone-agent/call.py`:

```python
#!/usr/bin/env python3
"""
AI Phone Caller — CLI entry point.

Usage:
    python call.py <phone_number> "<goal>"

Example:
    python call.py "+13035551234" "find out if the business is open on weekends"
"""
import sys
from pathlib import Path

# Ensure imports work when run directly
sys.path.insert(0, str(Path(__file__).parent))

from config import load_config
from elevenlabs_client import initiate_call, poll_conversation, fetch_audio
from report import save_artifacts, generate_summary, write_summary

CALLS_DIR = Path(__file__).parent.parent / "calls"
PROMPTS_DIR = Path(__file__).parent / "prompts"


def build_system_prompt(goal: str) -> str:
    """Read the base system prompt template and substitute the goal."""
    template = (PROMPTS_DIR / "agent_system.txt").read_text(encoding="utf-8")
    return template.replace("{{GOAL}}", goal)


def main():
    if len(sys.argv) < 3:
        print("Usage: python call.py <phone_number> \"<goal>\"")
        print('Example: python call.py "+13035551234" "find out if the owner is open to selling"')
        sys.exit(1)

    to_number = sys.argv[1]
    goal = sys.argv[2]

    print(f"\nInitiating call to {to_number}")
    print(f"Goal: {goal}\n")

    try:
        config = load_config()
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("Copy .env.example to .env and fill in your API keys.")
        sys.exit(1)

    system_prompt = build_system_prompt(goal)
    first_message = "Hi, this is Mac calling on behalf of Zeb Lawrence. Is this a good time to talk?"

    try:
        conversation_id = initiate_call(
            api_key=config["ELEVENLABS_API_KEY"],
            agent_id=config["ELEVENLABS_AGENT_ID"],
            phone_number_id=config["ELEVENLABS_PHONE_NUMBER_ID"],
            to_number=to_number,
            system_prompt=system_prompt,
            first_message=first_message,
        )
        print(f"Call started (conversation_id: {conversation_id})")
        print("Waiting for call to complete...\n")

        conversation_data = poll_conversation(config["ELEVENLABS_API_KEY"], conversation_id)
        print("Call completed. Fetching recording...")

        audio_bytes = fetch_audio(config["ELEVENLABS_API_KEY"], conversation_id)

        call_dir, transcript_text = save_artifacts(
            calls_dir=CALLS_DIR,
            to_number=to_number,
            goal=goal,
            conversation_data=conversation_data,
            audio_bytes=audio_bytes,
        )

        print(f"Artifacts saved to {call_dir}")
        print("Generating summary...\n")

        summary = generate_summary(
            anthropic_api_key=config["ANTHROPIC_API_KEY"],
            goal=goal,
            to_number=to_number,
            transcript_text=transcript_text,
        )

        write_summary(call_dir, summary)

        print("=" * 60)
        print("CALL SUMMARY")
        print("=" * 60)
        print(summary)
        print("=" * 60)
        print(f"\nArtifacts:")
        print(f"  Transcript: {call_dir}/transcript.txt")
        print(f"  Full JSON:  {call_dir}/transcript.json")
        if audio_bytes:
            print(f"  Recording:  {call_dir}/recording.mp3")
        print(f"  Summary:    {call_dir}/summary.md")

    except TimeoutError as e:
        print(f"\nTimeout: {e}")
        sys.exit(1)
    except RuntimeError as e:
        print(f"\nCall error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the full test suite to confirm nothing broke**

```bash
cd workspace/phone-agent && python -m pytest tests/ -v
```

Expected: 19 passed, 0 failed

- [ ] **Step 3: Verify the help message works**

```bash
cd workspace/phone-agent && python call.py
```

Expected output:
```
Usage: python call.py <phone_number> "<goal>"
Example: python call.py "+13035551234" "find out if the owner is open to selling"
```

- [ ] **Step 4: Verify config error message works**

```bash
cd workspace/phone-agent && python call.py "+13035551234" "test goal"
```

Expected output (with no .env set):
```
Configuration error: Missing required environment variables: ELEVENLABS_API_KEY, ...
Copy .env.example to .env and fill in your API keys.
```

---

## Task 7: Account Setup and Live Test

This task is manual — no code to write. Follow the setup checklist from DESIGN.md, then make a real test call.

- [ ] **Step 1: Create ElevenLabs account**

Go to elevenlabs.io → sign up → navigate to Settings → API Keys → copy your key.

- [ ] **Step 2: Create a Conversational AI agent**

ElevenLabs dashboard → Conversational AI → Create Agent:
- Name: `Mac Phone Agent`
- Voice: `Aria` (or any natural-sounding voice)
- System prompt: paste contents of `workspace/phone-agent/prompts/agent_system.txt` (the `{{GOAL}}` placeholder will be overridden per-call)
- First message: `Hi, this is Mac calling on behalf of Zeb Lawrence. Is this a good time to talk?`
- Max duration: `10 minutes`

Note the agent ID from the URL or settings panel.

- [ ] **Step 3: Get a Twilio phone number**

Go to twilio.com → Console → Phone Numbers → Buy a Number:
- Choose a US number with a local area code
- Enable "Voice" capability
- Cost: ~$1.15/month

- [ ] **Step 4: Import Twilio number into ElevenLabs**

ElevenLabs dashboard → Conversational AI → Phone Numbers → Add Phone Number → Import from Twilio:
- Enter your Twilio Account SID and Auth Token
- Select the number you just bought
- Note the ElevenLabs phone number ID shown after import

- [ ] **Step 5: Create .env file**

```bash
cp workspace/phone-agent/.env.example workspace/phone-agent/.env
```

Edit `workspace/phone-agent/.env` and fill in:
```
ELEVENLABS_API_KEY=<your key>
ELEVENLABS_AGENT_ID=<your agent id>
ELEVENLABS_PHONE_NUMBER_ID=<your EL phone number id>
ANTHROPIC_API_KEY=<your anthropic key>
```

- [ ] **Step 6: Make a test call to your own phone**

```bash
cd workspace/phone-agent && python call.py "+1YOURNUMBER" "ask what time it is and then say goodbye"
```

Expected flow:
1. Your phone rings from an unknown number
2. The agent greets you and asks what time it is
3. You respond, agent thanks you and ends the call
4. Script prints the summary
5. Check `workspace/calls/` — a new directory should exist with `transcript.json`, `transcript.txt`, `recording.mp3`, `summary.md`

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by |
|-----------------|-----------|
| Triggered from Claude Code session via `python call.py` | Task 6 |
| ElevenLabs Conversational AI + Twilio | Tasks 3, 7 |
| Per-call system prompt override via `conversation_initiation_client_data` | Task 3 (initiate_call) |
| Poll until done with 10-min timeout | Task 3 (poll_conversation) |
| `transcript.json` saved | Task 4 (save_artifacts) |
| `transcript.txt` saved | Task 4 (save_artifacts + format_transcript) |
| `recording.mp3` saved | Task 4 (save_artifacts) |
| `summary.md` generated via Claude Sonnet | Task 5 |
| Summary printed to stdout | Task 6 (call.py) |
| Missing env var → clear error | Task 2 (config.py) |
| No answer / voicemail → handled | EL agent handles; poll returns `done` with empty transcript; Task 5 summary flags it |
| Call failed status → RuntimeError | Task 3 (poll_conversation) |
| Timeout → TimeoutError | Task 3 (poll_conversation) |
| `call_recording_enabled: true` | Task 3 (initiate_call body) |
| `.env.example` template | Task 1 |
| `workspace/calls/` directory | Task 1 |
| `prompts/agent_system.txt` template | Already exists (created during design) |

All spec requirements covered. No gaps found.

**Placeholder scan:** No TBD, TODO, or incomplete sections. All code blocks are complete. All function signatures are consistent across tasks (`format_transcript`, `save_artifacts`, `generate_summary`, `write_summary` defined in Task 4/5, used in Task 6).

**Type consistency check:**
- `save_artifacts` returns `(Path, str)` in Task 4 — destructured as `call_dir, transcript_text` in Task 6. ✓
- `generate_summary` takes `(str, str, str, str)` — called with same signature in Task 6. ✓
- `initiate_call` returns `str` (conversation_id) — assigned in Task 6. ✓
- `poll_conversation` returns `dict` — passed to `save_artifacts` as `conversation_data`. ✓
- `fetch_audio` returns `bytes | None` — passed to `save_artifacts` as `audio_bytes`. ✓
