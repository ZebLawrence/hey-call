/**
 * Twilio Function — ElevenLabs post-call webhook receiver
 *
 * Receives the `post_call_transcription` event from ElevenLabs after an
 * inbound call to the Twilio number handled by the EL agent, and SMSes
 * a summary + first few transcript turns to the NOTIFY_TO number.
 *
 * Setup:
 *   1. Twilio Console → Functions and Assets → Services → new or existing service
 *   2. New Function → Path `/elevenlabs-webhook` → Visibility: Public
 *   3. Paste this file as the function body
 *   4. Service → Environment Variables:
 *        ELEVENLABS_AGENT_SECRET = your ElevenLabs agent ID (acts as a shared secret)
 *        NOTIFY_TO               = recipient phone in E.164 (e.g. +1...)
 *        NOTIFY_FROM             = your Twilio voice/SMS number (e.g. +1...)
 *      Service → Dependencies: none extra needed; Twilio client is built in
 *   5. Deploy → copy the public URL (https://<service>-<hash>.twil.io/elevenlabs-webhook)
 *   6. ElevenLabs agent → Workflows → Post-call webhook → paste the URL
 *   7. Place a test call; check phone for SMS
 *
 * Auth approach:
 *   Twilio Functions doesn't expose the raw request body, so HMAC body-hash
 *   verification isn't possible here. Instead we check two things:
 *     1. The `elevenlabs-signature` header is present and its timestamp is fresh.
 *     2. event.data.agent_id matches ELEVENLABS_AGENT_SECRET, confirming the
 *        payload came from our agent and not some other EL account.
 */

const ALLOWED_SIG_AGE_SEC = 30 * 60; // reject webhooks older than 30 min

function verifyRequest(sigHeader, agentId, agentSecret) {
  // 1. Signature header must be present and carry a fresh timestamp
  if (!sigHeader) return { ok: false, reason: 'missing-elevenlabs-signature' };

  const parts = Object.fromEntries(
    sigHeader.split(',').map(s => {
      const [k, ...rest] = s.split('=');
      return [k.trim(), rest.join('=').trim()];
    })
  );

  const t = parts.t;
  if (!t || !Number.isFinite(Number(t))) return { ok: false, reason: 'malformed-signature' };

  const age = Math.abs(Math.floor(Date.now() / 1000) - Number(t));
  if (age > ALLOWED_SIG_AGE_SEC) {
    return { ok: false, reason: `stale-signature (age=${age}s)` };
  }

  // 2. Payload must reference our agent ID
  if (!agentId || agentId !== agentSecret) {
    return { ok: false, reason: 'agent-mismatch' };
  }

  return { ok: true, reason: 'ok' };
}

function fmtDuration(secs) {
  if (!Number.isFinite(secs)) return '?';
  const m = Math.floor(secs / 60);
  const s = Math.round(secs % 60);
  return m > 0 ? `${m}m${s}s` : `${s}s`;
}

function pickCallerNumber(data) {
  // Try several likely locations; EL/Twilio integrations vary
  const init = data.conversation_initiation_client_data || {};
  const dyn = init.dynamic_variables || {};
  return (
    dyn.system__caller_id ||
    dyn.caller_id ||
    dyn.from_number ||
    dyn.from ||
    data.metadata?.phone_call?.external_number ||
    data.metadata?.phone_call?.from_number ||
    'unknown'
  );
}

exports.handler = async function (context, event, callback) {
  const twiml = new Twilio.Response();
  twiml.appendHeader('Content-Type', 'application/json');

  try {
    // 1. Auth: fresh timestamp + agent ID check
    const sigHeader = event.request?.headers?.['elevenlabs-signature'];
    const agentId = event.data?.agent_id;

    if (context.ELEVENLABS_AGENT_SECRET) {
      const v = verifyRequest(sigHeader, agentId, context.ELEVENLABS_AGENT_SECRET);
      if (!v.ok) {
        console.warn('auth-failed', v.reason);
        twiml.setStatusCode(401);
        twiml.setBody({ error: 'unauthorized', reason: v.reason });
        return callback(null, twiml);
      }
    }

    // 2. Only handle post_call_transcription — ignore audio + init-failure for now
    if (event.type !== 'post_call_transcription') {
      twiml.setStatusCode(200);
      twiml.setBody({ status: 'ignored', type: event.type });
      return callback(null, twiml);
    }

    const data = event.data || {};
    const convoId = data.conversation_id || '?';
    const duration = data.metadata?.call_duration_secs ?? 0;
    const termination = data.metadata?.termination_reason || '';
    const successful = data.analysis?.call_successful || 'unknown';
    const summary = (data.analysis?.transcript_summary || '').trim();
    const from = pickCallerNumber(data);

    const turns = (data.transcript || []).filter(t => t.message && t.message.trim());
    const firstFour = turns
      .slice(0, 4)
      .map(t => `${t.role === 'agent' ? 'AI' : 'Caller'}: ${t.message.replace(/\s+/g, ' ').trim()}`)
      .join('\n');

    // 3. Compose SMS body, keep under 1500 chars for safety
    let body = `📞 ${fmtDuration(duration)} · ${successful}\nFrom: ${from}\n\n`;
    if (summary) body += `${summary}\n\n`;
    if (firstFour) body += `— First exchange —\n${firstFour}\n\n`;
    if (termination) body += `End: ${termination}\n`;
    body += `ID: ${convoId}`;

    if (body.length > 1500) body = body.slice(0, 1497) + '...';

    // 4. Send via Twilio
    const client = context.getTwilioClient();
    const msg = await client.messages.create({
      from: context.NOTIFY_FROM,
      to: context.NOTIFY_TO,
      body,
    });

    twiml.setStatusCode(200);
    twiml.setBody({ status: 'sent', sid: msg.sid, to: context.NOTIFY_TO });
    return callback(null, twiml);
  } catch (err) {
    console.error('webhook-error', err);
    twiml.setStatusCode(500);
    twiml.setBody({ error: 'internal', message: String(err?.message || err) });
    return callback(null, twiml);
  }
};
