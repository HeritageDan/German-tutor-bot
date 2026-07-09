"""
Web API routes for the HTML/JS frontend.
All endpoints return JSON. Auth via Bearer token in Authorization header.
"""

import base64
import os
import uuid

from flask import Blueprint, request, jsonify

import auth
import storage
import speech
from tutor_brain import build_system_prompt, call_claude
from roadmap import get_next_tier

api = Blueprint("api", __name__, url_prefix="/api")

TMP_DIR = "tmp_audio"
os.makedirs(TMP_DIR, exist_ok=True)


# ── Auth helpers ────────────────────────────────────────────────────────────

def _require_auth():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None, (jsonify({"error": "Unauthorized — please log in."}), 401)
    user = auth.verify_token(header[7:])
    if not user:
        return None, (jsonify({"error": "Session expired — please log in again."}), 401)
    return user, None


# ── Auth endpoints ───────────────────────────────────────────────────────────

@api.route("/signup", methods=["POST"])
def signup():
    body = request.get_json(silent=True) or {}
    email = body.get("email", "").strip()
    password = body.get("password", "")
    display_name = body.get("display_name", "").strip() or email.split("@")[0]
    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400
    result = auth.signup(email, password, display_name)
    if not result["ok"]:
        return jsonify({"error": result["error"]}), 409
    return jsonify({"token": result["token"], "user": result["user"]}), 201


@api.route("/login", methods=["POST"])
def login():
    body = request.get_json(silent=True) or {}
    email = body.get("email", "").strip()
    password = body.get("password", "")
    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400
    result = auth.login(email, password)
    if not result["ok"]:
        return jsonify({"error": result["error"]}), 401
    return jsonify({"token": result["token"], "user": result["user"]}), 200


# ── Chat endpoint ────────────────────────────────────────────────────────────

@api.route("/chat", methods=["POST"])
def chat():
    user, err = _require_auth()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    user_message = body.get("message", "").strip()
    session_type = body.get("session_type", "reply")

    if not user_message:
        return jsonify({"error": "Message cannot be empty."}), 400

    user_id = user["email"]
    progress = storage.get_progress(user_id)

    system_prompt = build_system_prompt(progress, session_type)
    claude_response = call_claude(
        system_prompt=system_prompt,
        user_message=user_message,
        conversation_history=progress["conversation_history"],
    )

    reply_text = claude_response.get("reply_text", "...")
    audio_phrase = claude_response.get("audio_phrase")
    topic_override_change = claude_response.get("topic_override_change")
    mode_change = claude_response.get("preferred_response_mode_change")
    mistake = claude_response.get("mistake_detected")
    progress_note = claude_response.get("tier_progress_note")

    if topic_override_change:
        progress["topic_override"] = topic_override_change
    if mode_change in ("text", "voice"):
        progress["preferred_response_mode"] = mode_change
    if mistake:
        storage.log_mistake(progress, mistake)
    if progress_note:
        storage.record_mastery_signal(progress, progress_note)
        if "ready to advance" in progress_note.lower():
            progress["current_tier"] = get_next_tier(progress["current_tier"])
            progress["sessions_on_current_tier"] = 0

    # Use MP3 base64 for web (not OGG — OGG doesn't work in Safari/iOS)
    audio_data = None
    if audio_phrase:
        try:
            audio_data = speech.text_to_speech_mp3_base64(audio_phrase)
        except Exception as e:
            print(f"TTS error in web chat: {e}")

    storage.append_history(progress, "user", user_message)
    storage.append_history(progress, "assistant", reply_text)
    storage.save_progress(user_id, progress)

    return jsonify({
        "reply": reply_text,
        "audio_data": audio_data,
        "current_tier": progress["current_tier"],
        "sessions_on_tier": progress["sessions_on_current_tier"],
        "streak": _calculate_streak(progress),
    }), 200


# ── Voice transcription endpoint (browser mic → Whisper → text) ──────────────

@api.route("/transcribe", methods=["POST"])
def transcribe():
    """
    Receives a base64-encoded audio blob from the browser MediaRecorder,
    transcribes it with Whisper, and returns the text.
    The frontend then sends that text as a normal /api/chat message.
    """
    user, err = _require_auth()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    audio_b64 = body.get("audio_data", "")
    mime_type = body.get("mime_type", "audio/webm")

    if not audio_b64:
        return jsonify({"error": "No audio data provided."}), 400

    # Strip data URI prefix if present (e.g. "data:audio/webm;base64,...")
    if "," in audio_b64:
        audio_b64 = audio_b64.split(",", 1)[1]

    try:
        audio_bytes = base64.b64decode(audio_b64)
    except Exception:
        return jsonify({"error": "Invalid audio data — could not decode base64."}), 400

    try:
        transcript = speech.speech_to_text_from_bytes(audio_bytes, mime_type)
    except Exception as e:
        print(f"STT error: {e}")
        return jsonify({"error": "Could not transcribe audio — please try again."}), 500

    if not transcript.strip():
        return jsonify({"error": "No speech detected — please try again."}), 200

    return jsonify({"transcript": transcript.strip()}), 200


# ── Progress endpoint ────────────────────────────────────────────────────────

@api.route("/progress", methods=["GET"])
def get_progress_api():
    user, err = _require_auth()
    if err:
        return err

    progress = storage.get_progress(user["email"])
    return jsonify({
        "current_tier": progress["current_tier"],
        "sessions_on_current_tier": progress["sessions_on_current_tier"],
        "mastery_signals": len(progress["mastery_signals"]),
        "mistake_count": len(progress["mistake_log"]),
        "recent_mistakes": progress["mistake_log"][-3:],
        "topic_override": progress.get("topic_override"),
        "streak": _calculate_streak(progress),
    }), 200


def _calculate_streak(progress: dict) -> int:
    from datetime import date, timedelta
    if not progress["mastery_signals"]:
        return 0
    dates = sorted(set(s["date"] for s in progress["mastery_signals"]), reverse=True)
    streak = 0
    expected = date.today()
    for d in dates:
        if d == str(expected) or d == str(expected - timedelta(days=1)):
            streak += 1
            expected = date.fromisoformat(d) - timedelta(days=1)
        else:
            break
    return streak
