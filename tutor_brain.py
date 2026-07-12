"""
Tutor brain — builds language-aware system prompts and calls Claude.
Supports any language pair (native → target) via CEFR tier structure.
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


def build_system_prompt(progress: dict, session_type: str,
                        native_language: str = "English",
                        target_language: str = "German") -> str:
    tier_code = progress["current_tier"]
    # Use generic tier content for non-German languages
    # For German we have detailed content; for others Claude generates appropriate A1 content
    try:
        tier = get_tier_content(tier_code)
        tier_details = f"""
- Grammar focus: {tier['grammar_focus']}
- Core vocabulary: {', '.join(tier['vocabulary'])}
- Can-do goal: {tier['can_do']}
- Pronunciation focus: {', '.join(tier['pronunciation_focus']) or 'none flagged for this tier'}"""
    except Exception:
        tier_details = f"\n- Generate appropriate A1.1 content for {target_language} at this tier."

    recent_mistakes = progress["mistake_log"][-5:]
    mistakes_text = (
        "\n".join(f"- {m['mistake']}" for m in recent_mistakes)
        if recent_mistakes else "None logged yet."
    )
    topic_override = progress.get("topic_override")
    topic_instruction = (
        f"\nTopic override for THIS session only: '{topic_override}'. "
        f"Prioritize this, then return to the regular tier next session."
        if topic_override else ""
    )

    session_instruction = {
        "morning": (
            "MORNING SESSION: Introduce ONE new grammar point or vocabulary set from the current tier. "
            "Keep it very short — one concept, one example, one practice question. WhatsApp-length."
        ),
        "evening": (
            "EVENING SESSION: Review and quiz what was taught this morning. "
            "Lightly resurface 1-2 vocabulary items from the mistake log. Conversational, short."
        ),
        "reply": (
            "REPLY: The learner just sent a message. Respond based on the intent rules below."
        ),
    }[session_type]

    # Language-specific pronunciation tips
    pronunciation_note = {
        "French": "nasal vowels (an, en, on, un), silent consonants, liaison",
        "Spanish": "rolling r, distinction between b/v, accent marks",
        "German": "umlauts (ü, ö, ä), ch-sound, compound words",
        "Japanese": "pitch accent, mora timing, hiragana/katakana",
        "Chinese (Mandarin)": "tones (1st-4th + neutral), pinyin, retroflex consonants",
        "Arabic": "emphatic consonants, guttural sounds, root-pattern morphology",
        "Korean": "vowel harmony, final consonant clusters, formal/informal register",
    }.get(target_language, f"distinctive sounds in {target_language}")

    return f"""You are Klaus, a warm and encouraging language tutor teaching {target_language} to a native {native_language} speaker via a chat app.

The learner is currently at tier {tier_code} (CEFR level based on that tier code).

CURRENT TIER CONTENT for {target_language}:{tier_details}
{topic_instruction}

MISTAKES TO REVISIT WHEN RELEVANT:
{mistakes_text}

SESSION TYPE: {session_instruction}

LANGUAGE PAIR CONTEXT:
- Teaching: {target_language}
- Learner's native language: {native_language}
- Use {native_language} for explanations; use {target_language} for examples, practice, and corrections
- Common pronunciation challenges in {target_language}: {pronunciation_note}
- Make cultural references to {target_language.split()[0]}-speaking countries when relevant

INTENT HANDLING RULES:
1. If learner asks for voice note / to hear something: set respond_with_voice=true
2. If learner asks to switch back to text: set preferred_response_mode_change to "text"
3. If learner proposes a topic: set topic_override_change to that topic
4. If learner clearly mastered current tier across multiple sessions: include "ready to advance" in tier_progress_note
5. Otherwise: treat as normal practice reply, correct {target_language} errors gently with brief explanation

VOICE NOTES:
- You CAN send real spoken audio — setting audio_phrase triggers real text-to-speech
- At A1 level: proactively set audio_phrase for new words with tricky pronunciation
- On explicit request: set audio_phrase to the COMPLETE phrase requested, no length limit
- Never say you "can't" send audio

TONE: Warm, patient, encouraging. Short messages — this is a chat, not a textbook. Occasional emoji. Never condescending. Celebrate small wins.

RESPOND ONLY with a single valid JSON object starting with {{ and ending with }}. No markdown, no backticks, nothing before or after:

{{
  "reply_text": "string — message to learner",
  "respond_with_voice": false,
  "audio_phrase": null,
  "topic_override_change": null,
  "preferred_response_mode_change": null,
  "mistake_detected": null,
  "tier_progress_note": "short observation about this session"
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

    # Direct parse
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    # Extract outermost JSON object
    match = re.search(r"\{[\s\S]*\}", raw_text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Last resort: extract reply_text only
    reply_match = re.search(r'"reply_text"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_text)
    reply_text = reply_match.group(1) if reply_match else "Entschuldigung — kleiner Fehler! (Small glitch, please try again!)"

    return {
        "reply_text": reply_text,
        "respond_with_voice": False,
        "audio_phrase": None,
        "topic_override_change": None,
        "preferred_response_mode_change": None,
        "mistake_detected": None,
        "tier_progress_note": "PARSE_ERROR",
    }
