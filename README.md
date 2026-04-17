# hey-call

AI phone agent that makes outbound calls on your behalf. Give it a number and a goal — it calls, conducts the conversation, and reports back with a summary, full transcript, and recording.

## How it works

```
You: "call +13035551234, goal: find out if the owner would consider selling"
hey-call: [initiates call via ElevenLabs + Twilio]
           [waits for call to complete]
           [saves transcript + recording]
           [Mac analyzes transcript in-session]
```

**Stack:** ElevenLabs Conversational AI (STT + LLM + TTS) · Twilio (phone number) · Claude Code (summary, in-session)  
**Cost:** ~$0.47 per 5-minute call (no extra API costs — summary runs in your Claude Code session)

## Setup

### 1. Accounts required

- [ElevenLabs](https://elevenlabs.io) — create a Conversational AI agent, note the agent ID ([API docs](https://elevenlabs.io/docs/api-reference/conversational-ai/twilio-outbound-call))
- [Twilio](https://twilio.com) — buy a US phone number (~$1.15/month), import it into ElevenLabs ([guide](https://elevenlabs.io/docs/eleven-agents/phone-numbers/twilio-integration/native-integration))
- [Claude Code](https://claude.com/claude-code) — summary generation happens in-session (no separate API key needed)

### 2. ElevenLabs agent configuration

In the ElevenLabs dashboard:
- Conversational AI → Create Agent
- Name: `hey-call agent` (or anything)
- Voice: `Aria` (or any natural-sounding voice)
- Paste the contents of `prompts/agent_system.txt` as the system prompt
- First message: `Hi, this is Mac calling on behalf of Zeb Lawrence. Is this a good time to talk?`
- Max duration: 10 minutes

Then: Settings → Phone Numbers → Import from Twilio → select your number.

### 3. Install and configure

```bash
pip install -r requirements.txt

cp .env.example .env
# edit .env with your API keys
```

### 4. Make a call

```bash
python call.py "+13035551234" "find out if the owner is open to selling the business"
```

## Output

Each call saves to `calls/YYYY-MM-DD_HH-MM_<last4>/`:

```
calls/
└── 2026-04-17_14-32_1234/
    ├── transcript.json   # raw ElevenLabs API response
    ├── transcript.txt    # human-readable turn-by-turn
    └── recording.mp3     # full call audio (if available)
```

The transcript is printed to stdout. Mac (Claude Code) reads it and generates a summary in-session, then saves `summary.md` to the call directory.

## Docs

- [`DESIGN.md`](DESIGN.md) — architecture, API details, cost model
- [`docs/spec.md`](docs/spec.md) — full design spec
- [`docs/plan.md`](docs/plan.md) — implementation plan

## Cost model

| Component | Rate | 5-min call |
|-----------|------|-----------|
| ElevenLabs Conversational AI | ~$0.08/min | $0.40 |
| Twilio outbound (US) | ~$0.014/min | $0.07 |
| Summary generation | $0 | $0 (in-session) |
| **Total** | | **~$0.47** |

See [DESIGN.md](DESIGN.md) for detailed cost breakdowns with source links.
