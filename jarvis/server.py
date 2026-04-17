#!/usr/bin/env python3
import os
import sys
import asyncio
import tempfile
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

sys.path.insert(0, str(Path(__file__).parent))
import stt
import llm
import tts

app = FastAPI()
executor = ThreadPoolExecutor(max_workers=2)
STATIC_DIR = Path(__file__).parent / "static"


async def run_sync(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, func, *args)


def convert_to_wav(input_path: str, output_path: str) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", input_path, "-ar", "16000", "-ac", "1", output_path],
        check=True,
        capture_output=True,
    )


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    print("[Server] Client connected")

    try:
        while True:
            # Receive audio bytes from browser (webm/opus)
            audio_bytes = await ws.receive_bytes()

            webm_tmp = None
            wav_tmp = None
            mp3_path = None

            try:
                # Save incoming audio
                webm_tmp = tempfile.NamedTemporaryFile(suffix=".webm", delete=False)
                webm_tmp.write(audio_bytes)
                webm_tmp.close()

                # Convert to WAV for Whisper
                wav_tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                wav_tmp.close()
                await run_sync(convert_to_wav, webm_tmp.name, wav_tmp.name)

                # Transcribe
                await ws.send_json({"status": "transcribing"})
                transcript = await run_sync(stt.transcribe, wav_tmp.name)

                if not transcript:
                    await ws.send_json({"status": "idle", "error": "no_speech"})
                    continue

                await ws.send_json({"status": "thinking", "transcript": transcript})

                # LLM
                response = await run_sync(llm.chat, transcript)

                await ws.send_json({"status": "speaking", "text": response})

                # TTS
                mp3_path = await run_sync(tts.speak, response)
                with open(mp3_path, "rb") as f:
                    audio_data = f.read()

                await ws.send_bytes(audio_data)
                await ws.send_json({"status": "idle"})

            except Exception as e:
                print(f"[Error] {e}")
                await ws.send_json({"status": "idle", "error": str(e)})
            finally:
                for path in [
                    webm_tmp.name if webm_tmp else None,
                    wav_tmp.name if wav_tmp else None,
                    mp3_path,
                ]:
                    if path:
                        try:
                            os.unlink(path)
                        except OSError:
                            pass

    except WebSocketDisconnect:
        print("[Server] Client disconnected")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5173))
    print(f"[Jarvis] Starting server on http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
