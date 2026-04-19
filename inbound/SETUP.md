# Inbound Call → SMS Notification

Forward ElevenLabs post-call transcription webhooks to your phone as SMS.

Architecture: `Caller → Twilio number → ElevenLabs agent → (call ends) → ElevenLabs webhook → Twilio Function → Twilio SMS → your phone`.

No local webhook exposure. Everything runs in cloud services you already pay for.

## One-time setup

### 1. Create the Twilio Function
1. Open https://console.twilio.com/us1/develop/functions/services → **Create Service** (name it `hey-call-inbound`).
2. In the service, **Add → Function**. Path: `/elevenlabs-webhook`. Visibility: **Public**.
3. Paste the contents of `elevenlabs-webhook.js` into the editor.
4. Click **Save**.

### 2. Add environment variables
Service → **Environment Variables**:

| Key | Value |
| --- | --- |
| `ELEVENLABS_WEBHOOK_SECRET` | (the HMAC secret from the EL agent's post-call webhook settings — generated when you create the webhook) |
| `NOTIFY_TO` | Recipient phone in E.164 (e.g. `+1...`) |
| `NOTIFY_FROM` | Your Twilio voice/SMS number (the inbound number the caller dials) |

### 3. Deploy
Click **Deploy All**. Twilio gives you a public URL like:
`https://hey-call-inbound-1234.twil.io/elevenlabs-webhook`

### 4. Wire up ElevenLabs
1. ElevenLabs Dashboard → **Agents** → the agent handling this number.
2. **Workflows** → **Post-call webhook** → paste the Twilio Function URL.
3. Save. Copy the generated HMAC secret if you haven't already — that's `ELEVENLABS_WEBHOOK_SECRET` above.

### 5. Test
Call the Twilio number. Let the AI agent handle it for ~30s, then hang up. Within ~10s you should get an SMS with the summary + first few transcript lines.

## Logs + debugging
- Twilio Function logs: Console → Functions → your Service → **Logs** (live tail). Any 401 means signature mismatch — double-check `ELEVENLABS_WEBHOOK_SECRET`.
- ElevenLabs webhook delivery history: agent → Workflows → the webhook has a recent-deliveries panel with status codes.
- If SMS arrives but summary is empty: EL takes a few seconds to finalize `analysis.transcript_summary`; very short calls may not have one.

## Extending later
- Swap SMS for iMessage: route to an iMessage bridge (imsg CLI on the Mac, or a relay service). But SMS to your iPhone already shows as an iMessage/SMS thread natively, so this is rarely worth it.
- Store full transcripts: add a step that PUTs the full JSON to a Cloudflare R2 bucket or appends to a Google Sheet via the Sheets API, then include the link in the SMS.
- Filter by outcome: only notify on `call_successful !== "success"` to get alerts only on calls that need attention.
- Create GitHub issues from unsuccessful calls: add a GitHub API call before the SMS.

## Cost
- Twilio Functions: free tier covers ~10k executions/month.
- SMS: ~$0.008 per outbound US SMS.
- So ~$0.01 per inbound call notification.
