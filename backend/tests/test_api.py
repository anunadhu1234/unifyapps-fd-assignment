"""HTTP API: sign-in and roles, chat (JSON + SSE), conversation history, CSV export, rate limiting."""

import json

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import SecretStr

from agent.supervisor.dependencies import build_deps
from agent.supervisor.supervisor import SQLAgent
from controllers.context import AppServices
from main import create_app
from middleware.rate_limit import limiter
from tests.fakes import ScriptedLLM
from utils.config import get_settings
from utils.thread_store import ThreadStore

BROWSER_A = {"X-Client-Id": "client-alice-0001"}
BROWSER_B = {"X-Client-Id": "client-bob-00000001"}


def customers_script(n=1):
    return {
        "intent_detection": [{"intent": "generate_sql", "standalone_question": "Show all customers.",
                              "user_sql": None, "reason": "t"}] * n,
        "query_planner": [{"restated_request": "All customers", "tables": ["Customers"],
                           "select": [{"kind": "all_columns", "table": "Customers"}]}] * n,
        "sql_generation": [{"sql": "SELECT * FROM Customers"}] * n,
        "generate_explanation": ["This query retrieves every customer.\n\n- Reads `Customers`."] * n,
    }


@pytest.fixture
def client(tmp_path):
    settings = get_settings()
    saved = (settings.auth_normal_password, settings.auth_dev_password, settings.auth_secret)
    settings.auth_normal_password = SecretStr("normal-pass")
    settings.auth_dev_password = SecretStr("dev-pass")
    settings.auth_secret = SecretStr("test-secret-" + "x" * 40)
    limiter._hits.clear()

    def make(script):
        agent = SQLAgent(build_deps(llm=ScriptedLLM(script)), InMemorySaver())
        app = create_app(AppServices(agent=agent, threads=ThreadStore(tmp_path / "app.db")))
        return TestClient(app)

    yield make
    settings.auth_normal_password, settings.auth_dev_password, settings.auth_secret = saved
    limiter._hits.clear()


def sign_in(c, role="normal", browser=None):
    s = get_settings()
    username, password = ((s.auth_normal_username, "normal-pass") if role == "normal"
                          else (s.auth_dev_username, "dev-pass"))
    body = c.post("/api/auth/login", json={"username": username, "password": password}).json()
    assert body["user"]["role"] == role
    return {**(browser or BROWSER_A), "Authorization": f"Bearer {body['token']}"}


def ask(c, headers, question="Show all customers.", **extra):
    return c.post("/api/chat", json={"question": question, **extra}, headers=headers)


def test_health(client):
    r = client({}).get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_sign_in(client):
    c = client({})
    assert c.post("/api/auth/login", json={"username": "demo", "password": "wrong"}).status_code == 401
    headers = sign_in(c, "dev")
    assert c.get("/api/auth/me", headers=headers).json()["user"]["role"] == "dev"


def test_endpoints_require_sign_in(client):
    c = client({})
    assert ask(c, BROWSER_A).status_code == 401
    assert c.get("/api/threads", headers=BROWSER_A).status_code == 401
    assert c.get("/api/schema").status_code == 401
    assert c.get("/api/threads", headers={**BROWSER_A, "Authorization": "Bearer not-a-token"}).status_code == 401


def test_role_decides_what_the_response_contains(client):
    c = client(customers_script(2))
    normal = ask(c, sign_in(c, "normal")).json()["response"]
    assert normal["type"] == "sql" and "dev" not in normal
    dev = ask(c, sign_in(c, "dev")).json()["response"]
    assert dev["dev"]["llm_calls"]


def test_client_id_is_required(client):
    c = client({})
    headers = sign_in(c)
    headers.pop("X-Client-Id")
    r = ask(c, headers, "hi")
    assert r.status_code == 422 and "error" in r.json()


def test_stream_emits_progress_then_response(client):
    c = client(customers_script())
    with c.stream("POST", "/api/chat/stream", json={"question": "Show all customers."}, headers=sign_in(c)) as r:
        body = "".join(r.iter_text())
    events = [line.split(": ", 1)[1] for line in body.splitlines() if line.startswith("event: ")]
    assert events[0] == "start" and events[-1] == "response" and "node" in events
    final = json.loads(body.strip().split("data: ")[-1])
    assert final["response"]["type"] == "sql" and "dev" not in final["response"]


