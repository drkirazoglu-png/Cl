"""WhatsApp Cloud API (Meta) istemcisi."""

import hashlib
import hmac

import httpx

# WhatsApp metin mesajı üst sınırı 4096 karakter.
MAX_MESSAGE_LEN = 4096


def verify_signature(app_secret: str, body: bytes, signature_header: str | None) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header.removeprefix("sha256="))


def split_message(text: str, limit: int = MAX_MESSAGE_LEN) -> list[str]:
    parts: list[str] = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut <= 0:
            cut = text.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        parts.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    if text:
        parts.append(text)
    return parts


def extract_text_messages(payload: dict) -> list[dict]:
    """Webhook gövdesinden gelen mesajları çıkarır: [{id, from, type, text}]."""
    out = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                out.append(
                    {
                        "id": msg.get("id"),
                        "from": msg.get("from"),
                        "type": msg.get("type"),
                        "text": (msg.get("text") or {}).get("body", ""),
                    }
                )
    return out


class WhatsAppClient:
    def __init__(self, token: str, phone_number_id: str, api_version: str = "v21.0") -> None:
        self._url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
        self._http = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {token}"}, timeout=30.0
        )

    async def send_text(self, to: str, text: str) -> None:
        for part in split_message(text):
            resp = await self._http.post(
                self._url,
                json={
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "text",
                    "text": {"body": part},
                },
            )
            resp.raise_for_status()

    async def mark_read(self, message_id: str) -> None:
        await self._http.post(
            self._url,
            json={"messaging_product": "whatsapp", "status": "read", "message_id": message_id},
        )

    async def aclose(self) -> None:
        await self._http.aclose()
