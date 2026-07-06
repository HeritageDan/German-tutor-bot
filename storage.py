"""
Progress storage — per-user JSON files, one per phone number.
Swap to Supabase later by only rewriting get_progress() and save_progress().
"""

import json
import os
from datetime import date

PROGRESS_DIR = os.environ.get("PROGRESS_DIR", "user_progress")
os.makedirs(PROGRESS_DIR, exist_ok=True)

DEFAULT_PROGRESS = {
    "current_tier": "A1.1",
    "tier_started_at": None,
    "sessions_on_current_tier": 0,
    "mastery_signals": [],
    "vocab_introduced": [],
    "mistake_log": [],
    "topic_override": None,
    "preferred_response_mode": "text",
    "conversation_history": []
}


def _progress_path(phone_number: str) -> str:
    safe = phone_number.replace("+", "").replace(" ", "")
    return os.path.join(PROGRESS_DIR, f"progress_{safe}.json")


def get_progress(phone_number: str) -> dict:
    path = _progress_path(phone_number)
    if not os.path.exists(path):
        fresh = DEFAULT_PROGRESS.copy()
        fresh["tier_started_at"] = str(date.today())
        save_progress(phone_number, fresh)
        return fresh
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_progress(phone_number: str, progress: dict) -> None:
    with open(_progress_path(phone_number), "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def append_history(progress: dict, role: str, content: str, max_turns: int = 12) -> dict:
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
