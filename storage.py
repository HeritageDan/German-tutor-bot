"""
Persistent storage via Supabase (PostgreSQL).
Falls back to local JSON files if SUPABASE_URL is not set (useful for local dev).

Supabase tables required:
  - users (see README SQL)
  - user_progress (see README SQL)
"""

import json
import os
import requests
from datetime import date

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)

# Fallback: local JSON (dev only)
PROGRESS_DIR = os.environ.get("PROGRESS_DIR", "user_progress")
if not USE_SUPABASE:
    os.makedirs(PROGRESS_DIR, exist_ok=True)

DEFAULT_PROGRESS = {
    "current_tier": "A1.1",
    "tier_started_at": str(date.today()),
    "sessions_on_current_tier": 0,
    "mastery_signals": [],
    "vocab_introduced": [],
    "mistake_log": [],
    "topic_override": None,
    "preferred_response_mode": "text",
    "conversation_history": [],
}


def _sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _sb_url(table: str, filters: str = "") -> str:
    return f"{SUPABASE_URL}/rest/v1/{table}{filters}"


# ── Get progress ────────────────────────────────────────────────────────────

def get_progress(user_email: str) -> dict:
    if not USE_SUPABASE:
        return _json_get_progress(user_email)

    try:
        resp = requests.get(
            _sb_url("user_progress", f"?user_email=eq.{user_email}&limit=1"),
            headers=_sb_headers(), timeout=10
        )
        resp.raise_for_status()
        rows = resp.json()
        if rows:
            row = rows[0]
            return {
                "current_tier": row.get("current_tier", "A1.1"),
                "tier_started_at": row.get("tier_started_at", str(date.today())),
                "sessions_on_current_tier": row.get("sessions_on_current_tier", 0),
                "mastery_signals": row.get("mastery_signals") or [],
                "vocab_introduced": row.get("vocab_introduced") or [],
                "mistake_log": row.get("mistake_log") or [],
                "topic_override": row.get("topic_override"),
                "preferred_response_mode": row.get("preferred_response_mode", "text"),
                "conversation_history": row.get("conversation_history") or [],
            }
        # No row yet — create one
        fresh = DEFAULT_PROGRESS.copy()
        save_progress(user_email, fresh)
        return fresh
    except Exception as e:
        print(f"Supabase get_progress error: {e}")
        return DEFAULT_PROGRESS.copy()


def save_progress(user_email: str, progress: dict) -> None:
    if not USE_SUPABASE:
        return _json_save_progress(user_email, progress)

    data = {
        "user_email": user_email,
        "current_tier": progress.get("current_tier", "A1.1"),
        "tier_started_at": progress.get("tier_started_at", str(date.today())),
        "sessions_on_current_tier": progress.get("sessions_on_current_tier", 0),
        "mastery_signals": progress.get("mastery_signals", []),
        "vocab_introduced": progress.get("vocab_introduced", []),
        "mistake_log": progress.get("mistake_log", []),
        "topic_override": progress.get("topic_override"),
        "preferred_response_mode": progress.get("preferred_response_mode", "text"),
        "conversation_history": progress.get("conversation_history", []),
        "updated_at": "now()",
    }
    try:
        # Upsert (insert or update based on user_email)
        resp = requests.post(
            _sb_url("user_progress"),
            headers={**_sb_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
            json=data, timeout=10
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"Supabase save_progress error: {e}")


# ── History / mistake helpers ───────────────────────────────────────────────

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


# ── User language profile ───────────────────────────────────────────────────

def get_user_languages(user_email: str) -> dict:
    """Returns {native_language, target_language} for a user."""
    if not USE_SUPABASE:
        return {"native_language": "English", "target_language": "German"}
    try:
        resp = requests.get(
            _sb_url("users", f"?email=eq.{user_email}&select=native_language,target_language&limit=1"),
            headers=_sb_headers(), timeout=10
        )
        resp.raise_for_status()
        rows = resp.json()
        if rows:
            return {
                "native_language": rows[0].get("native_language", "English"),
                "target_language": rows[0].get("target_language", "German"),
            }
    except Exception as e:
        print(f"Supabase get_user_languages error: {e}")
    return {"native_language": "English", "target_language": "German"}


def set_user_languages(user_email: str, native_language: str, target_language: str) -> bool:
    """Updates the user's language pair and resets their progress to A1.1."""
    if not USE_SUPABASE:
        return False
    try:
        # Update language in users table
        resp = requests.patch(
            _sb_url("users", f"?email=eq.{user_email}"),
            headers={**_sb_headers(), "Prefer": "return=minimal"},
            json={"native_language": native_language, "target_language": target_language},
            timeout=10
        )
        resp.raise_for_status()
        # Reset progress to A1.1 for new language
        fresh = DEFAULT_PROGRESS.copy()
        save_progress(user_email, fresh)
        return True
    except Exception as e:
        print(f"Supabase set_user_languages error: {e}")
        return False


# ── JSON fallback (local dev) ───────────────────────────────────────────────

def _progress_path(email: str) -> str:
    safe = email.replace("@", "_at_").replace(".", "_")
    return os.path.join(PROGRESS_DIR, f"progress_{safe}.json")


def _json_get_progress(email: str) -> dict:
    path = _progress_path(email)
    if not os.path.exists(path):
        fresh = DEFAULT_PROGRESS.copy()
        _json_save_progress(email, fresh)
        return fresh
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _json_save_progress(email: str, progress: dict) -> None:
    with open(_progress_path(email), "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)
