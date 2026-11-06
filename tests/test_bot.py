import asyncio
import hashlib
import hmac
from types import SimpleNamespace

from dialogbrain.brain import REFUSAL_REPLY, Brain
from dialogbrain.memory import ConversationStore
from dialogbrain.whatsapp import extract_text_messages, split_message, verify_signature


class Block(SimpleNamespace):
    def to_dict(self):
        return dict(self.__dict__)


class FakeMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def make_brain(tmp_path, responses):
    messages = FakeMessages(responses)
    client = SimpleNamespace(beta=SimpleNamespace(messages=messages))
    store = ConversationStore(str(tmp_path / "t.db"))
    return Brain(store, client, "claude-opus-5-5", "sys"), messages, store


def resp(text, stop="end_turn"):
    return SimpleNamespace(
        stop_reason=stop,
        content=[Block(type="thinking", thinking="", signature="sig"), Block(type="text", text=text)],
    )


def test_history_is_remembered_and_replayed_unchanged(tmp_path):
    brain, messages, store = make_brain(tmp_path, [resp("Merhaba Ali!"), resp("Adın Ali.")])
    assert asyncio.run(brain.reply("905", "Adım Ali")) == "Merhaba Ali!"
    assert asyncio.run(brain.reply("905", "Adım ne?")) == "Adın Ali."

    second = messages.calls[1]["messages"]
    assert [m["role"] for m in second] == ["user", "assistant", "user"]
    assert second[1]["content"][0] == {"type": "thinking", "thinking": "", "signature": "sig"}
    assert messages.calls[1]["fallbacks"] == "default"
    assert len(store.history("905")) == 4
    assert store.history("other") == []


def test_refusal_is_not_stored(tmp_path):
    brain, _, store = make_brain(tmp_path, [SimpleNamespace(stop_reason="refusal", content=[])])
    assert asyncio.run(brain.reply("905", "x")) == REFUSAL_REPLY
    assert store.history("905") == []


def test_reset_and_dedupe(tmp_path):
    store = ConversationStore(str(tmp_path / "t.db"))
    store.append_turn("a", [{"type": "text", "text": "hi"}], [{"type": "text", "text": "yo"}])
    store.reset("a")
    assert store.history("a") == []
    assert store.mark_processed("wamid.1") is True
    assert store.mark_processed("wamid.1") is False


def test_split_message():
    text = ("kelime " * 1500).strip()
    parts = split_message(text)
    assert all(len(p) <= 4096 for p in parts)
    assert " ".join(parts) == text


def test_signature():
    body = b'{"a":1}'
    sig = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert verify_signature("secret", body, sig)
    assert not verify_signature("secret", body, "sha256=bad")
    assert not verify_signature("secret", body, None)


def test_extract_messages():
    payload = {"entry": [{"changes": [{"value": {"messages": [
        {"id": "wamid.1", "from": "905", "type": "text", "text": {"body": "Selam"}}
    ]}}]}]}
    assert extract_text_messages(payload) == [
        {"id": "wamid.1", "from": "905", "type": "text", "text": "Selam"}
    ]
