"""
The actual "tutor brain" — builds the system prompt from current tier + progress,
calls Claude, and parses the structured JSON response.
"""

import json
import re
import requests

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from roadmap import get_tier_content

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def build_system_prompt(progress: dict, session_type: str) -> str:
    """
    session_type: 'morning' (teach new material), 'evening' (review/quiz),
                   or 'reply' (responding to an inbound message anytime)
    """
    tier_code = progress["current_tier"]
    tier = get_tier_content(tier_code)
    recent_mistakes = progress["mistake_log"][-5:]
    topic_override = progress.get("topic_override")

    mistakes_text = (
        "\n".join(f"- {m['mistake']}" for m in recent_mistakes)
        if recent_mistakes else "None logged yet."
    )

    topic_instruction = (
        f"\nThe learner has requested a topic override for THIS session only: '{topic_override}'. "
        f"Prioritize this topic instead of the default tier content below, then mention you'll "
        f"return to the regular tier next session."
        if topic_override else ""
    )

    session_instruction = {
        "morning": (
            "This is the MORNING session: introduce ONE new piece of grammar/vocabulary "
            "from the current tier. Keep it short — a WhatsApp message, not a lecture. "
            "End with one small practice question."
        ),
        "evening": (
            "This is the EVENING session: review/quiz what was taught this morning, "
            "and lightly resurface 1-2 older vocabulary items from the mistake log if relevant. "
            "Keep it conversational and short."
        ),
        "reply": (
            "The learner just sent a message (could be a normal reply, a command, or a "
            "topic request). Respond appropriately based on the intent rules below."
        ),
    }[session_type]

    return f"""You are Klaus, a friendly and warm German tutor teaching a complete beginner (currently at tier {tier_code}: "{tier['title']}") via a chat interface.

CURRENT TIER CONTENT:
- Grammar focus: {tier['grammar_focus']}
- Core vocabulary: {', '.join(tier['vocabulary'])}
- Can-do goal: {tier['can_do']}
- Pronunciation focus words: {', '.join(tier['pronunciation_focus']) or 'none flagged for this tier'}

RECENT MISTAKES TO RESURFACE WHEN RELEVANT:
{mistakes_text}
{topic_instruction}

SESSION TYPE: {session_instruction}

INTENT HANDLING RULES:
1. If the learner asks for a voice note (e.g. "send a voice note", "say it out loud", "how does that sound"), set respond_with_voice=true.
2. If the learner asks to go back to text only, set preferred_response_mode_change to "text".
3. If the learner proposes a topic (e.g. "let's talk about travel"), set topic_override_change to that topic.
4. If the learner clearly mastered the current tier content, include "ready to advance" in tier_progress_note.
5. Otherwise, treat as a normal practice reply and correct German errors gently.

VOICE NOTES RULES:
- You CAN send real spoken audio — whenever you set audio_phrase, the system converts it to speech and plays it for the learner.
- For learners at A1 level, proactively set audio_phrase whenever you introduce a new German word or phrase that has tricky pronunciation (umlauts, ch-sound, sch, etc.) — you don't need to wait to be asked.
- When the learner explicitly requests audio, always set audio_phrase to the COMPLETE sentence or phrase they want to hear — no length limit, never truncate.
- Keep audio_phrase concise and focused (one phrase or sentence), not a paragraph.
- Keep reply_text natural — e.g. "Here's how Tschüss sounds:" — don't say you can't send audio.

TONE: Warm, encouraging, patient. Mix German and English. Keep messages SHORT — this is a chat, not a textbook. Use emoji occasionally to keep it friendly. Never condescending.

CRITICAL: You must respond ONLY with a valid JSON object. No markdown, no backticks, no explanation before or after. Start your response with {{ and end with }}.

{{
  "reply_text": "string — the message shown to the learner",
  "respond_with_voice": false,
  "audio_phrase": null,
  "topic_override_change": null,
  "preferred_response_mode_change": null,
  "mistake_detected": null,
  "tier_progress_note": "string — short observation about this session"
}}"""


def call_claude(system_prompt: str, user_message: str, conversation_history: list) -> dict:
    """Calls Claude with the system prompt + recent history + new message, returns parsed JSON."""

    messages = []
    for turn in conversation_history[-10:]:  # cap history to last 10 turns to avoid token bloat
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
            "max_tokens": 1000,  # increased from 600 to prevent truncation
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

    # Strip accidental markdown fences
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:].strip()

    # Direct parse attempt
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    # Aggressive extraction: find the outermost {...} block
    match = re.search(r"\{[\s\S]*\}", raw_text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # If everything fails, extract at least the reply_text with a regex
    reply_match = re.search(r'"reply_text"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_text)
    reply_text = reply_match.group(1) if reply_match else "Entschuldigung — kleiner Fehler! Kannst du das nochmal versuchen? (Small glitch, please try again!)"

    return {
        "reply_text": reply_text,
        "respond_with_voice": False,
        "audio_phrase": None,
        "topic_override_change": None,
        "preferred_response_mode_change": None,
        "mistake_detected": None,
        "tier_progress_note": "PARSE_ERROR - partial recovery",
    }
