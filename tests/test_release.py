"""Offline regression tests: fixtures, API boundaries, and request isolation."""
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

import db
import logic
import llm_router
from main import app


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "demo.db"))
    for key in ["OPENAI_API_KEY", "GEMINI_API_KEY", "GEMINI_MODEL", "CAMPUS_API_TOKEN"]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ALLOW_CLOUD_LLM", "false")
    monkeypatch.setenv("LLM_STRATEGY", "offline")
    # Regression tests must never call a real provider or validate an exposed key.
    def no_network(*args, **kwargs):
        raise AssertionError("Unexpected network access")
    monkeypatch.setattr(llm_router.requests, "get", no_network)
    monkeypatch.setattr(llm_router.requests, "post", no_network)


@pytest.fixture
def client():
    with TestClient(app, client=("127.0.0.1", 50000)) as c:
        yield c


def test_database_is_reproducible_and_idempotent():
    db.init_db()
    db.init_db()
    with db.get_connection() as c:
        assert c.execute("select count(*) from students").fetchone()[0] == 25
        assert c.execute("select count(*) from attendance").fetchone()[0] == 25
        assert c.execute("select count(*) from marks").fetchone()[0] == 75
    assert {row["id"] for row in db.get_weak_students()} == {3, 5, 10, 12, 15, 17, 21, 24}


@pytest.mark.parametrize("query,kind", [
    ("Show students with attendance below 60%", "data"),
    ("List all students in ECE branch", "data"),
    ("Identify weak students and suggest improvements", "analytical"),
    ("Analyze performance of CSE 3rd year students", "analytical"),
    ("Who are the top performers?", "analytical"),
    ("What is the minimum attendance policy?", "knowledge"),
])
def test_documented_queries_work_offline(client, query, kind):
    response = client.post("/query", json={"query": query})
    assert response.status_code == 200
    result = response.json()
    assert result["query_type"] == kind
    assert result["answer"]
    assert result["model_info"]["provider"] in {"database", "fallback"}


def test_no_global_history_or_debug_endpoint(client):
    client.post("/query", json={"query": "List all students"})
    assert client.get("/session-memory").status_code == 404
    assert client.get("/docs").status_code == 404
    assert not hasattr(logic, "context_engine")
    assert not hasattr(logic, "llm_router")


