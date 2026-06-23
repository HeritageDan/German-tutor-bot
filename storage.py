"""
Progress storage — currently a local JSON file.

This is intentionally isolated into two functions (get_progress, save_progress)
so that later, switching to Supabase only means rewriting THIS file —
nothing else in the app needs to change.
"""

import json
import os
from datetime import date

from config import PROGRESS_FILE

DEFAULT_PROGRESS = {
    "current_tier": "A1.1",
    "tier_started_at": str(date.today()),
    "sessions_on_current_tier": 0,
    "mastery_signals": [],
    "vocab_introduced": [],
    "mistake_log": [],
    "topic_override": None,
    "preferred_response_mode": "text",  # "text" or "voice"
    "conversation_history": []  # last N exchanges, for short-term context
}


def get_progress() -> dict:
    """Load progress from disk, creating a fresh record if none exists yet."""
    if not os.path.exists(PROGRESS_FILE):
        save_progress(DEFAULT_PROGRESS)
        return DEFAULT_PROGRESS.copy()

    with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_progress(progress: dict) -> None:
    """Persist progress back to disk."""
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def append_history(progress: dict, role: str, content: str, max_turns: int = 12) -> dict:
    """Keep a rolling window of recent conversation turns for short-term context."""
    progress["conversation_history"].append({"role": role, "content": content})
    progress["conversation_history"] = progress["conversation_history"][-max_turns:]
    return progress


def log_mistake(progress: dict, mistake: str) -> dict:
    progress["mistake_log"].append({"date": str(date.today()), "mistake": mistake})
    return progress


def record_mastery_signal(progress: dict, signal: str) -> dict:
    progress["mastery_signals"].append({"date": str(date.today()), "note": signal})
    progress["sessions_on_current_tier"] += 1
    return progress