def test_history_is_private_to_each_account_and_browser(client):
    c = client(customers_script())
    alice = sign_in(c, "normal", BROWSER_A)
    thread = ask(c, alice).json()["thread_id"]
    assert [t["thread_id"] for t in c.get("/api/threads", headers=alice).json()["threads"]] == [thread]
    turns = c.get(f"/api/threads/{thread}", headers=alice).json()["turns"]
    assert turns[0]["question"] == "Show all customers." and turns[0]["response"]["type"] == "sql"
    # Same test account on another browser, or the other account on the same browser: not visible.
    for other in (sign_in(c, "normal", BROWSER_B), sign_in(c, "dev", BROWSER_A)):
        assert c.get("/api/threads", headers=other).json()["threads"] == []
        assert c.get(f"/api/threads/{thread}", headers=other).status_code == 404
        assert ask(c, other, "x", thread_id=thread).status_code == 404


def test_rename_and_delete(client):
    c = client(customers_script())
    h = sign_in(c)
    thread = ask(c, h).json()["thread_id"]
    assert c.patch(f"/api/threads/{thread}", json={"title": "Customer list"}, headers=h).json()["ok"]
    assert c.get("/api/threads", headers=h).json()["threads"][0]["title"] == "Customer list"
    assert c.delete(f"/api/threads/{thread}", headers=h).json()["ok"]
    assert c.get("/api/threads", headers=h).json()["threads"] == []


def test_csv_export_returns_all_rows(client):
    c = client(customers_script())
    h = sign_in(c)
    response = ask(c, h).json()["response"]
    assert response["results"]["row_count"] == 500  # the chat shows a capped preview
    csv = c.get(f"/api/export/{response['request_id']}.csv", headers=h)
    assert csv.status_code == 200 and "attachment" in csv.headers["content-disposition"]
    assert len(csv.text.strip().splitlines()) == 3001  # header + every customer
    other = sign_in(c, "normal", BROWSER_B)
    assert c.get(f"/api/export/{response['request_id']}.csv", headers=other).status_code == 404


def test_rate_limit_applies_to_every_account(client):
    s = get_settings()
    c = client(customers_script(s.rate_limit_per_minute))
    h = sign_in(c, "dev")
    for _ in range(s.rate_limit_per_minute):
        assert ask(c, h).status_code == 200
    blocked = ask(c, h)
    assert blocked.status_code == 429 and "Retry-After" in blocked.headers


def test_dev_endpoints_need_the_dev_account(client):
    c = client({})
    assert c.get("/api/dev/prompts", headers=sign_in(c, "normal")).status_code == 403
    dev = sign_in(c, "dev")
    prompts = c.get("/api/dev/prompts", headers=dev).json()["prompts"]
    assert {p["name"] for p in prompts} >= {"intent_detection", "query_planner", "sql_generation"}
    assert c.get("/api/dev/llm", headers=dev).json()["step_tiers"]["sql_generation"] == "auto"


def test_login_attempts_are_limited(client):
    c = client({})
    codes = [c.post("/api/auth/login", json={"username": "demo", "password": "nope"}).status_code
             for _ in range(get_settings().login_attempts_per_minute + 1)]
    assert codes[-1] == 429 and set(codes[:-1]) == {401}


def test_schema_summary(client):
    c = client({})
    body = c.get("/api/schema", headers=sign_in(c)).json()
    assert [t["name"] for t in body["tables"]] == ["Employees", "Customers", "Products", "Orders", "OrderItems"]
    assert body["suggested_questions"]


def test_accounts_list_never_includes_passwords(client):
    body = client({}).get("/api/auth/accounts").json()
    assert {a["role"] for a in body["accounts"]} == {"normal", "dev"}
    assert "password" not in str(body).lower() and "normal-pass" not in str(body)


def test_run_history_is_dev_only(client):
    c = client(customers_script(2))
    dev = sign_in(c, "dev")
    ask(c, dev)
    ask(c, dev, "Show all customers.")
    assert c.get("/api/dev/runs", headers=sign_in(c, "normal")).status_code == 403
    body = c.get("/api/dev/runs", headers=dev).json()
    assert body["summary"]["runs"] == 2 and body["summary"]["input_tokens"] > 0
    run = body["runs"][0]
    assert run["type"] == "sql" and run["llm_calls"] >= 4 and run["pipeline_ms"] >= 0
