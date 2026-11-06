"""Claude API ile konuşma mantığı."""

import asyncio
import logging
from collections import defaultdict

import anthropic

from .memory import ConversationStore

log = logging.getLogger(__name__)

REFUSAL_REPLY = "Üzgünüm, bu isteğe yardımcı olamıyorum. Başka bir konuda sorabilirsin."
ERROR_REPLY = "Şu an cevap veremiyorum, lütfen birazdan tekrar dene."


class Brain:
    def __init__(
        self,
        store: ConversationStore,
        client: anthropic.AsyncAnthropic,
        model: str,
        system_prompt: str,
        effort: str = "low",
    ) -> None:
        self.store = store
        self.client = client
        self.model = model
        self.system_prompt = system_prompt
        self.effort = effort
        # Aynı kullanıcıdan gelen mesajlar sırayla işlensin diye kullanıcı başına kilit.
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def reply(self, user_id: str, text: str) -> str:
        async with self._locks[user_id]:
            return await self._reply(user_id, text)

    async def _reply(self, user_id: str, text: str) -> str:
        history = self.store.history(user_id)
        user_content = [{"type": "text", "text": text}]
        messages = history + [{"role": "user", "content": user_content}]

        try:
            response = await self.client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=self.system_prompt,
                messages=messages,
                output_config={"effort": self.effort},
                # Önbellek: her istekte geçmişin ortak öneki ucuz okunur.
                cache_control={"type": "ephemeral"},
                # Güvenlik sınıflandırıcısı reddederse Anthropic'in önerdiği modele düş.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.RateLimitError:
            log.warning("Claude API hız sınırına takıldı")
            return ERROR_REPLY
        except anthropic.APIStatusError as exc:
            log.error("Claude API hatası %s: %s", exc.status_code, exc.message)
            return ERROR_REPLY
        except anthropic.APIConnectionError:
            log.exception("Claude API'ye bağlanılamadı")
            return ERROR_REPLY

        if response.stop_reason == "refusal":
            # Reddedilen tur geçmişe yazılmaz; konuşma temiz kalır.
            return REFUSAL_REPLY

        answer = "".join(b.text for b in response.content if b.type == "text").strip()

        # Cevabın tüm blokları (thinking dahil) değiştirilmeden saklanır.
        assistant_content = [b.to_dict() for b in response.content]
        self.store.append_turn(user_id, user_content, assistant_content)

        return answer or "…"
