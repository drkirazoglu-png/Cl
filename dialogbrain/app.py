"""FastAPI webhook sunucusu.

Çalıştırma:  uvicorn dialogbrain.app:app --host 0.0.0.0 --port 8000
"""

import logging
from contextlib import asynccontextmanager

import anthropic
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response

from .brain import Brain
from .config import Settings
from .memory import ConversationStore
from .whatsapp import WhatsAppClient, extract_text_messages, verify_signature

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("dialogbrain")

RESET_COMMANDS = {"/reset", "/sifirla", "/sıfırla"}
HELP_TEXT = (
    "Merhaba! Ben Dialogbrain. Bana istediğini yazabilirsin, konuşmamızı hatırlarım.\n"
    "Geçmişi silmek için */sıfırla* yaz."
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings.from_env()
    store = ConversationStore(settings.db_path)
    app.state.settings = settings
    app.state.store = store
    app.state.brain = Brain(
        store=store,
        client=anthropic.AsyncAnthropic(),
        model=settings.model,
        system_prompt=settings.system_prompt,
        effort=settings.effort,
    )
    app.state.whatsapp = WhatsAppClient(
        settings.whatsapp_token, settings.whatsapp_phone_number_id, settings.graph_api_version
    )
    yield
    await app.state.whatsapp.aclose()


app = FastAPI(title="Dialogbrain", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/webhook")
async def verify_webhook(request: Request) -> Response:
    """Meta'nın webhook doğrulama isteği."""
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == request.app.state.settings.whatsapp_verify_token
    ):
        return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
    raise HTTPException(status_code=403, detail="Doğrulama başarısız")


@app.post("/webhook")
async def receive_webhook(request: Request, background: BackgroundTasks) -> dict:
    body = await request.body()
    settings: Settings = request.app.state.settings
    if settings.whatsapp_app_secret and not verify_signature(
        settings.whatsapp_app_secret, body, request.headers.get("X-Hub-Signature-256")
    ):
        raise HTTPException(status_code=401, detail="Geçersiz imza")

    payload = await request.json()
    for msg in extract_text_messages(payload):
        if msg["id"] and request.app.state.store.mark_processed(msg["id"]):
            # Meta 200'ü hızlı bekler; cevabı arka planda üret.
            background.add_task(handle_message, request.app, msg)
    return {"status": "ok"}


async def handle_message(app: FastAPI, msg: dict) -> None:
    whatsapp: WhatsAppClient = app.state.whatsapp
    sender = msg["from"]
    try:
        await whatsapp.mark_read(msg["id"])
        if msg["type"] != "text":
            await whatsapp.send_text(sender, "Şimdilik yalnızca metin mesajlarını anlayabiliyorum.")
            return

        text = msg["text"].strip()
        lowered = text.lower()
        if lowered in RESET_COMMANDS:
            app.state.store.reset(sender)
            await whatsapp.send_text(sender, "Konuşma geçmişi silindi. Yeniden başlayalım!")
            return
        if lowered in {"/yardim", "/yardım", "/help"}:
            await whatsapp.send_text(sender, HELP_TEXT)
            return

        answer = await app.state.brain.reply(sender, text)
        await whatsapp.send_text(sender, answer)
    except Exception:
        log.exception("Mesaj işlenemedi: %s", msg.get("id"))
