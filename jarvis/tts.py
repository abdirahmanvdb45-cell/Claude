import os
import tempfile
from elevenlabs.client import ElevenLabs
from elevenlabs import save

# A deep, calm, authoritative voice — closest to Jarvis
# Default: "Adam" (premade ElevenLabs voice). Override with ELEVENLABS_VOICE_ID env var.
DEFAULT_VOICE_ID = "UmQN7jS1Ee8B1czsUtQh"

_client: ElevenLabs | None = None


def _get_client() -> ElevenLabs:
    global _client
    if _client is None:
        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            raise ValueError("ELEVENLABS_API_KEY environment variable not set.")
        _client = ElevenLabs(api_key=api_key)
    return _client


def speak(text: str) -> str:
    """Convert text to speech. Returns path to temp MP3 file."""
    client = _get_client()
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)
    model_id = os.getenv("ELEVENLABS_MODEL", "eleven_turbo_v2")  # fastest model

    audio = client.generate(
        text=text,
        voice=voice_id,
        model=model_id,
    )

    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    save(audio, tmp.name)
    return tmp.name
