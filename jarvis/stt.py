import os
from faster_whisper import WhisperModel

_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        # "base" is fast and accurate enough for voice commands
        # Use "small" or "medium" for better accuracy at cost of speed
        model_size = os.getenv("WHISPER_MODEL", "base")
        device = os.getenv("WHISPER_DEVICE", "cpu")
        compute_type = "int8" if device == "cpu" else "float16"
        print(f"[STT] Loading Whisper model '{model_size}' on {device}...")
        _model = WhisperModel(model_size, device=device, compute_type=compute_type)
        print("[STT] Model loaded.")
    return _model


def transcribe(audio_path: str) -> str:
    """Transcribe audio file to text. Returns empty string if nothing detected."""
    model = _get_model()
    segments, info = model.transcribe(audio_path, beam_size=5, language="en")
    text = " ".join(seg.text.strip() for seg in segments).strip()
    return text
