"""
Speech handling:
- Text-to-Speech via ElevenLabs (free tier, no card required)
- Speech-to-Text via a self-hosted Whisper model (faster-whisper) — runs locally,
  no API key, no account, completely free. Slightly slower on Render's free CPU tier.
"""

import os
import uuid

import requests
from pydub import AudioSegment
from faster_whisper import WhisperModel

from config import ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, ELEVENLABS_MODEL

TMP_DIR = "tmp_audio"
os.makedirs(TMP_DIR, exist_ok=True)

# Loaded once at startup, kept in memory — "tiny" keeps RAM usage low enough
# for Render's free tier (512MB total). First request after a cold start
# will be slower while the model loads/downloads.
_whisper_model = None

def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
    return _whisper_model

def text_to_speech_ogg(text: str) -> str:
    """Converts German text to an OGG/Opus audio file ready to send via WhatsApp."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": ELEVENLABS_MODEL,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()

    mp3_path = os.path.join(TMP_DIR, f"{uuid.uuid4()}.mp3")
    with open(mp3_path, "wb") as f:
        f.write(response.content)

    ogg_path = os.path.join(TMP_DIR, f"{uuid.uuid4()}.ogg")
    sound = AudioSegment.from_mp3(mp3_path)
    sound.export(ogg_path, format="ogg", codec="libopus")

    os.remove(mp3_path)
    return ogg_path


def speech_to_text_from_file(audio_file_path: str) -> str:
    """Transcribes an inbound voice note using the local Whisper model."""
    segments, _ = _whisper_model.transcribe(audio_file_path, language="de")
    text = " ".join(segment.text for segment in segments).strip()
    return text


def cleanup_file(path: str) -> None:
    if path and os.path.exists(path):
        os.remove(path)
