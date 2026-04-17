import os
import tempfile
from elevenlabs.client import ElevenLabs

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
    model_id = os.getenv("ELEVENLABS_MODEL", "eleven_turbo_v2")

    audio_iter = client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id=model_id,
    )

    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    for chunk in audio_iter:
        tmp.write(chunk)
    tmp.close()
    return tmp.name
