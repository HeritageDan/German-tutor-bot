"""
Azure Speech wrapper: text-to-speech (for outbound voice notes) and
speech-to-text (for transcribing your inbound voice notes).

WhatsApp requires audio in OGG/Opus format, so TTS output gets converted
via pydub (which needs ffmpeg installed on your server — see README).
"""

import os
import uuid

import azure.cognitiveservices.speech as speechsdk
from pydub import AudioSegment

from config import AZURE_SPEECH_KEY, AZURE_SPEECH_REGION, AZURE_GERMAN_VOICE

TMP_DIR = "tmp_audio"
os.makedirs(TMP_DIR, exist_ok=True)


def text_to_speech_ogg(text: str) -> str:
    """
    Converts German text to an OGG/Opus audio file ready to send via WhatsApp.
    Returns the file path.
    """
    speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
    speech_config.speech_synthesis_voice_name = AZURE_GERMAN_VOICE

    raw_wav_path = os.path.join(TMP_DIR, f"{uuid.uuid4()}.wav")
    audio_config = speechsdk.audio.AudioOutputConfig(filename=raw_wav_path)

    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
    result = synthesizer.speak_text_async(text).get()

    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        raise RuntimeError(f"TTS failed: {result.reason}")

    ogg_path = os.path.join(TMP_DIR, f"{uuid.uuid4()}.ogg")
    sound = AudioSegment.from_wav(raw_wav_path)
    sound.export(ogg_path, format="ogg", codec="libopus")

    os.remove(raw_wav_path)
    return ogg_path


def speech_to_text_from_file(audio_file_path: str) -> str:
    """
    Transcribes an inbound voice note. WhatsApp sends OGG/Opus — Azure STT wants WAV,
    so we convert first.
    """
    wav_path = os.path.join(TMP_DIR, f"{uuid.uuid4()}.wav")
    sound = AudioSegment.from_file(audio_file_path)
    sound.export(wav_path, format="wav")

    speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
    speech_config.speech_recognition_language = "de-DE"
    audio_config = speechsdk.audio.AudioConfig(filename=wav_path)

    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
    result = recognizer.recognize_once()

    os.remove(wav_path)

    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        return result.text
    elif result.reason == speechsdk.ResultReason.NoMatch:
        return ""  # couldn't make out any speech
    else:
        raise RuntimeError(f"STT failed: {result.reason}")


def cleanup_file(path: str) -> None:
    if path and os.path.exists(path):
        os.remove(path)
