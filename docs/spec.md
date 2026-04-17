# AI Phone Caller — Design Spec

> **Note:** This is a snapshot. The authoritative design spec is [`../DESIGN.md`](../DESIGN.md).

**Date:** 2026-04-16  
**Status:** Draft — pending implementation  
**Strategy:** ElevenLabs Conversational AI + Twilio  

---

## Overview

This system lets Mac (Claude Code) make outbound phone calls on Zeb's behalf. Zeb gives a number and a goal in-session; Mac kicks off a call, waits for it to complete, then reports back a summary while saving the full transcript and recording to `workspace/calls/`.

### Trigger Pattern

```
Zeb: "call +13035551234, goal: find out if the owner would consider selling"
Mac: [runs call.py] → call happens → reports summary back
```

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Claude Code Session                 │
│                                                      │
│  Zeb gives: target number + goal                    │
│  Mac runs: python call.py <number> "<goal>"         │
└────────────────────────┬─────────────────────────────┘
                         │ subprocess / Bash tool
                         ▼
┌─────────────────────────────────────────────────────┐
│                     call.py                          │
│  1. Build agent system prompt from goal template    │
│  2. Call ElevenLabs API → initiate outbound call    │
│  3. Poll for completion                             │
│  4. Fetch transcript + recording                    │
│  5. Generate summary via Claude API                 │
│  6. Save artifacts + print summary to stdout        │
└──────────┬──────────────────────┬────────────────────┘
           │                      │
           ▼                      ▼
┌──────────────────┐   ┌────────────────────────────────┐
│ ElevenLabs       │   │  workspace/calls/               │
│ Conversational AI│   │  YYYY-MM-DD_HH-MM_<last4>/     │
│                  │   │  ├── transcript.json            │
│  STT (Deepgram)  │   │  ├── transcript.txt            │
│  LLM (EL model)  │   │  ├── recording.mp3             │
│  TTS (EL voice)  │   │  └── summary.md                │
└──────────┬───────┘   └────────────────────────────────┘
           │
           ▼
┌──────────────────┐
│ Twilio           │
│ Phone Number     │──────► Target's phone
│ (registered in   │
│  ElevenLabs)     │
└──────────────────┘
```

---

## Components

### `workspace/phone-agent/`

| File | Purpose |
|------|---------|
| `call.py` | Main CLI entry point |
| `elevenlabs_client.py` | ElevenLabs API wrapper (initiate, poll, fetch) |
| `report.py` | Transcript → summary via Claude API |
| `config.py` | Env var loading + validation |
| `prompts/agent_system.txt` | Base system prompt template for the caller agent |
| `requirements.txt` | Python dependencies |

### `workspace/calls/`

Each call gets its own timestamped directory:

```
workspace/calls/
└── 2026-04-16_14-32_1234/
    ├── transcript.json      # raw ElevenLabs response
    ├── transcript.txt       # human-readable, turn-by-turn
    ├── recording.mp3        # full audio (if available)
    └── summary.md           # Mac's analysis of the call
```

---

## Call Flow (Step by Step)

```
1. Mac receives goal + number from Zeb
   │
2. call.py builds a system prompt:
   │   "You are Mac, a professional assistant calling on behalf of Zeb Lawrence.
   │    Your goal for this call: <GOAL>
   │    Be concise, professional, and friendly. End the call once the goal
   │    is achieved or it becomes clear you cannot achieve it."
   │
3. POST /v1/convai/twilio/outbound-call
   │   → agent_id: <pre-configured EL agent>
   │   → agent_phone_number_id: Twilio DID registered in EL
   │   → to_number: target
   │   → call_recording_enabled: true
   │   → conversation_initiation_client_data:
   │       conversation_config_override:
   │         agent:
   │           prompt: { prompt: <system prompt with goal> }
   │           first_message: "Hi, this is Mac calling on behalf of Zeb..."
   │   ← { success, conversation_id, callSid }
   │
4. Poll GET /v1/convai/conversations/{id} every 5s
   │   → status: "initiated" | "in-progress" | "processing" | "done" | "failed"
   │   → timeout: 10 minutes
   │
5. On "done":
   │   transcript is in the GET response body (.transcript array)
   │   GET /v1/convai/conversations/{id}/audio    → recording.mp3
   │
6. report.py sends transcript to Claude API
   │   → Returns structured summary markdown
   │
7. Print summary to stdout (Mac reads this)
   Save all artifacts to workspace/calls/<dir>/
