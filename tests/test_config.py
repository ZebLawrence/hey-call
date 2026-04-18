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


def test_load_config_raises_when_one_missing():
    """One missing var → ValueError mentioning that var."""
    env = {
        "ELEVENLABS_API_KEY": "el_key",
        "ELEVENLABS_AGENT_ID": "agent_id",
    }
    with patch.dict(os.environ, env, clear=True):
        from config import load_config
        with pytest.raises(ValueError) as exc:
            load_config()
        assert "ELEVENLABS_PHONE_NUMBER_ID" in str(exc.value)


def test_load_config_returns_dict_when_all_present():
    """All vars set → returns dict with all three keys."""
    env = {
        "ELEVENLABS_API_KEY": "el_key",
        "ELEVENLABS_AGENT_ID": "agent_id",
        "ELEVENLABS_PHONE_NUMBER_ID": "phone_id",
    }
    with patch.dict(os.environ, env, clear=True):
        from config import load_config
        config = load_config()
    assert config["ELEVENLABS_API_KEY"] == "el_key"
    assert config["ELEVENLABS_AGENT_ID"] == "agent_id"
    assert config["ELEVENLABS_PHONE_NUMBER_ID"] == "phone_id"
