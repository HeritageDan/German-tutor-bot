"""
Speech handling:
- text_to_speech_ogg()        → for WhatsApp (requires OGG/Opus format)
- text_to_speech_mp3_base64() → for web app (MP3, universally supported, no conversion needed)
- speech_to_text_from_file()  → transcribe a local file via self-hosted Whisper
- speech_to_text_from_bytes() → transcribe raw audio bytes from browser MediaRecorder
"""

import base64
import os
import uuid

import requests
from pydub import AudioSegment
from faster_whisper import WhisperModel

from config import ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, ELEVENLABS_MODEL

TMP_DIR = "tmp_audio"
os.makedirs(TMP_DIR, exist_ok=True)

_whisper_model = None


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
    return _whisper_model


def _elevenlabs_mp3_bytes(text: str) -> bytes:
    """Core ElevenLabs call — returns raw MP3 bytes."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": ELEVENLABS_MODEL,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.content


def text_to_speech_ogg(text: str) -> str:
    """WhatsApp TTS: returns local OGG/Opus file path. Caller cleans up."""
    mp3_bytes = _elevenlabs_mp3_bytes(text)
    mp3_path = os.path.join(TMP_DIR, f"{uuid.uuid4()}.mp3")
    with open(mp3_path, "wb") as f:
        f.write(mp3_bytes)
    ogg_path = os.path.join(TMP_DIR, f"{uuid.uuid4()}.ogg")
    AudioSegment.from_mp3(mp3_path).export(ogg_path, format="ogg", codec="libopus")
    os.remove(mp3_path)
    return ogg_path


def text_to_speech_mp3_base64(text: str) -> str:
    """Web TTS: returns base64 MP3 data URI. Works in all browsers including Safari/iOS."""
    mp3_bytes = _elevenlabs_mp3_bytes(text)
    return "data:audio/mpeg;base64," + base64.b64encode(mp3_bytes).decode()


def speech_to_text_from_file(audio_file_path: str) -> str:
    """Transcribes a local audio file (for WhatsApp inbound voice notes)."""
    model = _get_whisper_model()
    segments, _ = model.transcribe(audio_file_path, language="de")
    return " ".join(seg.text for seg in segments).strip()


def speech_to_text_from_bytes(audio_bytes: bytes, mime_type: str = "audio/webm") -> str:
    """Transcribes raw audio bytes from browser MediaRecorder."""
    if "ogg" in mime_type:
        ext = "ogg"
    elif "mp4" in mime_type or "m4a" in mime_type:
        ext = "mp4"
    else:
        ext = "webm"
    tmp_path = os.path.join(TMP_DIR, f"{uuid.uuid4()}.{ext}")
    try:
        with open(tmp_path, "wb") as f:
            f.write(audio_bytes)
        model = _get_whisper_model()
        segments, _ = model.transcribe(tmp_path)
        return " ".join(seg.text for seg in segments).strip()
    finally:
        cleanup_file(tmp_path)


def cleanup_file(path: str) -> None:
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
