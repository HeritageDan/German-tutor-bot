"""
Simple JWT-based auth.
Users are stored as JSON files in users/ directory (same pattern as progress storage).
Swap to Supabase later by only rewriting load_user() and save_user().

Future paid tier: add a 'plan' field ('free' | 'pro') to the user record.
Check it in /api/chat to gate features (e.g. voice notes, lesson history).
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "change-this-in-production")
TOKEN_EXPIRY_DAYS = 30
USERS_DIR = os.environ.get("USERS_DIR", "users")
os.makedirs(USERS_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# User storage
# ---------------------------------------------------------------------------

def _user_path(email: str) -> str:
    safe = email.lower().replace("@", "_at_").replace(".", "_")
    return os.path.join(USERS_DIR, f"user_{safe}.json")


def load_user(email: str) -> dict | None:
    path = _user_path(email)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_user(user: dict) -> None:
    path = _user_path(user["email"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(user, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Signup / Login
# ---------------------------------------------------------------------------

def signup(email: str, password: str, display_name: str) -> dict:
    """
    Creates a new user. Returns {"ok": True, "token": ...} or {"ok": False, "error": ...}
    """
    email = email.lower().strip()
    if load_user(email):
        return {"ok": False, "error": "An account with this email already exists."}

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "display_name": display_name,
        "password_hash": hashed,
        "plan": "free",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    save_user(user)
    token = _generate_token(user)
    return {"ok": True, "token": token, "user": _public_user(user)}


def login(email: str, password: str) -> dict:
    """
    Returns {"ok": True, "token": ...} or {"ok": False, "error": ...}
    """
    email = email.lower().strip()
    user = load_user(email)
    if not user:
        return {"ok": False, "error": "No account found with this email."}

    if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return {"ok": False, "error": "Incorrect password."}

    token = _generate_token(user)
    return {"ok": True, "token": token, "user": _public_user(user)}


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def _generate_token(user: dict) -> str:
    payload = {
        "user_id": user["id"],
        "email": user["email"],
        "plan": user["plan"],
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRY_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def verify_token(token: str) -> dict | None:
    """Returns the decoded payload dict, or None if invalid/expired."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def _public_user(user: dict) -> dict:
    """Strip the password hash before sending user data to the frontend."""
    return {k: v for k, v in user.items() if k != "password_hash"}
