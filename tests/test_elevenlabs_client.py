import pytest
from unittest.mock import patch, MagicMock


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
    agent_override = body["conversation_initiation_client_data"]["conversation_config_override"]["agent"]
    assert agent_override["prompt"]["prompt"] == "Your goal: find out the hours."
    assert agent_override["first_message"] == "Hi, this is Mac."


def test_initiate_call_omits_first_message_when_not_provided():
    """When first_message is omitted, body should not contain that key."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "success": True,
        "conversation_id": "conv_xyz",
        "callSid": "CA123",
        "message": "ok",
    }

    with patch("requests.post", return_value=mock_response) as mock_post:
        from elevenlabs_client import initiate_call
        initiate_call("k", "a", "p", "+13035551234", "Goal: test.")

    _, kwargs = mock_post.call_args
    agent_override = kwargs["json"]["conversation_initiation_client_data"][
        "conversation_config_override"
    ]["agent"]
    assert "first_message" not in agent_override
    assert agent_override["prompt"]["prompt"] == "Goal: test."


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
        with patch("time.sleep"):
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

    start_time = 0.0
    times = [start_time, start_time + 901]

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
