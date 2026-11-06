import os
from dataclasses import dataclass


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Ortam değişkeni eksik: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    whatsapp_token: str
    whatsapp_phone_number_id: str
    whatsapp_verify_token: str
    whatsapp_app_secret: str | None
    graph_api_version: str
    db_path: str
    model: str
    effort: str
    system_prompt: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            whatsapp_token=_require("WHATSAPP_TOKEN"),
            whatsapp_phone_number_id=_require("WHATSAPP_PHONE_NUMBER_ID"),
            whatsapp_verify_token=_require("WHATSAPP_VERIFY_TOKEN"),
            whatsapp_app_secret=os.environ.get("WHATSAPP_APP_SECRET") or None,
            graph_api_version=os.environ.get("GRAPH_API_VERSION", "v21.0"),
            db_path=os.environ.get("DIALOGBRAIN_DB", "dialogbrain.db"),
            model=os.environ.get("CLAUDE_MODEL", "claude-opus-5-5"),
            effort=os.environ.get("CLAUDE_EFFORT", "low"),
            system_prompt=os.environ.get(
                "SYSTEM_PROMPT",
                "Sen Dialogbrain adında, WhatsApp üzerinden konuşan yardımsever bir asistansın. "
                "Kullanıcının dilinde, kısa ve anlaşılır cevaplar ver. WhatsApp biçimlendirmesi "
                "kullan (*kalın*, _italik_); Markdown başlıkları ve tablolar kullanma.",
            ),
        )
