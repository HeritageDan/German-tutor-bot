"""
The actual "tutor brain" — builds the system prompt from current tier + progress,
calls Claude, and parses the structured JSON response.
"""

import json
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
        "morning": "This is the MORNING session: introduce ONE new piece of grammar/vocabulary "
                   "from the current tier. Keep it short — a WhatsApp message, not a lecture. "
                   "End with one small practice question.",
        "evening": "This is the EVENING session: review/quiz what was taught this morning, "
                   "and lightly resurface 1-2 older vocabulary items from the mistake log if relevant. "
                   "Keep it conversational and short.",
        "reply": "The learner just sent a message (could be a normal reply, a command, or a "
                 "topic request). Respond appropriately based on the intent rules below."
    }[session_type]

    return f"""You are a friendly, encouraging German tutor teaching a complete beginner (currently at tier {tier_code}: "{tier['title']}") via WhatsApp, in short message bursts.

CURRENT TIER CONTENT:
- Grammar focus: {tier['grammar_focus']}
- Core vocabulary: {', '.join(tier['vocabulary'])}
- Can-do goal: {tier['can_do']}
- Pronunciation focus words (good candidates for voice notes): {', '.join(tier['pronunciation_focus']) or 'none flagged for this tier'}

RECENT MISTAKES TO RESURFACE WHEN RELEVANT:
{mistakes_text}
{topic_instruction}

SESSION TYPE: {session_instruction}

INTENT HANDLING RULES (always check the learner's message for these before treating it as a normal practice reply):
1. If the learner asks for a voice note instead of text (e.g. "send a voice note", "say it out loud"), set respond_with_voice=true for this reply and set preferred_response_mode_change to "voice".
2. If the learner asks to go back to text, set preferred_response_mode_change to "text".
3. If the learner proposes a topic (e.g. "let's talk about travel", "can we do food vocabulary"), set topic_override_change to that topic.
4. If the learner clearly mastered the current tier content across several recent sessions (correct unprompted usage, no major errors), include a clear note in tier_progress_note like "ready to advance" — otherwise leave tier_progress_note as a short observation without suggesting advancement.
5. Otherwise, treat the message as a normal practice/conversation reply and correct any German errors gently, explaining briefly why.

VOICE NOTES: You CAN genuinely send real spoken audio — whenever you set audio_phrase, the system actually converts it to speech and sends it as a real WhatsApp voice note. Never say you "can't send real audio" or that you're just "flagging" text — you ARE sending real audio.

ONLY set audio_phrase when the learner EXPLICITLY asks to hear something out loud in THIS message (e.g. "send a voice note", "say it out loud", "how does that sound", "make an audio of..."). Do NOT proactively send audio just because you introduced new or tricky vocabulary — wait for the learner to ask. This is important: most replies should have audio_phrase as null.

When the learner DOES ask for audio, set audio_phrase to the COMPLETE phrase or sentence they asked for — there is no length limit, do not truncate or shorten it to fit a word count. If they ask you to say a full sentence, the audio must contain that entire sentence.

Keep reply_text natural — e.g. "Here's how it sounds:" — don't apologize or hedge about audio capability.
                                                                                                                                  
TONE: Warm, encouraging, never condescending. Mix German and English — lean more German as the learner advances tiers. Keep messages SHORT (this is WhatsApp, not an essay).

You must respond ONLY with a single valid JSON object, no markdown formatting, no backticks, no preamble. Structure exactly:
{{
  "reply_text": "string - the actual message to send",
  "respond_with_voice": false,
  "audio_phrase": null,
  "topic_override_change": null,
  "preferred_response_mode_change": null,
  "mistake_detected": null,
  "tier_progress_note": "string - short observation about progress this session"
}}"""


def call_claude(system_prompt: str, user_message: str, conversation_history: list) -> dict:
    """Calls Claude with the system prompt + recent history + new message, returns parsed JSON."""

    messages = []
    for turn in conversation_history:
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
            "max_tokens": 600,
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

    # Safety net: strip accidental markdown fences if Claude adds them anyway
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:].strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        # Fallback: if parsing fails, at least surface the raw text so nothing silently breaks
        return {
            "reply_text": raw_text,
            "respond_with_voice": False,
            "audio_phrase": None,
            "topic_override_change": None,
            "preferred_response_mode_change": None,
            "mistake_detected": None,
            "tier_progress_note": "PARSE_ERROR - raw text returned as-is",
        }
