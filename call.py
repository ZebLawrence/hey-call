#!/usr/bin/env python3
"""
hey-call — AI Phone Caller CLI.

Usage:
    python call.py <phone_number> "<goal>" ["<context>"]

Examples:
    python call.py "+13035551234" "find out if the business is open on weekends"
    python call.py "+13035551234" "ask if the laundromat is for sale" "Zeb toured it last week — owner is Maria, she mentioned retiring soon."
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from config import load_config
from elevenlabs_client import initiate_call, poll_conversation, fetch_audio
from report import save_artifacts

PROJECT_ROOT = Path(__file__).parent
CALLS_DIR = PROJECT_ROOT / "calls"
PROMPTS_DIR = PROJECT_ROOT / "prompts"

E164_PATTERN = re.compile(r"^\+\d{10,15}$")


def validate_phone_number(number: str) -> None:
    """Validate phone number is E.164 format. Raises ValueError if not."""
    if not E164_PATTERN.match(number):
        raise ValueError(
            f"Invalid phone number: {number}\n"
            f"Expected E.164 format: +<country code><number> (e.g. +13035551234)"
        )


def build_system_prompt(goal: str, context: str = "") -> str:
    """Read the base system prompt template and substitute goal + context.

    Empty/whitespace context is replaced with a neutral marker so the
    placeholder never leaks into the agent's prompt.
    """
    template = (PROMPTS_DIR / "agent_system.txt").read_text(encoding="utf-8")
    context_block = context.strip() if context and context.strip() else "(none provided)"
    return template.replace("{{GOAL}}", goal).replace("{{CONTEXT}}", context_block)


def main():
    if len(sys.argv) < 3:
        print('Usage: python call.py <phone_number> "<goal>" ["<context>"]')
        print('Example: python call.py "+13035551234" "find out if the owner is open to selling"')
        sys.exit(1)

    to_number = sys.argv[1]
    goal = sys.argv[2]
    context = sys.argv[3] if len(sys.argv) > 3 else ""

    try:
        validate_phone_number(to_number)
    except ValueError as e:
        print(f"Validation error: {e}")
        sys.exit(1)

    print(f"\nInitiating call to {to_number}")
    print(f"Goal: {goal}\n")

    try:
        config = load_config()
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("Copy .env.example to .env and fill in your API keys.")
        sys.exit(1)

    system_prompt = build_system_prompt(goal, context)

    try:
        conversation_id = initiate_call(
            api_key=config["ELEVENLABS_API_KEY"],
            agent_id=config["ELEVENLABS_AGENT_ID"],
            phone_number_id=config["ELEVENLABS_PHONE_NUMBER_ID"],
            to_number=to_number,
            system_prompt=system_prompt,
        )
        print(f"Call started (conversation_id: {conversation_id})")
        print("Waiting for call to complete...\n")

        conversation_data = poll_conversation(config["ELEVENLABS_API_KEY"], conversation_id)
        print("Call completed. Fetching recording...")

        has_audio = conversation_data.get("has_audio", False)
        audio_bytes = fetch_audio(config["ELEVENLABS_API_KEY"], conversation_id, has_audio=has_audio)

        call_dir, transcript_text = save_artifacts(
            calls_dir=CALLS_DIR,
            to_number=to_number,
            goal=goal,
            conversation_data=conversation_data,
            audio_bytes=audio_bytes,
        )

        print("=" * 60)
        print(f"CALL COMPLETE — {to_number}")
        print(f"Goal: {goal}")
        print("=" * 60)
        print()
        if transcript_text:
            print("TRANSCRIPT:")
            print("-" * 40)
            print(transcript_text)
            print("-" * 40)
        else:
            print("(No transcript — call may not have connected)")
        print()
        print(f"Artifacts saved to {call_dir}/")
        print(f"  transcript.txt  — formatted turn-by-turn")
        print(f"  transcript.json — raw ElevenLabs response")
        if audio_bytes:
            print(f"  recording.mp3   — full call audio")

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
