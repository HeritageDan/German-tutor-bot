"""
Web API routes for the HTML/JS frontend.
Auth via Bearer token in Authorization header.
"""

import base64
import os
from datetime import date, timedelta

from flask import Blueprint, request, jsonify

import auth
import storage
import speech
from tutor_brain import build_system_prompt, call_claude, SUPPORTED_LANGUAGES
from roadmap import get_tier_content, get_next_tier, TIER_ORDER, TIERS

api = Blueprint("api", __name__, url_prefix="/api")
TMP_DIR = "tmp_audio"
os.makedirs(TMP_DIR, exist_ok=True)


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _require_auth():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None, (jsonify({"error": "Unauthorized"}), 401)
    user = auth.verify_token(header[7:])
    if not user:
        return None, (jsonify({"error": "Session expired — please log in again."}), 401)
    return user, None


def _get_languages(user_email: str, token_payload: dict) -> tuple:
    try:
        langs = storage.get_user_languages(user_email)
        return langs.get("native_language", "English"), langs.get("target_language", "German")
    except Exception:
        return token_payload.get("native_language", "English"), token_payload.get("target_language", "German")


def _build_state(progress: dict, native_lang: str, target_lang: str) -> dict:
    tier_code = progress["current_tier"]
    tier_info = TIERS.get(tier_code, {})
    mastery_pct = min(100, progress.get("sessions_on_current_tier", 0) * 12)
    return {
        "current_tier": tier_code,
        "tier_title": tier_info.get("title", tier_code),
        "tier_mastery_score": mastery_pct,
        "streak_days": _calculate_streak(progress),
        "vocab_mastered": len(progress.get("vocab_introduced", [])),
        "total_xp": progress.get("total_xp", 0),
        "session_count": progress.get("session_count", 0),
        "preferred_response_mode": progress.get("preferred_response_mode", "text"),
        "native_language": native_lang,
        "target_language": target_lang,
    }


# ── Auth endpoints ────────────────────────────────────────────────────────────

@api.route("/signup", methods=["POST"])
def signup():
    body = request.get_json(silent=True) or {}
    email = body.get("email", "").strip()
    password = body.get("password", "")
    display_name = body.get("display_name", "").strip() or email.split("@")[0]
    native_language = body.get("native_language", "English")
    target_language = body.get("target_language", "German")
    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400
    result = auth.signup(email, password, display_name, native_language, target_language)
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


# ── State endpoint ────────────────────────────────────────────────────────────

@api.route("/state", methods=["GET"])
def get_state():
    user, err = _require_auth()
    if err:
        return err
    progress = storage.get_progress(user["email"])
    native_lang, target_lang = _get_languages(user["email"], user)
    return jsonify(_build_state(progress, native_lang, target_lang)), 200


# ── Language management ───────────────────────────────────────────────────────

@api.route("/languages", methods=["GET"])
def get_languages():
    return jsonify({"languages": SUPPORTED_LANGUAGES}), 200


@api.route("/set-languages", methods=["POST"])
def set_languages():
    user, err = _require_auth()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    native = body.get("native_language", "English")
    target = body.get("target_language", "German")
    if target not in SUPPORTED_LANGUAGES:
        return jsonify({"error": f"Unsupported language: {target}"}), 400
    storage.set_user_languages(user["email"], native, target)
    return jsonify({"ok": True}), 200


# ── Session trigger ───────────────────────────────────────────────────────────

@api.route("/start-session", methods=["POST"])
def start_session():
    user, err = _require_auth()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    session_type = body.get("session_type", "morning")
    if session_type not in ("morning", "evening", "interactive"):
        return jsonify({"error": "Invalid session_type"}), 400
    return _process_message(user, "(session start)", session_type)


# ── Chat endpoint ─────────────────────────────────────────────────────────────

@api.route("/chat", methods=["POST"])
def chat():
    user, err = _require_auth()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    user_message = body.get("message", "").strip()
    if not user_message:
        return jsonify({"error": "Message cannot be empty."}), 400
    return _process_message(user, user_message, "reply")


