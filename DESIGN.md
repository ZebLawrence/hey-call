# AI Phone Caller — Design Spec

**Date:** 2026-04-16  
**Status:** Draft — pending implementation  
**Strategy:** ElevenLabs Conversational AI + Twilio  

### API Documentation Links

| Service | Resource | URL |
|---------|----------|-----|
| ElevenLabs | Outbound Call API | https://elevenlabs.io/docs/api-reference/conversational-ai/twilio-outbound-call |
| ElevenLabs | Get Conversation | https://elevenlabs.io/docs/api-reference/conversational-ai/get-conversation |
| ElevenLabs | Get Conversation Audio | https://elevenlabs.io/docs/api-reference/conversational-ai/get-conversation-audio |
| ElevenLabs | Create Phone Number (Twilio Import) | https://elevenlabs.io/docs/api-reference/conversational-ai/create-phone-number |
| ElevenLabs | Twilio Native Integration Guide | https://elevenlabs.io/docs/eleven-agents/phone-numbers/twilio-integration/native-integration |
| Twilio | Phone Number Pricing | https://help.twilio.com/articles/223182908-How-much-does-a-phone-number-cost- |
| Twilio | Voice Pricing (US) | https://www.twilio.com/en-us/voice/pricing/us |
| Twilio | Buy a Phone Number | https://help.twilio.com/articles/223135247-How-to-Search-for-and-Buy-a-Twilio-Phone-Number-from-Console |
| Twilio | Account SID & Auth Token | https://help.twilio.com/articles/14726256820123-What-is-a-Twilio-Account-SID-and-where-can-I-find-it- |

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
│  5. Save artifacts + print transcript to stdout     │
│  6. Mac (Claude Code) analyzes in-session           │
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
| `report.py` | Transcript formatting + artifact saving |
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
   │   Docs: https://elevenlabs.io/docs/api-reference/conversational-ai/twilio-outbound-call
   │
4. Poll GET /v1/convai/conversations/{id} with backoff
   │   → status: "initiated" | "in-progress" | "processing" | "done" | "failed"
   │   → poll every 5s for the first 2 min, then every 10s
   │   → timeout: 15 minutes
   │   → transcript entries may have null `message` field — skip those
   │   Docs: https://elevenlabs.io/docs/api-reference/conversational-ai/get-conversation
   │
5. On "done":
   │   transcript is in the GET response body (.transcript array)
   │   check response `has_audio` field before fetching
   │   GET /v1/convai/conversations/{id}/audio    → recording.mp3
   │   Docs: https://elevenlabs.io/docs/api-reference/conversational-ai/get-conversation-audio
   │
6. Save all artifacts to workspace/calls/<dir>/
   │   Print formatted transcript to stdout
   │
7. Mac (Claude Code) reads the output and generates
   a structured summary in-session — no separate API call
```

---

## ElevenLabs Agent Configuration

One persistent agent is pre-configured in the ElevenLabs dashboard. Per-call customization happens via `conversation_initiation_client_data.conversation_config_override.agent` in the API call (so we don't create a new agent per call). See [ElevenLabs Outbound Call API](https://elevenlabs.io/docs/api-reference/conversational-ai/twilio-outbound-call) for the full schema.

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

Summary generation happens **in the Claude Code session**, not via a separate API call. After `call.py` prints the transcript to stdout, Mac reads it and produces a structured analysis:

```
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

Mac saves this summary to `summary.md` in the call's artifact directory. This approach has zero additional API cost and leverages the existing Claude Code session context.

---

## Environment Variables

```bash
ELEVENLABS_API_KEY=...          # ElevenLabs account API key
ELEVENLABS_AGENT_ID=...         # ID of the pre-configured EL agent
ELEVENLABS_PHONE_NUMBER_ID=...  # ID of the Twilio DID registered in EL
```

Twilio credentials are not needed in the Python code — they're configured inside ElevenLabs when you import the phone number. No Anthropic API key is needed — summary generation happens in the Claude Code session.

---

## Input Validation

Phone numbers must be E.164 format (`+` followed by 10-15 digits, e.g. `+13035551234`). `call.py` validates this before making any API calls and exits with a clear error if the format is wrong.

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Invalid phone number | Reject before API call with format guidance. |
| No answer | Poll returns `done` with empty transcript. Summary: "No answer." |
| Voicemail | Agent follows voicemail instructions in system prompt (leave brief message, end call). Transcript saved. Summary flags it. |
| Busy / failed | API returns `failed` status. Save whatever metadata exists, report to Zeb. |
| Timeout (>15 min) | Script terminates, attempts to fetch partial transcript if available, reports timeout. |
| No audio available | Check `has_audio` field from conversation response. Skip audio fetch if false. |
| Null transcript messages | Filter out transcript entries with null `message` field during formatting. |
| API error | Retry once, then fail with clear error message. |

---

## Setup Checklist (One-Time)

- [ ] Create [ElevenLabs](https://elevenlabs.io) account → Settings → API Keys → copy key
- [ ] Buy a Twilio phone number (~$1.15/month) — [Console → Develop → Phone Numbers → Buy a Number](https://console.twilio.com/us1/develop/phone-numbers/manage/search) ([guide](https://help.twilio.com/articles/223135247-How-to-Search-for-and-Buy-a-Twilio-Phone-Number-from-Console))
- [ ] Get Twilio Account SID + Auth Token from [Console Dashboard](https://console.twilio.com/) → Account Info ([guide](https://help.twilio.com/articles/14726256820123-What-is-a-Twilio-Account-SID-and-where-can-I-find-it-))
- [ ] Import Twilio number into ElevenLabs — [Conversational AI → Phone Numbers → Add → Import from Twilio](https://elevenlabs.io/docs/eleven-agents/phone-numbers/twilio-integration/native-integration) ([API](https://elevenlabs.io/docs/api-reference/conversational-ai/create-phone-number))
- [ ] Create EL agent (Conversational AI → Create Agent), note the agent ID
- [ ] Set env vars (copy `.env.example` to `.env`, fill in keys)
- [ ] `pip install -r requirements.txt`
- [ ] Test call: `python call.py "+1XXXXXXXXXX" "ask if they are open on weekends"`

---

## Cost Model

| Component | Rate | 5-min call | Source |
|-----------|------|-----------|--------|
| ElevenLabs Conversational AI | ~$0.08/min | $0.40 | [EL Pricing](https://elevenlabs.io/pricing) |
| Twilio outbound (US) | ~$0.014/min | $0.07 | [Twilio Voice Pricing](https://www.twilio.com/en-us/voice/pricing/us) |
| Summary generation | $0 | $0 | Done in-session by Claude Code (Mac) |
| Twilio DID number | $1.15/month | — | [Twilio Number Pricing](https://help.twilio.com/articles/223182908-How-much-does-a-phone-number-cost-) |
| **Total per call** | | **~$0.47** | |

At 10 calls/day: ~$4.70/day, ~$141/month + $1.15 DID = **~$142/month**.  
At 1-2 calls/day (expected): **~$15-29/month**.

---

## Future Extensions

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
