# Telnyx -> LiveKit SIP wiring notes

Goal: a caller dials your Telnyx number, Telnyx forwards via SIP to LiveKit,
LiveKit drops the call into a room and dispatches `sales-voice-agent`.

## 1. Telnyx side (Mission Control portal — your step)

1. Buy a phone number (~$1/mo).
2. Create a SIP Connection (elastic SIP trunking).
3. Under the connection's **origination/outbound** settings, point it at your
   LiveKit SIP URI: `sip:<your-livekit-project>.sip.livekit.cloud`
   (find this in the LiveKit Cloud dashboard under Settings -> SIP).
4. Attach the phone number to the connection.

## 2. LiveKit side (I do this once I have your LiveKit API key/secret)

```bash
# install the LiveKit CLI: https://docs.livekit.io/home/cli
cd ~/workspace/ai-sales-agents
lk sip inbound create sip/inbound-trunk.json   # -> prints trunk ID (ST_...)
# paste the trunk ID into sip/dispatch-rule.json, then:
lk sip dispatch create sip/dispatch-rule.json  # routes calls to the agent
```

`sip/dispatch-rule.json` — every call gets its own room, agent dispatched
(paste your trunk ID into the file before running):

```json
{
  "trunk": {
    "name": "telnyx-inbound",
    "numbers": ["+1XXXXXXXXXX"]
  }
}
```

`dispatch-rule.json` — every call gets its own room, agent dispatched:
```json
{
  "dispatch_rule": {
    "rule": { "dispatchRuleIndividual": { "roomPrefix": "call-" } },
    "roomConfig": { "agents": [{ "agentName": "sales-voice-agent" }] }
  },
  "trunkIds": ["ST_YOUR_TRUNK_ID"]
}
```

The `agentName` must match `agent_name="sales-voice-agent"` in
`voice-agent/agent.py`.

## 3. Run the agent

```bash
cd voice-agent
pip install -r requirements.txt
python agent.py start
```

Then dial the Telnyx number — the agent should pick up and greet you.

## Cost recap (approx)

- Number: ~$1/mo. Per-minute: ~$0.002 (Voice API) + ~$0.0032–0.005 (SIP).
- Inbound SIP channels: first 10 channels $12/mo (only matters at scale).