def _process_message(user: dict, user_message: str, session_type: str):
    user_id = user["email"]
    progress = storage.get_progress(user_id)
    native_lang, target_lang = _get_languages(user_id, user)

    system_prompt = build_system_prompt(progress, session_type, native_lang, target_lang)
    cr = call_claude(
        system_prompt=system_prompt,
        user_message=user_message,
        conversation_history=progress["conversation_history"],
    )

    reply_text       = cr.get("reply_text", "...")
    audio_phrase     = cr.get("audio_phrase")          # ONLY set by Claude on explicit request
    audio_phrase_eng = cr.get("audio_phrase_english")
    new_vocab        = cr.get("new_vocab") or []
    mistakes         = cr.get("mistakes_detected") or []
    topic_change     = cr.get("topic_override_change")
    mode_change      = cr.get("preferred_response_mode_change")  # persistent pref only
    progress_note    = cr.get("tier_progress_note", "")
    tier_adv_note    = cr.get("tier_advancement_note")
    award_xp         = cr.get("award_xp", 10)

    # Apply state changes
    if topic_change:
        progress["topic_override"] = topic_change
    # Only change persistent mode on explicit preference change (not one-time voice requests)
    if mode_change in ("text", "voice"):
        progress["preferred_response_mode"] = mode_change
    for m in mistakes:
        if isinstance(m, dict):
            storage.log_mistake(progress, f"{m.get('word','')} → {m.get('correction','')}")
        elif isinstance(m, str):
            storage.log_mistake(progress, m)
    if new_vocab:
        storage.add_vocab(progress, new_vocab)
    if progress_note:
        storage.record_mastery_signal(progress, progress_note)
        if "ready to advance" in progress_note.lower():
            next_tier = get_next_tier(progress["current_tier"])
            if next_tier != progress["current_tier"]:
                progress["current_tier"] = next_tier
                progress["sessions_on_current_tier"] = 0
                tier_info = TIERS.get(next_tier, {})
                tier_adv_note = tier_adv_note or f"You've advanced to {next_tier}: {tier_info.get('title', '')}!"

    storage.add_xp(progress, award_xp)
    storage.increment_session_count(progress)

    # Save history BEFORE audio (so history is always saved even if TTS fails)
    storage.append_history(progress, "user", user_message)
    storage.append_history(progress, "assistant", reply_text)
    storage.save_progress(user_id, progress)

    # TTS audio — ONLY when Claude explicitly set audio_phrase
    # Never auto-generate based on preferred_response_mode for the web app
    audio_data = None
    if audio_phrase:
        try:
            audio_data = speech.text_to_speech_mp3_base64(audio_phrase)
        except Exception as e:
            print(f"[web_api] TTS error: {e}")

    tier_code = progress["current_tier"]
    tier_info = TIERS.get(tier_code, {})

    return jsonify({
        "reply": reply_text,
        "audio_phrase": audio_phrase,
        "audio_phrase_english": audio_phrase_eng,
        "audio_data": audio_data,
        "new_vocab": new_vocab,
        "mistakes_detected": mistakes,
        "tier_advancement_note": tier_adv_note,
        "current_tier": tier_code,
        "tier_title": tier_info.get("title", tier_code),
        "tier_mastery_score": min(100, progress.get("sessions_on_current_tier", 0) * 12),
        "streak_days": _calculate_streak(progress),
        "vocab_mastered": len(progress.get("vocab_introduced", [])),
        "total_xp": progress.get("total_xp", 0),
        "session_count": progress.get("session_count", 0),
        "preferred_response_mode": progress.get("preferred_response_mode", "text"),
    }), 200


# ── Mode endpoint ─────────────────────────────────────────────────────────────

@api.route("/set-mode", methods=["POST"])
def set_mode():
    user, err = _require_auth()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    mode = body.get("mode", "text")
    if mode not in ("text", "voice"):
        return jsonify({"error": "mode must be 'text' or 'voice'"}), 400
    progress = storage.get_progress(user["email"])
    progress["preferred_response_mode"] = mode
    storage.save_progress(user["email"], progress)
    return jsonify({"ok": True}), 200


# ── Roadmap endpoint ──────────────────────────────────────────────────────────

@api.route("/roadmap", methods=["GET"])
def roadmap():
    user, err = _require_auth()
    if err:
        return err
    progress = storage.get_progress(user["email"])
    current = progress["current_tier"]
    current_idx = TIER_ORDER.index(current) if current in TIER_ORDER else 0

    tiers = []
    for i, code in enumerate(TIER_ORDER):
        info = TIERS.get(code, {})
        level = code.split(".")[0]
        tiers.append({
            "code": code,
            "title": info.get("title", code),
            "level": level,
            "vocab_target": max(30, len(info.get("vocabulary", [])) * 8),
            "is_done": i < current_idx,
            "is_current": code == current,
        })
    return jsonify({"current_tier": current, "tiers": tiers}), 200


# ── Voice transcription ───────────────────────────────────────────────────────

@api.route("/transcribe", methods=["POST"])
def transcribe():
    user, err = _require_auth()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    audio_b64 = body.get("audio_data", "")
    mime_type = body.get("mime_type", "audio/webm")
    if not audio_b64:
        return jsonify({"error": "No audio data provided."}), 400
    if "," in audio_b64:
        audio_b64 = audio_b64.split(",", 1)[1]
    try:
        audio_bytes = base64.b64decode(audio_b64)
    except Exception:
        return jsonify({"error": "Invalid audio data."}), 400
    try:
        transcript = speech.speech_to_text_from_bytes(audio_bytes, mime_type)
    except Exception as e:
        print(f"[web_api] STT error: {e}")
        return jsonify({"error": "Could not transcribe audio."}), 500
    if not transcript.strip():
        return jsonify({"error": "No speech detected — please try again."}), 200
    return jsonify({"transcript": transcript.strip()}), 200


# ── Progress (legacy compat) ──────────────────────────────────────────────────

@api.route("/progress", methods=["GET"])
def get_progress_api():
    user, err = _require_auth()
    if err:
        return err
    progress = storage.get_progress(user["email"])
    native_lang, target_lang = _get_languages(user["email"], user)
    state = _build_state(progress, native_lang, target_lang)
    state["recent_mistakes"] = progress["mistake_log"][-3:]
    return jsonify(state), 200


def _calculate_streak(progress: dict) -> int:
    if not progress.get("mastery_signals"):
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