def test_request_history_isolation(monkeypatch):
    db.init_db()
    def capture(self, messages, **kwargs):
        return {"content": messages[-1]["content"], "provider": "mock", "model": "test", "token_count": 1}
    monkeypatch.setattr(llm_router.LLMRouter, "chat", capture)
    def query(marker):
        return logic.process_query("Analyze performance", history=[{"query": marker, "response": marker}])["answer"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = list(pool.map(query, ["PRIVATE_SESSION_A", "PRIVATE_SESSION_B"]))
    assert "PRIVATE_SESSION_A" in a and "PRIVATE_SESSION_B" not in a
    assert "PRIVATE_SESSION_B" in b and "PRIVATE_SESSION_A" not in b


def test_cloud_requires_both_operator_and_request_consent(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    assert not llm_router.get_router({"allow_cloud": True}).check_openai()
    monkeypatch.setenv("ALLOW_CLOUD_LLM", "true")
    assert not llm_router.get_router().check_openai()
    assert llm_router.get_router({"allow_cloud": True}).check_openai()


def test_router_uses_only_backend_keys_and_isolates_settings(monkeypatch):
    monkeypatch.setenv("ALLOW_CLOUD_LLM", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "operator-key")
    a = llm_router.get_router({"openai_api_key": "client-key", "strategy": "auto", "allow_cloud": True})
    b = llm_router.get_router()
    assert a.openai_api_key == b.openai_api_key == "operator-key"
    assert a.strategy == "auto" and a.allow_cloud
    assert b.strategy == "offline" and not b.allow_cloud


def test_always_ollama_cannot_fall_back_to_cloud(monkeypatch):
    post = Mock(side_effect=llm_router.requests.ConnectionError("offline"))
    monkeypatch.setattr(llm_router.requests, "post", post)
    router = llm_router.LLMRouter(openai_api_key="key", gemini_api_key="key", gemini_model="model",
                                  strategy="always_ollama", allow_cloud=True)
    result = router.chat([{"role": "user", "content": "hello"}])
    assert result["provider"] == "fallback"
    assert post.call_count == 1
    assert post.call_args.args[0].startswith("http://localhost:11434/")


def test_provider_failures_have_bounded_retries_and_redacted_errors(monkeypatch):
    post = Mock(side_effect=RuntimeError("sensitive key must not be returned"))
    monkeypatch.setattr(llm_router.requests, "post", post)
    router = llm_router.LLMRouter(gemini_api_key="test", gemini_model="demo", allow_cloud=True, strategy="auto")
    result = router.chat([{"role": "user", "content": "hello"}])
    assert post.call_count == 2
    assert "sensitive" not in str(result)


def test_gemini_rest_request_uses_backend_key(monkeypatch):
    response = Mock(status_code=200)
    response.json.return_value = {"candidates": [{"content": {"parts": [{"text": "answer"}]}}]}
    post = Mock(return_value=response)
    monkeypatch.setattr(llm_router.requests, "post", post)
    monkeypatch.setenv("GEMINI_API_KEY", "backend-key")
    monkeypatch.setenv("GEMINI_MODEL", "demo-model")
    monkeypatch.setenv("ALLOW_CLOUD_LLM", "true")
    router = llm_router.get_router({"strategy": "always_gemini", "allow_cloud": True})
    assert router.chat([{"role": "user", "content": "hello"}])["content"] == "answer"
    assert post.call_args.kwargs["headers"] == {"x-goog-api-key": "backend-key"}
    assert post.call_args.kwargs["allow_redirects"] is False
    assert "key=" not in post.call_args.args[0]


def test_rejects_request_supplied_network_destination(client):
    response = client.post("/query", json={"query": "hi", "llm_config": {"ollama_url": "http://internal"}})
    assert response.status_code == 422


@pytest.mark.parametrize("field", ["openai_api_key", "gemini_api_key"])
def test_api_rejects_request_credentials_without_echoing_them(client, field):
    response = client.post("/query", json={"query": "hi", "llm_config": {field: "PRIVATE"}})
    assert response.status_code == 422 and "PRIVATE" not in response.text


def test_status_exposes_configuration_without_exposing_keys_or_making_calls(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "PRIVATE")
    monkeypatch.setenv("GEMINI_MODEL", "demo-model")
    response = client.get("/llm-status")
    assert response.status_code == 200
    assert response.json()["gemini_configured"] is True
    assert response.json()["cloud_enabled_by_operator"] is False
    assert "PRIVATE" not in response.text


def test_api_errors_do_not_echo_inputs(client, monkeypatch):
    response = client.post("/query", json={"query": "PRIVATE", "llm_config": {"strategy": "invalid"}})
    assert response.status_code == 422 and "PRIVATE" not in response.text
    def fail(**kwargs):
        raise RuntimeError("PRIVATE")
    monkeypatch.setattr(logic, "process_query", fail)
    response = client.post("/query", json={"query": "hi"})
    assert response.status_code == 500 and "PRIVATE" not in response.text


def test_whitespace_and_oversized_input_rejected(client):
    assert client.post("/query", json={"query": " "}).status_code == 400
    assert client.post("/query", json={"query": "x" * 4001}).status_code == 422
    assert client.post("/query", json={"query": "hi", "history": [{"query": "q", "response": "a"}] * 4}).status_code == 422


def test_remote_backend_requires_authentication(monkeypatch):
    with TestClient(app, client=("192.0.2.1", 50000)) as remote:
        assert remote.get("/health").status_code == 403
        monkeypatch.setenv("CAMPUS_API_TOKEN", "demo-access-token")
        assert remote.get("/health").status_code == 401
        assert remote.get("/health", headers={"Authorization": "Bearer demo-access-token"}).status_code == 200


def test_cors_is_not_wildcard(client):
    response = client.options("/query", headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in response.headers


def test_offline_mode_never_contacts_providers(monkeypatch):
    post = Mock()
    get = Mock()
    monkeypatch.setattr(llm_router.requests, "post", post)
    monkeypatch.setattr(llm_router.requests, "get", get)
    router = llm_router.LLMRouter(openai_api_key="test", gemini_api_key="test", gemini_model="test",
                                  strategy="offline", allow_cloud=True)
    assert router.chat([{"role": "user", "content": "hello"}])["provider"] == "fallback"
    assert router.decide_provider("hello")[0] == "fallback"
    router.get_status()
    post.assert_not_called()
    get.assert_not_called()


@pytest.mark.parametrize("query,top_section", [
    ("What is the minimum attendance policy?", "ATTENDANCE POLICY"),
    ("What is the library policy for borrowing books?", "LIBRARY POLICY"),
    ("How much is the fee for improvement exams?", "IMPROVEMENT EXAMINATIONS"),
    ("What are the scholarship guidelines?", "FEE POLICY"),
    ("Who qualifies for remedial classes?", "REMEDIAL CLASSES"),
    ("How do I change my mentor under the mentorship program?", "MENTORSHIP PROGRAM"),
    ("What is the grading policy?", "GRADING POLICY"),
    ("What is the policy on mobile phones during lectures?", "DISCIPLINARY POLICY"),
])
def test_policy_results_rank_relevant_sections_and_return_exact_sources(client, query, top_section):
    from policy_search import KNOWLEDGE_BASE

    response = client.post("/query", json={"query": query})
    assert response.status_code == 200
    result = response.json()
    assert result["query_type"] == "knowledge"
    sources = result["sources"]
    assert 1 <= len(sources) <= 3
    assert sources[0]["section"] == top_section
    for number, source in enumerate(sources, start=1):
        assert source["number"] == number
        assert f"[{number}] {source['excerpt']}" in result["answer"]
        lines = (KNOWLEDGE_BASE / source["document"]).read_text(encoding="utf-8").splitlines()
        assert source["excerpt"] == "\n".join(lines[source["start_line"] - 1:source["end_line"]])


@pytest.mark.parametrize("query", ["What is the drone policy?", "What are the policies?"])
def test_policy_no_match_returns_no_sources(client, query):
    result = client.post("/query", json={"query": query}).json()
    assert result["query_type"] == "knowledge"
    assert result["sources"] == []
    assert "couldn't find a matching section" in result["answer"]


def test_provider_synthesis_uses_the_same_numbering_exposed_by_api(client, monkeypatch):
    chat = Mock(return_value={"content": "Four books [1].", "provider": "ollama",
                              "model": "test", "token_count": 10})
    monkeypatch.setattr(llm_router.LLMRouter, "chat", chat)
    result = client.post("/query", json={"query": "What is the library policy?"}).json()
    assert result["answer"] == "Four books [1]."
    source = result["sources"][0]
    assert source["section"] == "LIBRARY POLICY"
    assert f"[1] {source['document']}: {source['excerpt']}" in chat.call_args.args[0][-1]["content"]


def test_policy_search_treats_punctuation_as_text(client):
    text = 'What is the library policy? " ) OR * :'
    response = client.post("/query", json={"query": text})
    assert response.status_code == 200
    assert response.json()["sources"][0]["section"] == "LIBRARY POLICY"
