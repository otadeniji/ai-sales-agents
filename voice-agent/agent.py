"""Sales voice agent — LiveKit Agents.

Shared brain for both lanes:
  - Phone lane: Telnyx number -> LiveKit SIP trunk -> room -> this agent.
    SIP dispatch rule creates rooms named "<SIP_ROOM_PREFIX><caller>" (default
    "call-"), so the agent skips the avatar there.
  - Web lane:   browser -> LiveKit room (WebRTC) -> this agent + Simli avatar.

Simli wiring verified against https://docs.livekit.io/agents/integrations/avatar/simli/
(livekit-plugins-simli; AvatarSession takes simli.SimliConfig with required
face_id + emotion_id, and must be started BEFORE session.start()).

Run:
    pip install -r requirements.txt
    cp ../.env.example ../.env   # then fill in keys
    python agent.py dev        # dev mode
    python agent.py start      # production worker
"""

import logging
import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from livekit import agents
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import deepgram, openai, silero

logger = logging.getLogger("sales-agent")

# Simli avatar plugin (web lane only).
try:
    from livekit.plugins import simli

    HAS_SIMLI = True
except ImportError:  # pragma: no cover
    simli = None  # type: ignore
    HAS_SIMLI = False

# Must match the roomPrefix in sip/dispatch-rule.json.
SIP_ROOM_PREFIX = os.environ.get("SIP_ROOM_PREFIX", "call-")

SALES_SYSTEM_PROMPT = """You are a friendly AI sales agent for the business.
Keep replies short and conversational — this is spoken, not written.
- Greet callers warmly, ask what they're looking for.
- Answer product questions from the catalog (TODO: wire real catalog).
- Offer to book an appointment or take their details for a callback.
- Never claim to be human. If asked, say you're the business's AI assistant.
- Keep every turn under ~30 seconds of speech.
"""


class SalesAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=SALES_SYSTEM_PROMPT,
            stt=deepgram.STT(),
            llm=openai.LLM(model="gpt-4o-mini"),
            # Swap for cartesia.TTS() or elevenlabs.TTS() if preferred:
            tts=openai.TTS(),
            turn_detection=silero.VAD.load(),
        )


async def entrypoint(ctx: JobContext):
    await ctx.connect()
    room_name = ctx.room.name or ""
    is_phone_call = room_name.startswith(SIP_ROOM_PREFIX)
    logger.info("incoming session room=%s phone_lane=%s", room_name, is_phone_call)

    session = AgentSession()

    # Web lane: attach the Simli lip-synced avatar before starting the session.
    if not is_phone_call and HAS_SIMLI:
        face_id = os.environ.get("SIMLI_FACE_ID", "")
        emotion_id = os.environ.get("SIMLI_EMOTION_ID", "")
        if face_id and emotion_id:
            avatar = simli.AvatarSession(
                simli.SimliConfig(face_id=face_id, emotion_id=emotion_id)
            )
            await avatar.start(session, room=ctx.room)
            logger.info("Simli avatar attached (face_id=%s)", face_id)
        else:
            logger.warning(
                "SIMLI_FACE_ID / SIMLI_EMOTION_ID not set — "
                "web lane will be voice-only until configured."
            )
    elif not is_phone_call:
        logger.warning("livekit-plugins-simli not installed — web lane voice-only.")

    await session.start(agent=SalesAgent(), room=ctx.room)

    # Greet right after the session starts (pickup on phone, join on web).
    await session.generate_reply(
        instructions="Greet the caller warmly and ask how you can help."
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cli.run_app(
        WorkerOptions(entrypoint_fnc=entrypoint, agent_name="sales-voice-agent")
    )
