"""
Web API routes — mounted onto the existing Flask app in app.py.
These serve the HTML/JS frontend, completely separate from the WhatsApp webhook.

All endpoints return JSON. Auth is via Bearer token in the Authorization header.
"""

import os
import uuid
import base64

from flask import Blueprint, request, jsonify, send_file

import auth
import storage
import speech
from tutor_brain import build_system_prompt, call_claude
from roadmap import get_next_tier

api = Blueprint("api", __name__, url_prefix="/api")

TMP_DIR = "tmp_audio"
os.makedirs(TMP_DIR, exist_ok=True)
AUDIO_DIR = "web_audio"
os.makedirs(AUDIO_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _get_current_user():
    """Extracts and verifies the Bearer token from the request. Returns payload or None."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    token = header[7:]
    return auth.verify_token(token)


def _require_auth():
    """Returns (user_payload, None) or (None, error_response)."""
    user = _get_current_user()
    if not user:
        return None, (jsonify({"error": "Unauthorized — please log in."}), 401)
    return user, None


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Chat endpoint — the core of the web app
# ---------------------------------------------------------------------------

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

    # Use email as the unique key for progress (consistent with multi-user storage)
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

    # Apply any command/state changes
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

    # Generate audio if requested — return as base64 data URI (avoids disk persistence issues)
    audio_data = None
    if audio_phrase:
        try:
            ogg_path = speech.text_to_speech_ogg(audio_phrase)
            with open(ogg_path, "rb") as f:
                audio_bytes = f.read()
            audio_data = "data:audio/ogg;base64," + base64.b64encode(audio_bytes).decode()
            speech.cleanup_file(ogg_path)
        except Exception as e:
            print(f"TTS error in web chat: {e}")

    # Update conversation history and persist
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


# ---------------------------------------------------------------------------
# Audio file serving
# ---------------------------------------------------------------------------

@api.route("/audio/<filename>", methods=["GET"])
def serve_audio(filename):
    """Serves generated voice note files to the frontend."""
    # Basic security: only allow simple filenames, no path traversal
    if "/" in filename or ".." in filename:
        return jsonify({"error": "Invalid filename."}), 400
    path = os.path.join(AUDIO_DIR, filename)
    if not os.path.exists(path):
        return jsonify({"error": "Audio file not found."}), 404
    return send_file(path, mimetype="audio/ogg")


# ---------------------------------------------------------------------------
# Progress endpoint
# ---------------------------------------------------------------------------

@api.route("/progress", methods=["GET"])
def get_progress_api():
    user, err = _require_auth()
    if err:
        return err

    user_id = user["email"]
    progress = storage.get_progress(user_id)

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
    """Counts consecutive days with at least one mastery signal."""
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
