# AI Sales Agents — Simli + LiveKit + Telnyx

Two lanes, one shared voice brain:

```
VOICE CALLS LANE (Telnyx + LiveKit)
Caller ──PSTN──▶ Telnyx number ──SIP──▶ LiveKit SIP trunk ──▶ LiveKit room
                                                          │
                                              ┌───────────┴───────────┐
                                              ▼           ▼           ▼
                                            STT         LLM         TTS
                                         (Deepgram)  (OpenAI)   (Cartesia/ElevenLabs)
                                              │                       │
                                              └─────── Agent ─────────┘
                                                        │ audio
                                                        ▼
                                                     Caller

AVATAR LANE (Simli + LiveKit, website)
Visitor ──browser──▶ LiveKit room (WebRTC) ──▶ same voice agent pipeline
                                                        │ agent audio
                                                        ▼
                                              Simli lip-synced avatar
                                              (livekit.plugins.simli)
```

Both lanes share one agent brain (`voice-agent/agent.py`). Simli only renders
on the web lane; phone callers just hear the voice.

## Costs (approx, Oct 2026 — verify before committing)

- **Simli**: Free tier 50 min/mo; Hobby $10/mo (1,000 min); Pro $49/mo (5,500 min).
  ~$0.009–0.01/min. Cheapest real-time avatar option found.
- **LiveKit**: Cloud has a free tier; self-hosting the open-source server is free
  (you'd pay for your own VPS). STT/LLM/TTS billed by their providers.
- **Telnyx**: Numbers ~$1/mo. Voice ~$0.002/min + SIP trunking ~$0.0032–0.005/min.
  Pure pay-as-you-go, no seats.

Reality check: 1,000 call-minutes/mo ≈ roughly $85–$230 all-in depending on
model/voice choices.

## Setup — your steps (I can't do these for you)

1. **Telnyx** — sign up, buy a phone number (~$1/mo), create a SIP connection.
   See `telnyx-sip-notes.md` for the exact trunk config.
2. **LiveKit** — sign up at LiveKit Cloud (or I'll self-host the OSS server).
   Grab the API key + secret and your SIP URI from the dashboard.
3. **Simli** — sign up, create a face/avatar, grab the API key + face ID.
4. Hand me the API keys (I'll give you a secure way to share them — never
   paste secrets in chat).

## Setup — my steps (once I have the keys)

1. Fill in `.env`, install deps, verify the agent boots.
2. Create the LiveKit inbound SIP trunk + dispatch rule pointing at Telnyx.
3. Wire the Simli avatar plugin for the web lane.
4. Test call + test web session, then hand you the demo links.

## Compliance note

Inbound agents and website avatars are the clean lane. Automated outbound
sales calls are heavily regulated in the US (robocall/TCPA rules) — I won't
set up cold-call blasting.

## Status

🟡 Wired, untested. Everything that doesn't need secrets is done:

- `voice-agent/agent.py` — voice pipeline + Simli avatar wiring (avatar attaches
  on the web lane, skipped for phone calls detected by the `call-` room prefix).
- `web-avatar/token_server.py` — serves the demo page, mints LiveKit tokens,
  and auto-dispatches the agent to the web room.
- `web-avatar/index.html` — full LiveKit client: mic, avatar video, agent audio.
- `sip/inbound-trunk.json` + `sip/dispatch-rule.json` — ready-made templates.

Still blocked on API keys (your step above). Once they're in `.env`:

```bash
cd voice-agent && pip install -r requirements.txt && python agent.py dev
cd web-avatar && python token_server.py   # open http://localhost:8000
lk sip inbound create sip/inbound-trunk.json    # -> note the ST_... trunk ID
lk sip dispatch create sip/dispatch-rule.json   # paste the trunk ID first
```
