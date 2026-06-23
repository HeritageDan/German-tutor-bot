"""
Main Flask app — the webhook listener.

Two responsibilities:
1. GET /webhook  - Meta's verification handshake when you first connect the webhook
2. POST /webhook - receives every inbound WhatsApp message (text or voice) from you,
                    runs it through Claude, sends back a response (text or voice)

Morning/evening SCHEDULED lessons are NOT triggered from here — those come from
GitHub Actions calling the /send-lesson endpoint below on a cron schedule.
"""

import os
import uuid

from flask import Flask, request, jsonify

import config
import storage
import whatsapp_client
import speech
from tutor_brain import build_system_prompt, call_claude
from roadmap import get_next_tier

app = Flask(__name__)

TMP_DIR = "tmp_audio"
os.makedirs(TMP_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# TEMPORARY DEBUG ROUTE — remove once webhook verification is confirmed working
# ---------------------------------------------------------------------------
@app.route("/debug-token", methods=["GET"])
def debug_token():
    value = config.META_VERIFY_TOKEN
    return {
        "value": value,
        "length": len(value) if value else 0,
        "is_none": value is None
    }, 200


# ---------------------------------------------------------------------------
# Webhook verification (Meta calls this once when you first set up the webhook URL)
# ---------------------------------------------------------------------------
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == config.META_VERIFY_TOKEN:
        return challenge, 200
    return "Verification failed", 403


# ---------------------------------------------------------------------------
# Inbound messages (every reply you send, text or voice)
# ---------------------------------------------------------------------------
@app.route("/webhook", methods=["POST"])
def receive_message():
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"status": "ignored"}), 200

    parsed = whatsapp_client.parse_inbound_message(payload)
    if parsed is None:
        return jsonify({"status": "ignored"}), 200  # status callback, not a real message

    from_number = parsed["from"]

    # Only respond to your own number — ignore everything else
    if config.YOUR_WHATSAPP_NUMBER and from_number != config.YOUR_WHATSAPP_NUMBER:
        return jsonify({"status": "ignored - unknown sender"}), 200

    user_text = None

    if parsed["type"] == "text":
        user_text = parsed["text"]

    elif parsed["type"] == "audio":
        local_path = os.path.join(TMP_DIR, f"{uuid.uuid4()}.ogg")
        try:
            media_url = whatsapp_client.get_media_url(parsed["media_id"])
            whatsapp_client.download_media(media_url, local_path)
            user_text = speech.speech_to_text_from_file(local_path)
            if not user_text:
                whatsapp_client.send_text(
                    from_number,
                    "Ich konnte das nicht verstehen — kannst du das nochmal sagen? "
                    "(Couldn't quite make that out, try again?)"
                )
                return jsonify({"status": "stt_no_match"}), 200
        finally:
            speech.cleanup_file(local_path)
    else:
        whatsapp_client.send_text(from_number, "I can only handle text or voice notes right now!")
        return jsonify({"status": "unsupported_type"}), 200

    handle_conversation_turn(from_number, user_text, session_type="reply")
    return jsonify({"status": "ok"}), 200


# ---------------------------------------------------------------------------
# Scheduled lessons (called by GitHub Actions cron — see github_actions/ folder)
# ---------------------------------------------------------------------------
@app.route("/send-lesson", methods=["POST"])
def send_lesson():
    """
    Expects JSON body: {"session_type": "morning"} or {"session_type": "evening"}
    """
    shared_secret = os.environ.get("WEBHOOK_SHARED_SECRET")
    if shared_secret and request.headers.get("X-Webhook-Secret") != shared_secret:
        return jsonify({"error": "unauthorized"}), 401

    body = request.get_json(silent=True) or {}
    session_type = body.get("session_type", "morning")

    if session_type not in ("morning", "evening"):
        return jsonify({"error": "session_type must be 'morning' or 'evening'"}), 400

    handle_conversation_turn(
        config.YOUR_WHATSAPP_NUMBER,
        user_message="(scheduled lesson trigger - no user message)",
        session_type=session_type,
        is_scheduled_push=True,
    )
    return jsonify({"status": "lesson_sent"}), 200


# ---------------------------------------------------------------------------
# Core orchestration logic — shared by both inbound replies and scheduled lessons
# ---------------------------------------------------------------------------
def handle_conversation_turn(to_number: str, user_message: str, session_type: str,
                              is_scheduled_push: bool = False) -> None:
    progress = storage.get_progress()

    system_prompt = build_system_prompt(progress, session_type)

    claude_response = call_claude(
        system_prompt=system_prompt,
        user_message=user_message,
        conversation_history=progress["conversation_history"],
    )

    reply_text = claude_response.get("reply_text", "...")
    respond_with_voice = claude_response.get("respond_with_voice", False)
    audio_phrase = claude_response.get("audio_phrase")
    topic_override_change = claude_response.get("topic_override_change")
    mode_change = claude_response.get("preferred_response_mode_change")
    mistake = claude_response.get("mistake_detected")
    progress_note = claude_response.get("tier_progress_note")

    # Apply any in-conversation commands the learner issued
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

    # Decide final response mode: explicit per-message flag wins, else the standing preference
    should_send_voice = respond_with_voice or progress["preferred_response_mode"] == "voice"

    # Always send the text first (so you have it in writing too)
    whatsapp_client.send_text(to_number, reply_text)

    # Send a voice note if flagged, using either the tutor's chosen phrase or the full reply
    phrase_to_voice = audio_phrase if audio_phrase else (reply_text if should_send_voice else None)
    if phrase_to_voice:
        audio_path = None
        try:
            audio_path = speech.text_to_speech_ogg(phrase_to_voice)
            whatsapp_client.send_audio(to_number, audio_path)
        finally:
            speech.cleanup_file(audio_path)

    # Update rolling conversation history and persist everything
    storage.append_history(progress, "user", user_message)
    storage.append_history(progress, "assistant", reply_text)
    storage.save_progress(progress)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
