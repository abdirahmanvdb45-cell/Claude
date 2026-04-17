#!/usr/bin/env python3
"""
Jarvis — Voice AI Agent
Push Enter to speak, Ctrl+C to exit.
"""

import os
import sys
import tempfile
from dotenv import load_dotenv

load_dotenv()

import audio
import stt
import llm
import tts


WAKE_PHRASES = {"goodbye jarvis", "shut down", "goodbye", "exit", "quit"}


def _cleanup(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def run() -> None:
    print("=" * 50)
    print("  J.A.R.V.I.S.  —  Online")
    print("  Press Enter to speak | Ctrl+C to exit")
    print("=" * 50)

    # Greet on startup
    greeting = llm.chat("You've just been activated. Greet your user briefly.")
    print(f"\n[Jarvis] {greeting}")
    audio_path = tts.speak(greeting)
    audio.play_audio(audio_path)
    _cleanup(audio_path)

    while True:
        try:
            input("\nPress Enter to speak...")
        except EOFError:
            # Non-interactive mode — just wait
            import time
            time.sleep(0.5)
            continue
        except KeyboardInterrupt:
            _shutdown()
            return

        # Record
        wav_path = None
        mp3_path = None
        try:
            wav_path = audio.record_until_silence()

            # Transcribe
            print("[Jarvis] Processing...")
            transcript = stt.transcribe(wav_path)
            _cleanup(wav_path)
            wav_path = None

            if not transcript:
                print("[Jarvis] I didn't catch that, sir.")
                continue

            print(f"\n[You] {transcript}")

            # Check for exit commands
            if transcript.lower().strip().rstrip(".,!?") in WAKE_PHRASES:
                farewell = llm.chat("The user is shutting you down. Say a brief farewell.")
                print(f"[Jarvis] {farewell}")
                mp3_path = tts.speak(farewell)
                audio.play_audio(mp3_path)
                _cleanup(mp3_path)
                return

            # Get LLM response
            response = llm.chat(transcript)
            print(f"[Jarvis] {response}")

            # Speak response
            mp3_path = tts.speak(response)
            audio.play_audio(mp3_path)

        except KeyboardInterrupt:
            _shutdown()
            return
        except Exception as e:
            print(f"[Error] {e}", file=sys.stderr)
        finally:
            if wav_path:
                _cleanup(wav_path)
            if mp3_path:
                _cleanup(mp3_path)


def _shutdown() -> None:
    print("\n[Jarvis] Shutting down. Good day, sir.")


if __name__ == "__main__":
    run()
