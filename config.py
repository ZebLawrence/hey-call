import os

REQUIRED_VARS = [
    "ELEVENLABS_API_KEY",
    "ELEVENLABS_AGENT_ID",
    "ELEVENLABS_PHONE_NUMBER_ID",
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
