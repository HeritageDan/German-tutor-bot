"""
Tutor brain — language-aware system prompts and Claude API calls.
"""

import json
import re
import requests

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from roadmap import get_tier_content

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

SUPPORTED_LANGUAGES = [
    "French", "Spanish", "German", "Italian", "Portuguese", "Dutch",
    "Japanese", "Chinese (Mandarin)", "Korean", "Arabic", "Russian",
    "Swedish", "Norwegian", "Polish", "Turkish", "Hindi",
]

PRONUNCIATION_TIPS = {
    "French": "nasal vowels (an/en/on), silent final consonants, liaison",
    "Spanish": "rolling r, b vs v, written accent marks",
    "German": "umlauts (ü/ö/ä), ch-sound (ich vs ach), compound nouns",
    "Japanese": "pitch accent, mora timing, long vowels",
    "Chinese (Mandarin)": "4 tones + neutral tone, retroflex consonants",
    "Arabic": "emphatic consonants, guttural sounds, long vowels",
    "Korean": "vowel harmony, tense vs lax consonants, formal register",
    "Italian": "double consonants, rolling r, open vs closed vowels",
    "Portuguese": "nasal vowels, ão ending",
    "Russian": "soft vs hard consonants, vowel reduction",
}


def build_system_prompt(progress: dict, session_type: str,
                        native_language: str = "English",
                        target_language: str = "German") -> str:
    tier_code = progress["current_tier"]
    try:
        tier = get_tier_content(tier_code)
        tier_details = (
            f"\n- Grammar focus: {tier['grammar_focus']}"
            f"\n- Core vocabulary: {', '.join(tier['vocabulary'])}"
            f"\n- Can-do goal: {tier['can_do']}"
        )
    except Exception:
        tier_details = f"\n- Generate appropriate beginner content for {target_language}."

    recent_mistakes = progress["mistake_log"][-5:]
    mistakes_text = (
        "\n".join(f"- {m['mistake']}" for m in recent_mistakes)
        if recent_mistakes else "None yet."
    )
    topic_override = progress.get("topic_override")
    topic_note = (
        f"\nTOPIC OVERRIDE (this session only): '{topic_override}'. "
        "Focus on this topic. Reset topic_override_change to null after this session."
        if topic_override else ""
    )

    history = progress.get("conversation_history", [])
    is_fresh_conversation = len(history) == 0

    if is_fresh_conversation:
        continuity_note = "This is the START of a new conversation. You may introduce yourself briefly."
    else:
        continuity_note = (
            f"This is a CONTINUING conversation ({len(history)//2} exchanges so far). "
            "DO NOT re-introduce yourself. DO NOT say 'Great to meet you' or 'Welcome'. "
            "Continue naturally from where you left off, as if mid-conversation."
        )

    session_instruction = {
        "morning": "MORNING LESSON: Introduce ONE new grammar point or vocabulary item from the current tier. Short message, one practice question at the end. Do not re-introduce yourself if conversation history exists.",
        "evening": "EVENING REVIEW: Quiz the learner on today's material. Lightly resurface 1-2 past mistakes. Conversational, short.",
        "interactive": "FREE PRACTICE: Respond naturally to whatever the learner says. Focus on fluency and real conversation.",
        "reply": "REPLY: Respond directly to the learner's message. Stay focused — do not restart the conversation or re-introduce yourself.",
    }.get(session_type, "REPLY: Respond naturally.")

    pron_tip = PRONUNCIATION_TIPS.get(target_language, f"distinctive sounds in {target_language}")

    return f"""You are Klaus, a warm language tutor teaching {target_language} to a native {native_language} speaker via a chat app.

TIER: {tier_code}{tier_details}
{topic_note}

CONVERSATION STATE: {continuity_note}

RECENT MISTAKES TO REVISIT WHEN RELEVANT:
{mistakes_text}

SESSION: {session_instruction}

LANGUAGE RULES:
- Explain grammar and correct mistakes in {native_language}
- Use {target_language} for examples, drills, and practice sentences
- Use **bold** (double asterisks) to highlight key {target_language} words or phrases
- Keep messages SHORT — this is a chat app, not a textbook
- Warm and encouraging tone; celebrate effort
- Pronunciation challenges in {target_language}: {pron_tip}

VOICE NOTE RULES (CRITICAL — read carefully):
- audio_phrase: ONLY set this when the learner EXPLICITLY asks for a voice note IN THIS SPECIFIC MESSAGE (e.g. "send a voice note", "say that out loud", "how does X sound")
- If the learner does NOT ask for audio, set audio_phrase to null — even if you're introducing a new word
- audio_phrase_english: a short English translation or hint shown under the voice card (only set when audio_phrase is set)
- respond_with_voice: set to true ONLY when the learner explicitly requests audio this turn
- preferred_response_mode_change: ONLY set this if the learner says something like "always send voice from now on" or "switch to text only" — NOT for a single one-time voice request
- NEVER proactively send audio without being asked

XP: award_xp between 5–25 based on learner engagement (5=minimal, 15=good attempt, 25=excellent)

VOCAB TRACKING:
- new_vocab: array of NEW {target_language} words/phrases you introduce this turn (strings, max 4)
- mistakes_detected: array of objects for errors — format: {{"word": "what they said", "correction": "correct form"}}

RESPOND WITH A SINGLE VALID JSON OBJECT ONLY. Start with {{ end with }}. No markdown, no text before or after:

{{
  "reply_text": "your message — use **bold** for key words, use actual newlines (not \\\\n)",
  "respond_with_voice": false,
  "audio_phrase": null,
  "audio_phrase_english": null,
  "new_vocab": [],
  "mistakes_detected": [],
  "topic_override_change": null,
  "preferred_response_mode_change": null,
  "tier_progress_note": "short observation about this turn",
  "tier_advancement_note": null,
  "award_xp": 10
}}"""


def call_claude(system_prompt: str, user_message: str, conversation_history: list) -> dict:
    messages = []
    for turn in conversation_history[-10:]:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": user_message})

    response = requests.post(
        ANTHROPIC_URL,
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": CLAUDE_MODEL,
            "max_tokens": 1000,
            "system": system_prompt,
            "messages": messages,
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    raw_text = "".join(
        block["text"] for block in data["content"] if block["type"] == "text"
    ).strip()

    # Strip markdown fences
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:].strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", raw_text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    reply_match = re.search(r'"reply_text"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_text)
    reply_text = reply_match.group(1) if reply_match else "Entschuldigung — kleiner Fehler! Please try again."

    return {
        "reply_text": reply_text,
        "respond_with_voice": False,
        "audio_phrase": None,
        "audio_phrase_english": None,
        "new_vocab": [],
        "mistakes_detected": [],
        "topic_override_change": None,
        "preferred_response_mode_change": None,
        "tier_progress_note": "PARSE_ERROR",
        "tier_advancement_note": None,
        "award_xp": 5,
    }
