"""
Central place for all environment variables / secrets.
Set these in your hosting platform's environment settings (Render, PythonAnywhere, etc.)
Never hardcode real values here — this file just reads from the environment.
"""

import os

# --- Meta WhatsApp Cloud API ---
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")          # Permanent or temporary token from Meta App
META_PHONE_NUMBER_ID = os.environ.get("META_PHONE_NUMBER_ID")    # The phone number ID (not your actual number) from Meta App
META_VERIFY_TOKEN = os.environ.get("META_VERIFY_TOKEN")          # A string YOU choose, used to verify webhook setup
META_API_VERSION = os.environ.get("META_API_VERSION", "v19.0")

# --- Anthropic Claude API ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

# --- ElevenLabs (Text-to-Speech) — free tier, no card required ---
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
ELEVENLABS_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")

# --- Speech-to-Text: self-hosted Whisper model, no API key needed at all ---
# (handled directly in speech.py — nothing to configure here)

# --- Your own WhatsApp number (so the bot only responds to YOU) ---
YOUR_WHATSAPP_NUMBER = os.environ.get("YOUR_WHATSAPP_NUMBER")    # e.g. "2376XXXXXXXX" (no +, no spaces)

# --- Storage ---
# Local JSON file for now. Swap for Supabase later without touching the rest of the app
# as long as the same functions (get_progress / save_progress) are used.
PROGRESS_FILE = os.environ.get("PROGRESS_FILE", "progress.json")