```

---

## ElevenLabs Agent Configuration

One persistent agent is pre-configured in the ElevenLabs dashboard. Per-call customization happens via `conversation_initiation_client_data.conversation_config_override.agent` in the API call (so we don't create a new agent per call).

**Agent settings:**

| Setting | Value |
|---------|-------|
| Name | Mac Phone Agent |
| Voice | Aria (natural, professional) or Rachel |
| First message | "Hi, this is Mac calling on behalf of Zeb Lawrence. Is this a good time?" |
| System prompt | Loaded from `prompts/agent_system.txt`, overridden per-call with the goal |
| Max duration | 10 minutes |
| End call on silence | 30 seconds |
| Language | English |

**Phone number:** One Twilio DID number (+1 area code of choice) imported into ElevenLabs as a phone number resource. Cost: ~$1.15/month.

---

## Summary Generation

`report.py` sends the completed transcript to Claude (claude-sonnet-4-6) with this prompt:

```
You are Mac, analyzing a phone call you just completed on Zeb's behalf.
Call goal: <GOAL>
Target: <NUMBER>

Analyze the transcript and produce a structured report:

## Call Outcome
[achieved / partially achieved / not achieved / no answer / voicemail]

## Key Facts Learned
[bullet list]

## Follow-Up Actions
[bullet list, or "None"]

## Notable Moments
[anything surprising, useful, or worth flagging]

## Raw Transcript Summary
[2-3 sentence narrative of how the call went]
```

The summary is printed to stdout and saved to `summary.md`.

---

## Environment Variables

```bash
ELEVENLABS_API_KEY=...          # ElevenLabs account API key
ELEVENLABS_AGENT_ID=...         # ID of the pre-configured EL agent
ELEVENLABS_PHONE_NUMBER_ID=...  # ID of the Twilio DID registered in EL
```

Twilio credentials are not needed in the Python code — they're configured inside ElevenLabs when you import the phone number. No Anthropic API key needed — summary generation happens in the Claude Code session.

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| No answer | Poll returns `done` with empty transcript. Summary: "No answer." |
| Voicemail | Agent detects voicemail, ends call. Transcript saved. Summary flags it. |
| Busy / failed | API returns error status. Log to `error.log`, report to Zeb. |
| Timeout (>10 min) | Script terminates, saves partial transcript, reports timeout. |
| API error | Retry once, then fail with clear error message. |

---

## Setup Checklist (One-Time)

- [ ] Create ElevenLabs account, get API key
- [ ] Buy a Twilio phone number (~$1.15/month)
- [ ] Import Twilio number into ElevenLabs (Settings → Phone Numbers → Import)
- [ ] Create the EL agent (Conversational AI → New Agent), note the agent ID
- [ ] Set env vars (can live in `workspace/phone-agent/.env`, gitignored)
- [ ] `pip install -r requirements.txt`
- [ ] Test call: `python call.py "+1XXXXXXXXXX" "ask if they are open on weekends"`

---

## Cost Model

> See [`../DESIGN.md`](../DESIGN.md) for the authoritative cost model with source links.

| Component | Rate | 5-min call |
|-----------|------|-----------|
| ElevenLabs Conversational AI | ~$0.08/min | $0.40 |
| Twilio outbound (US) | ~$0.014/min | $0.07 |
| Claude summary (claude-sonnet-4-6) | ~$0.01/call | $0.01 |
| Twilio DID number | $1.15/month | — |
| **Total per call** | | **~$0.48** |

At 10 calls/day: ~$4.80/day, ~$144/month + $1.15 DID = **~$145/month**.  
At 1-2 calls/day (expected): **~$16-30/month**.

---

## Future Extensions

- **Voicemail detection + message**: If voicemail detected, leave a scripted message and end.
- **IVR navigation**: ElevenLabs agents can navigate "press 1 for sales" menus automatically.
- **Callback scheduling**: If nobody answers, re-queue for a different time.
- **Custom caller ID**: With Twilio, can set a display name (e.g., "Zeb Lawrence Consulting").
- **Batch mode**: CSV of numbers + shared goal → call all of them, produce a combined report.
- **Upgrade LLM to Claude**: Swap EL's default model for a Claude endpoint via Vapi if deeper reasoning is needed mid-call.

---

## What Mac Does During a Call

Mac is not live on the call. The ElevenLabs agent conducts the conversation autonomously per the system prompt. Mac's role is:

1. Set up the call with the right goal and persona
2. Wait for completion (polling in background)
3. Analyze the results
4. Report back

This is intentional — real-time intervention would require WebSocket streaming and a much more complex integration. The current design is reliable, simple, and sufficient for the stated use cases.
