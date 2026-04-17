import os
import tempfile
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav


SAMPLE_RATE = 16000
CHANNELS = 1


def record_until_silence(
    silence_threshold: float = 0.01,
    silence_duration: float = 1.5,
    max_duration: float = 30.0,
) -> str:
    """Record audio until silence is detected. Returns path to temp WAV file."""
    print("\n[Jarvis] Listening... (speak now)")

    frames = []
    silent_frames = 0
    silence_limit = int(silence_duration * SAMPLE_RATE)
    max_frames = int(max_duration * SAMPLE_RATE)
    total_frames = 0
    recording_started = False

    def callback(indata, frame_count, time_info, status):
        nonlocal silent_frames, total_frames, recording_started
        frames.append(indata.copy())
        rms = np.sqrt(np.mean(indata ** 2))
        total_frames += frame_count

        if rms > silence_threshold:
            recording_started = True
            silent_frames = 0
        elif recording_started:
            silent_frames += frame_count

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="float32",
        callback=callback,
        blocksize=1024,
    ):
        while True:
            sd.sleep(100)
            if recording_started and silent_frames >= silence_limit:
                break
            if total_frames >= max_frames:
                break

    audio = np.concatenate(frames, axis=0).flatten()
    audio_int16 = (audio * 32767).astype(np.int16)

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    wav.write(tmp.name, SAMPLE_RATE, audio_int16)
    return tmp.name


def play_audio(file_path: str) -> None:
    """Play a WAV or MP3 audio file."""
    import subprocess
    # Use aplay for WAV, mpg123/ffplay for others
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".wav":
        subprocess.run(["aplay", "-q", file_path], check=False)
    elif ext == ".mp3":
        # Try mpg123 first, fall back to ffplay
        result = subprocess.run(["which", "mpg123"], capture_output=True)
        if result.returncode == 0:
            subprocess.run(["mpg123", "-q", file_path], check=False)
        else:
            subprocess.run(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", file_path], check=False)
    else:
        subprocess.run(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", file_path], check=False)
