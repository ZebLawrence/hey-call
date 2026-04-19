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
 *        ELEVENLABS_WEBHOOK_SECRET = (from EL agent → post-call webhook config)
 *        NOTIFY_TO                  = (recipient phone in E.164, e.g. +1...)
 *        NOTIFY_FROM                = (your Twilio voice/SMS number, e.g. +1...)
 *      Service → Dependencies: none extra needed; crypto + Twilio client are built in
 *   5. Deploy → copy the public URL (https://<service>-<hash>.twil.io/elevenlabs-webhook)
 *   6. ElevenLabs agent → Workflows → Post-call webhook → paste the URL
 *   7. Place a test call; check phone for SMS
 */

const crypto = require('crypto');

const ALLOWED_SIG_AGE_SEC = 30 * 60; // reject webhooks older than 30 min

function verifySignature(rawBody, sigHeader, secret) {
  if (!sigHeader || !secret) return { ok: false, reason: 'missing-signature-or-secret' };

  // ElevenLabs format:  "t=<unix>,v0=<hex>"  (may be several comma-separated items)
  const parts = Object.fromEntries(
    sigHeader.split(',').map(s => {
      const [k, ...rest] = s.split('=');
      return [k.trim(), rest.join('=').trim()];
    })
  );
  const t = parts.t;
  const v0 = parts.v0;
  if (!t || !v0) return { ok: false, reason: 'malformed-signature' };

  const age = Math.abs(Math.floor(Date.now() / 1000) - Number(t));
  if (!Number.isFinite(age) || age > ALLOWED_SIG_AGE_SEC) {
    return { ok: false, reason: `stale-signature (age=${age}s)` };
  }

  const expected = crypto
    .createHmac('sha256', secret)
    .update(`${t}.${rawBody}`)
    .digest('hex');

  const a = Buffer.from(expected, 'hex');
  const b = Buffer.from(v0, 'hex');
  if (a.length !== b.length) return { ok: false, reason: 'signature-length-mismatch' };
  const ok = crypto.timingSafeEqual(a, b);
  return { ok, reason: ok ? 'ok' : 'signature-mismatch' };
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
    // 1. Raw body + signature verification
    //    Twilio Functions parses JSON into `event`, but the raw body is also
    //    exposed on `event.request.rawBody` (available when Service has
    //    "Enable ACCESS_CONTROL_ALLOW_ORIGIN" logic; otherwise reconstruct).
    //    Safest: rebuild rawBody from the parsed object and only verify if
    //    we got raw from the request.
    const sigHeader = event.request?.headers?.['elevenlabs-signature'];
    const rawBody =
      event.request?.rawBody ||
      JSON.stringify(
        // Strip the Twilio-injected `request` key so we hash the original payload
        Object.fromEntries(Object.entries(event).filter(([k]) => k !== 'request'))
      );

    if (context.ELEVENLABS_WEBHOOK_SECRET) {
      const v = verifySignature(rawBody, sigHeader, context.ELEVENLABS_WEBHOOK_SECRET);
      if (!v.ok) {
        console.warn('signature-check-failed', v.reason);
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
