import time
import requests

BASE_URL = "https://api.elevenlabs.io/v1"
POLL_INTERVAL_INITIAL = 5
POLL_INTERVAL_BACKOFF = 10
POLL_BACKOFF_AFTER = 120
POLL_TIMEOUT = 900


def initiate_call(
    api_key: str,
    agent_id: str,
    phone_number_id: str,
    to_number: str,
    system_prompt: str,
    first_message: str | None = None,
) -> str:
    """Initiate an outbound call via ElevenLabs.

    Returns the conversation_id for polling.
    Raises RuntimeError if the API reports failure.

    `first_message` is optional — if omitted, the agent's pre-configured
    greeting is used. Per-field overrides must be allowed in the EL agent's
    Security → Overrides settings.
    """
    url = f"{BASE_URL}/convai/twilio/outbound-call"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }
    agent_override = {"prompt": {"prompt": system_prompt}}
    if first_message is not None:
        agent_override["first_message"] = first_message
    body = {
        "agent_id": agent_id,
        "agent_phone_number_id": phone_number_id,
        "to_number": to_number,
        "call_recording_enabled": True,
        "conversation_initiation_client_data": {
            "conversation_config_override": {
                "agent": agent_override,
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
        elapsed = time.time() - start
        if elapsed > POLL_TIMEOUT:
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

        interval = POLL_INTERVAL_BACKOFF if elapsed > POLL_BACKOFF_AFTER else POLL_INTERVAL_INITIAL
        time.sleep(interval)


def fetch_audio(api_key: str, conversation_id: str, has_audio: bool = True) -> bytes | None:
    """Download the call recording.

    Returns audio bytes if available, None if the recording is not present.
    """
    if not has_audio:
        return None
    url = f"{BASE_URL}/convai/conversations/{conversation_id}/audio"
    headers = {"xi-api-key": api_key}
    resp = requests.get(url, headers=headers, timeout=60)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.content
