"""
Persistent storage via Supabase (PostgreSQL).
Falls back to local JSON files if SUPABASE_URL is not set.
"""

import json
import os
import requests
from datetime import date, datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)

PROGRESS_DIR = os.environ.get("PROGRESS_DIR", "user_progress")
if not USE_SUPABASE:
    os.makedirs(PROGRESS_DIR, exist_ok=True)

DEFAULT_PROGRESS = {
    "current_tier": "A1.1",
    "tier_started_at": str(date.today()),
    "sessions_on_current_tier": 0,
    "session_count": 0,
    "mastery_signals": [],
    "vocab_introduced": [],
    "mistake_log": [],
    "topic_override": None,
    "preferred_response_mode": "text",
    "conversation_history": [],
    "total_xp": 0,
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


def get_progress(user_email: str) -> dict:
    if not USE_SUPABASE:
        return _json_get(user_email)
    try:
        resp = requests.get(
            _sb_url("user_progress", f"?user_email=eq.{user_email}&limit=1"),
            headers=_sb_headers(), timeout=10
        )
        resp.raise_for_status()
        rows = resp.json()
        if rows:
            r = rows[0]
            return {
                "current_tier": r.get("current_tier", "A1.1"),
                "tier_started_at": r.get("tier_started_at", str(date.today())),
                "sessions_on_current_tier": r.get("sessions_on_current_tier", 0),
                "session_count": r.get("session_count", 0),
                "mastery_signals": r.get("mastery_signals") or [],
                "vocab_introduced": r.get("vocab_introduced") or [],
                "mistake_log": r.get("mistake_log") or [],
                "topic_override": r.get("topic_override"),
                "preferred_response_mode": r.get("preferred_response_mode", "text"),
                "conversation_history": r.get("conversation_history") or [],
                "total_xp": r.get("total_xp", 0),
            }
        # No row yet — create one
        fresh = DEFAULT_PROGRESS.copy()
        save_progress(user_email, fresh)
        return fresh
    except Exception as e:
        print(f"[storage] get_progress error: {e}")
        return DEFAULT_PROGRESS.copy()


def save_progress(user_email: str, progress: dict) -> None:
    if not USE_SUPABASE:
        return _json_save(user_email, progress)
    # Use a proper ISO timestamp — not the string "now()" which Supabase rejects
    data = {
        "user_email": user_email,
        "current_tier": progress.get("current_tier", "A1.1"),
        "tier_started_at": progress.get("tier_started_at", str(date.today())),
        "sessions_on_current_tier": progress.get("sessions_on_current_tier", 0),
        "session_count": progress.get("session_count", 0),
        "mastery_signals": progress.get("mastery_signals", []),
        "vocab_introduced": progress.get("vocab_introduced", []),
        "mistake_log": progress.get("mistake_log", []),
        "topic_override": progress.get("topic_override"),
        "preferred_response_mode": progress.get("preferred_response_mode", "text"),
        "conversation_history": progress.get("conversation_history", []),
        "total_xp": progress.get("total_xp", 0),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        resp = requests.post(
            _sb_url("user_progress"),
            headers={**_sb_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
            json=data, timeout=10
        )
        if not resp.ok:
            print(f"[storage] save_progress HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"[storage] save_progress error: {e}")


def get_user_languages(user_email: str) -> dict:
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
        print(f"[storage] get_user_languages error: {e}")
    return {"native_language": "English", "target_language": "German"}


def set_user_languages(user_email: str, native_language: str, target_language: str) -> bool:
    if not USE_SUPABASE:
        return False
    try:
        resp = requests.patch(
            _sb_url("users", f"?email=eq.{user_email}"),
            headers={**_sb_headers(), "Prefer": "return=minimal"},
            json={"native_language": native_language, "target_language": target_language},
            timeout=10
        )
        if not resp.ok:
            print(f"[storage] set_user_languages HTTP {resp.status_code}: {resp.text[:200]}")
            return False
        # Reset progress to A1.1 for new language
        fresh = DEFAULT_PROGRESS.copy()
        save_progress(user_email, fresh)
        return True
    except Exception as e:
        print(f"[storage] set_user_languages error: {e}")
        return False


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


def add_vocab(progress: dict, words: list) -> dict:
    existing = set(progress.get("vocab_introduced", []))
    for w in words:
        if w and w not in existing:
            progress["vocab_introduced"].append(w)
            existing.add(w)
    return progress


def add_xp(progress: dict, xp: int) -> dict:
    progress["total_xp"] = progress.get("total_xp", 0) + max(0, int(xp))
    return progress


def increment_session_count(progress: dict) -> dict:
    progress["session_count"] = progress.get("session_count", 0) + 1
    return progress


# ── JSON fallback (local dev only) ──────────────────────────────────────────

def _progress_path(email: str) -> str:
    safe = email.replace("@", "_at_").replace(".", "_")
    return os.path.join(PROGRESS_DIR, f"progress_{safe}.json")


def _json_get(email: str) -> dict:
    path = _progress_path(email)
    if not os.path.exists(path):
        fresh = DEFAULT_PROGRESS.copy()
        _json_save(email, fresh)
        return fresh
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _json_save(email: str, progress: dict) -> None:
    with open(_progress_path(email), "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)
