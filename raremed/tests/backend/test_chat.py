import json
import threading
import uuid

import httpx
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.model_config import load_model_config
from app.ai.prompts import system_prompt
from app.ai.providers import build_provider
from app.ai.providers.base import GenerationChunk, ProviderError
from app.ai.providers.ollama import OllamaProvider, request_think
from app.ai.thinking import ThinkSplitter
from app.core.config import get_settings
from app.core.security import hash_password
from app.models import Base, User
from app.repositories.conversation import ConversationRepository, utcnow
from app.services.chat import PersistResult, iterate_reply, persist_turn, save_turn, trim_messages


def _parse_sse(payload: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in payload.split("\n\n"):
        if not block.strip():
            continue
        event = "message"
        data = ""
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data += line.split(":", 1)[1].strip()
        events.append((event, json.loads(data)))
    return events


def _ndjson(*rows: dict) -> str:
    return "\n".join(json.dumps(row) for row in rows) + "\n"


def _install_transport(monkeypatch, handler) -> None:
    def build(_settings, _config):
        return OllamaProvider(
            "http://ollama.test",
            client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler)),
        )

    monkeypatch.setattr("app.api.v1.endpoints.chat.build_provider", build)


def test_ollama_probe_reports_the_configured_model():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": "qwen3:4b"}]})

    result = OllamaProvider(
        "http://ollama.test",
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    ).probe("qwen3:4b")

    assert result.reachable is True
    assert result.model_ready is True
    assert result.installed_models == ["qwen3:4b"]


def test_ollama_probe_is_offline_when_the_port_refuses():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    result = OllamaProvider(
        "http://127.0.0.1:11434",
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    ).probe("qwen3:4b")

    assert result.reachable is False
    assert result.model_ready is False
    assert result.detail == "ConnectError"


def test_qwen3_keeps_reasoning_out_of_the_answer_channel():
    assert request_think("qwen3:4b", False) is False
    assert request_think("qwen3:4b", True) is True
    assert request_think("llama3.2", False) is False
    assert request_think("llama3.2", True) is True


def test_live_ollama_connection_when_it_is_running():
    result = OllamaProvider(get_settings().ollama_base_url, probe_timeout=2).probe("qwen3:4b")
    if not result.reachable:
        pytest.skip(result.detail or "Ollama is not running")
    assert result.base_url


