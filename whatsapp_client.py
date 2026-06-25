"""
Thin wrapper around Meta's WhatsApp Cloud API.
Handles: sending text, sending audio (voice notes), downloading inbound media (audio you send in).
"""

import requests

from config import META_ACCESS_TOKEN, META_PHONE_NUMBER_ID, META_API_VERSION

GRAPH_BASE = f"https://graph.facebook.com/{META_API_VERSION}"


def _headers():
    return {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


def send_text(to_number: str, message: str) -> dict:
    url = f"{GRAPH_BASE}/{META_PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": message},
    }
    resp = requests.post(url, headers=_headers(), json=payload, timeout=20)
    resp.raise_for_status()
    return resp.json()


def upload_audio(file_path: str) -> str:
    """Uploads an OGG/Opus audio file to Meta's servers, returns the media ID needed to send it."""
    url = f"{GRAPH_BASE}/{META_PHONE_NUMBER_ID}/media"
    with open(file_path, "rb") as f:
        files = {"file": (file_path, f, "audio/ogg")}
        data = {"messaging_product": "whatsapp", "type": "audio/ogg"}
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {META_ACCESS_TOKEN}"},
            files=files,
            data=data,
            timeout=30,
        )
    resp.raise_for_status()
    return resp.json()["id"]


def send_audio(to_number: str, file_path: str) -> dict:
    """Uploads then sends a voice note. file_path must be a valid OGG/Opus file."""
    media_id = upload_audio(file_path)
    url = f"{GRAPH_BASE}/{META_PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "audio",
        "audio": {"id": media_id},
    }
    resp = requests.post(url, headers=_headers(), json=payload, timeout=20)
    resp.raise_for_status()
    return resp.json()


def get_media_url(media_id: str) -> str:
    """Inbound media (e.g. a voice note you sent) arrives as a media ID — resolve it to a download URL."""
    url = f"{GRAPH_BASE}/{media_id}"
    resp = requests.get(url, headers={"Authorization": f"Bearer {META_ACCESS_TOKEN}"}, timeout=20)
    resp.raise_for_status()
    return resp.json()["url"]


def download_media(media_url: str, save_path: str) -> str:
    resp = requests.get(media_url, headers={"Authorization": f"Bearer {META_ACCESS_TOKEN}"}, timeout=30)
    resp.raise_for_status()
    with open(save_path, "wb") as f:
        f.write(resp.content)
    return save_path


def parse_inbound_message(payload: dict) -> dict | None:
    """
    Extracts the useful bits from Meta's webhook payload.
    Returns None if this payload isn't an actual inbound message (e.g. a status update).
    """
    try:
        entry = payload["entry"][0]
        changes = entry["changes"][0]["value"]
        if "messages" not in changes:
            return None

        message = changes["messages"][0]
        from_number = message["from"]
        msg_type = message["type"]
        message_id = message.get("id")

        if msg_type == "text":
            return {"from": from_number, "type": "text", "text": message["text"]["body"], "id": message_id}

        if msg_type == "audio":
            return {"from": from_number, "type": "audio", "media_id": message["audio"]["id"], "id": message_id}

        return {"from": from_number, "type": msg_type, "raw": message, "id": message_id}

    except (KeyError, IndexError):
        return None
