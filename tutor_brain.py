"""
Tutor brain — builds language-aware system prompts and calls Claude.
Returns enriched JSON: vocab pills, mistake pills, voice card data, XP.
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
    "Chinese (Mandarin)": "4 tones + neutral tone, retroflex consonants (zh/ch/sh/r)",
    "Arabic": "emphatic consonants, guttural sounds (ح/خ/ع/غ), long vowels",
    "Korean": "vowel harmony, tense vs lax consonants, formal register",
    "Italian": "double consonants, rolling r, open vs closed vowels",
    "Portuguese": "nasal vowels, ão ending, European vs Brazilian differences",
    "Russian": "soft vs hard consonants, vowel reduction in unstressed syllables",
}


def build_system_prompt(progress: dict, session_type: str,
                        native_language: str = "English",
                        target_language: str = "German") -> str:
    tier_code = progress["current_tier"]
    try:
        tier = get_tier_content(tier_code)
        tier_details = f"""
- Grammar focus: {tier['grammar_focus']}
- Core vocabulary: {', '.join(tier['vocabulary'])}
- Can-do goal: {tier['can_do']}
- Pronunciation focus: {', '.join(tier['pronunciation_focus']) or 'none'}"""
    except Exception:
        tier_details = f"\n- Generate appropriate beginner content for {target_language} at this CEFR level."

    recent_mistakes = progress["mistake_log"][-5:]
    mistakes_text = (
        "\n".join(f"- {m['mistake']}" for m in recent_mistakes)
        if recent_mistakes else "None yet."
    )
    topic_override = progress.get("topic_override")
    topic_note = (
        f"\nTopic override for THIS session: '{topic_override}'. "
        f"Focus on this, then return to normal tier next session."
        if topic_override else ""
    )

    session_instruction = {
        "morning": "MORNING LESSON: Introduce ONE new grammar point or vocabulary set. Short, focused, one practice question at the end.",
        "evening": "EVENING REVIEW: Quiz/review this morning's material. Resurface 1-2 items from the mistake log. Keep it light and conversational.",
        "interactive": "FREE PRACTICE: Respond naturally to whatever the learner says. Prioritise fluency and conversation over strict grammar drilling.",
        "reply": "REPLY: Respond to the learner's message based on context and intent rules.",
    }.get(session_type, "REPLY: Respond naturally.")

    pron_tip = PRONUNCIATION_TIPS.get(target_language, f"distinctive sounds in {target_language}")

    return f"""You are Klaus, a warm and encouraging language tutor teaching {target_language} to a native {native_language} speaker in a real-time chat app.

CURRENT TIER: {tier_code}{tier_details}
{topic_note}

RECENT MISTAKES TO REVISIT:
{mistakes_text}

SESSION: {session_instruction}

CONTEXT:
- Native language: {native_language} (use this for explanations)
- Target language: {target_language} (use this for examples, corrections, practice)
- Pronunciation challenge areas: {pron_tip}
- Keep messages SHORT — this is a chat interface, not a textbook
- Use **bold** (double asterisks) for key {target_language} words or phrases you want to highlight
- Warm, encouraging tone. Celebrate small wins. Never condescending.

INTENT RULES:
1. Voice note request ("say it out loud", "send audio", "how does X sound"): set respond_with_voice=true, set audio_phrase
2. Switch to text: set preferred_response_mode_change="text"
3. Topic request ("let's do travel vocab"): set topic_override_change to that topic
4. Tier mastery detected: include "ready to advance" in tier_progress_note
5. Otherwise: normal teaching/correction reply

VOICE NOTE RULES:
- respond_with_voice=true → system sends REAL spoken audio via ElevenLabs TTS
- audio_phrase: the EXACT phrase to speak aloud (no length limit when requested)
- audio_phrase_english: English translation or hint for what the phrase means (show under the voice card)
- At A1/A2 level: proactively set audio_phrase for new words with tricky pronunciation (don't wait to be asked)
- Never claim you can't send audio — you genuinely can

VOCAB & MISTAKE TRACKING:
- new_vocab: array of NEW {target_language} words/phrases you introduce this turn (strings only, 0-4 items)
- mistakes_detected: array of objects for any {native_language}-influenced or grammatical errors the learner made, format: {{"word": "what they said", "correction": "correct form"}}

XP AWARD:
- award_xp: integer 5-25 based on learner engagement this turn (5 = minimal, 15 = good attempt, 25 = excellent)

RESPOND ONLY with a single valid JSON object. Start with {{ and end with }}. Nothing else:

{{
  "reply_text": "string — your message to the learner, use **bold** for key words",
  "respond_with_voice": false,
  "audio_phrase": null,
  "audio_phrase_english": null,
  "new_vocab": [],
  "mistakes_detected": [],
  "topic_override_change": null,
  "preferred_response_mode_change": null,
  "tier_progress_note": "short observation",
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