def test_chat_rejects_an_anonymous_request(sqlite_client):
    response = sqlite_client.post(
        "/api/v1/chat",
        json={"messages": [{"role": "user", "content": "Hello"}], "locale": "en"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_chat_request_streams_tokens_and_reports_speed(auth_client, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        assert body["model"] == "qwen3:4b"
        assert "think" not in body
        assert body["messages"][0]["role"] == "system"
        assert "verified diagnosis" in body["messages"][0]["content"]
        assert body["messages"][-1]["content"] == "Hello"
        return httpx.Response(
            200,
            content=_ndjson(
                {"message": {"role": "assistant", "content": "Hel"}, "done": False},
                {"message": {"role": "assistant", "content": "lo"}, "done": False},
                {
                    "message": {"role": "assistant", "content": ""},
                    "done": True,
                    "eval_count": 2,
                    "eval_duration": 1_000_000_000,
                },
            ),
        )

    monkeypatch.setattr(
        "app.api.v1.endpoints.chat.persist_turn",
        lambda *args, **kwargs: PersistResult(False),
    )

    _install_transport(monkeypatch, handler)
    with auth_client.stream(
        "POST",
        "/api/v1/chat",
        json={"messages": [{"role": "user", "content": "Hello"}], "locale": "en"},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        payload = response.read().decode()

    events = _parse_sse(payload)
    assert [item[1]["text"] for item in events if item[0] == "token"] == ["Hel", "lo"]
    done = next(item[1] for item in events if item[0] == "done")
    assert done["model"] == "qwen3:4b"
    assert done["tokens_per_second"] == 2.0
    assert done["eval_count"] == 2
    assert done["stopped"] is False
    assert done["saved"] is False
    assert isinstance(done["elapsed_ms"], int)


def test_chat_reports_a_missing_model(auth_client, monkeypatch):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model 'qwen3:4b' not found"})

    monkeypatch.setattr(
        "app.api.v1.endpoints.chat.persist_turn",
        lambda *args, **kwargs: PersistResult(False),
    )
    _install_transport(monkeypatch, handler)
    with auth_client.stream(
        "POST",
        "/api/v1/chat",
        json={"messages": [{"role": "user", "content": "Hello"}], "locale": "ary"},
    ) as response:
        events = _parse_sse(response.read().decode())

    assert events[0][0] == "error"
    assert events[0][1]["code"] == "model_missing"
    assert "ollama pull qwen3:4b" in events[0][1]["message"]
    assert not any(event == "done" for event, _data in events)


def test_chat_reports_ollama_offline(auth_client, monkeypatch):
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(
        "app.api.v1.endpoints.chat.persist_turn",
        lambda *args, **kwargs: PersistResult(False),
    )
    _install_transport(monkeypatch, handler)
    with auth_client.stream(
        "POST",
        "/api/v1/chat",
        json={"messages": [{"role": "user", "content": "Hello"}]},
    ) as response:
        events = _parse_sse(response.read().decode())

    assert events[0][1]["code"] == "ollama_unavailable"
    assert "not reachable" in events[0][1]["message"]
    assert "ollama pull qwen3:4b" in events[0][1]["message"]


def test_stream_stops_when_cancelled():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_ndjson(
                {"message": {"content": "one"}, "done": False},
                {"message": {"content": "two"}, "done": False},
            ),
        )

    cancel = threading.Event()
    provider = OllamaProvider(
        "http://ollama.test",
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )

    def cancel_after_first(chunk: GenerationChunk) -> GenerationChunk:
        cancel.set()
        return chunk

    chunks = []
    for chunk in provider.stream(
        messages=[{"role": "user", "content": "Hi"}],
        model="qwen3:4b",
        temperature=0.6,
        num_ctx=4096,
        think=False,
        cancel=cancel,
    ):
        chunks.append(cancel_after_first(chunk))
    assert [chunk.text for chunk in chunks] == ["one"]


def test_thinking_tags_stay_out_of_the_answer_when_disabled():
    class Scripted:
        name = "scripted"

        def probe(self, model: str):
            raise NotImplementedError

        def stream(self, **_kwargs):
            yield GenerationChunk(text="<thi")
            yield GenerationChunk(text="nk>secret</think>Visible")
            yield GenerationChunk(thinking="hidden", done=True, eval_count=4, eval_duration_ns=2_000_000_000)

    config = load_model_config(get_settings())
    assert config.think is False
    chunks = list(
        iterate_reply(
            Scripted(),
            config,
            [type("Turn", (), {"role": "user", "content": "Hi"})()],
            "en",
            threading.Event(),
        )
    )
    assert "".join(chunk.text for chunk in chunks) == "Visible"
    assert all(chunk.thinking == "" for chunk in chunks)


def test_system_prompt_forbids_invented_evidence():
    english = system_prompt("en")
    assert "verified diagnosis" in english
    assert "knowledge graph is not connected" in english
    assert "Do not invent citations" in english
    assert "Darija" in system_prompt("ary")
    splitter = ThinkSplitter()
    visible, thinking = splitter.feed("A<think>no")
    assert visible == "A"
    assert thinking == "no"
    visible, thinking = splitter.feed("</think>B")
    assert visible == "B"
    assert thinking == ""


def test_context_trim_keeps_the_newest_turn():
    messages = [{"role": "system", "content": "s"}] + [
        {"role": "user", "content": "x" * 1000} for _ in range(10)
    ]
    trimmed = trim_messages(messages, num_ctx=512)
    assert trimmed[0]["role"] == "system"
    assert trimmed[-1]["content"] == "x" * 1000
    assert len(trimmed) < len(messages)


def test_openai_and_vllm_share_the_compatible_client(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "inference_provider", "vllm")
    monkeypatch.setattr(settings, "vllm_base_url", "")
    unconfigured = build_provider(settings, load_model_config(settings))
    assert unconfigured.name == "vllm"
    with pytest.raises(ProviderError) as missing:
        list(
            unconfigured.stream(
                messages=[{"role": "user", "content": "Hi"}],
                model="qwen3:4b",
                temperature=0.6,
                num_ctx=4096,
                think=False,
                cancel=threading.Event(),
            )
        )
    assert missing.value.code == "provider_not_configured"

    monkeypatch.setattr(settings, "inference_provider", "openai")
    monkeypatch.setattr(settings, "openai_base_url", "http://openai.test/v1")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        return httpx.Response(200, content='data: {"choices":[{"delta":{"content":"Hi"}}]}\n\ndata: [DONE]\n\n')

    provider = build_provider(settings, load_model_config(settings))
    provider._client_factory = lambda: httpx.Client(transport=httpx.MockTransport(handler))
    chunks = list(
        provider.stream(
            messages=[{"role": "user", "content": "Hi"}],
            model="qwen3:4b",
            temperature=0.6,
            num_ctx=4096,
            think=False,
            cancel=threading.Event(),
        )
    )
    assert "".join(chunk.text for chunk in chunks) == "Hi"
    assert chunks[-1].done is True


def test_save_turn_inserts_and_regenerate_replaces(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)
    monkeypatch.setattr("app.services.chat.get_session_factory", lambda: factory)
    session = factory()
    owner = User(
        email="owner@example.com",
        password_hash=hash_password("correcthorse1"),
        display_name="Owner",
        role="user",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    session.add(owner)
    session.flush()
    conversation = ConversationRepository(session).add(
        owner_id=owner.id,
        locale="en",
        title="New conversation",
        now=utcnow(),
    )
    session.commit()
    conversation_id = conversation.id
    owner_id = owner.id
    session.close()

    assert save_turn(conversation_id, "fr", "Bonjour", "Salut", False, owner_id=owner_id)
    assert save_turn(conversation_id, "fr", "Bonjour", "Encore", True, owner_id=owner_id)
    stored = ConversationRepository(factory()).get(conversation_id)
    assert stored is not None
    assert [message.role for message in stored.messages] == ["user", "assistant"]
    assert stored.messages[1].content == "Encore"
    assert stored.messages[1].status == "complete"
    assert stored.title == "Bonjour"

    assert persist_turn(
        conversation_id,
        "fr",
        "Bonjour",
        "partial",
        True,
        owner_id=owner_id,
        stopped=True,
        model="qwen3:4b",
    ).saved
    interrupted = ConversationRepository(factory()).get(conversation_id)
    assert interrupted is not None
    assert interrupted.messages[-1].status == "interrupted"
    assert interrupted.messages[-1].content == "partial"
    assert interrupted.messages[-1].extra["hpo_entities"] == []
    assert persist_turn(
        conversation_id,
        "fr",
        "secret",
        "nope",
        False,
        owner_id=uuid.uuid4(),
    ).saved is False
    engine.dispose()
