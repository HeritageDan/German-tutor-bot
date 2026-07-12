"""
JWT-based auth with Supabase user storage.
Falls back to local JSON files if SUPABASE_URL is not set.
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import requests

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "change-this-in-production")
TOKEN_EXPIRY_DAYS = 30

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)

USERS_DIR = os.environ.get("USERS_DIR", "users")
if not USE_SUPABASE:
    os.makedirs(USERS_DIR, exist_ok=True)


def _sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _sb_url(filters: str = "") -> str:
    return f"{SUPABASE_URL}/rest/v1/users{filters}"


# ── Load / save user ────────────────────────────────────────────────────────

def _load_user(email: str) -> dict | None:
    if USE_SUPABASE:
        try:
            resp = requests.get(
                _sb_url(f"?email=eq.{email.lower()}&limit=1"),
                headers=_sb_headers(), timeout=10
            )
            resp.raise_for_status()
            rows = resp.json()
            return rows[0] if rows else None
        except Exception as e:
            print(f"Supabase load_user error: {e}")
            return None
    # JSON fallback
    path = _user_path(email)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_user(user: dict) -> None:
    if USE_SUPABASE:
        try:
            resp = requests.post(
                _sb_url(),
                headers={**_sb_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
                json=user, timeout=10
            )
            resp.raise_for_status()
        except Exception as e:
            print(f"Supabase save_user error: {e}")
        return
    path = _user_path(user["email"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(user, f, ensure_ascii=False, indent=2)


def _user_path(email: str) -> str:
    safe = email.lower().replace("@", "_at_").replace(".", "_")
    return os.path.join(USERS_DIR, f"user_{safe}.json")


# ── Signup / Login ──────────────────────────────────────────────────────────

def signup(email: str, password: str, display_name: str,
           native_language: str = "English", target_language: str = "German") -> dict:
    email = email.lower().strip()
    if _load_user(email):
        return {"ok": False, "error": "An account with this email already exists."}

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "display_name": display_name,
        "password_hash": hashed,
        "plan": "free",
        "native_language": native_language,
        "target_language": target_language,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_user(user)
    return {"ok": True, "token": _generate_token(user), "user": _public_user(user)}


def login(email: str, password: str) -> dict:
    email = email.lower().strip()
    user = _load_user(email)
    if not user:
        return {"ok": False, "error": "No account found with this email."}
    if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return {"ok": False, "error": "Incorrect password."}
    return {"ok": True, "token": _generate_token(user), "user": _public_user(user)}


# ── Token helpers ───────────────────────────────────────────────────────────

def _generate_token(user: dict) -> str:
    payload = {
        "user_id": user["id"],
        "email": user["email"],
        "plan": user["plan"],
        "native_language": user.get("native_language", "English"),
        "target_language": user.get("target_language", "German"),
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRY_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def verify_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def _public_user(user: dict) -> dict:
    return {k: v for k, v in user.items() if k != "password_hash"}
