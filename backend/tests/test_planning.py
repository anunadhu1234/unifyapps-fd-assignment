"""Plan grounding, model routing, cost estimation and the few-shot examples."""

import pytest

from agent.exec.cost_estimator import CostEstimator
from agent.exec.sqlite_runner import ReadOnlyDatabase
from agent.guardrails.sql_validator import SQLValidator
from agent.knowledge.kb_resolver import get_kb
from agent.llm_client import ModelRouter
from agent.planner.plan_grounding import ground_plan
from agent.retrieval.swarm import example_retriever, run_swarm
from agent.supervisor.dependencies import load_examples
from utils.config import Settings, get_settings


@pytest.fixture(scope="module")
def kb():
    return get_kb()


@pytest.fixture(scope="module")
def db():
    return ReadOnlyDatabase(get_settings().database_path)


def ground(kb, db, tables, select, filters=(), **extra):
    return ground_plan({"restated_request": "x", "tables": tables, "select": select, "filters": list(filters),
                        **extra}, kb, db)


# ── grounding ────────────────────────────────────────────────────────────────


def test_names_are_snapped_and_values_mapped(kb, db):
    g = ground(kb, db, ["customer"], [{"kind": "column", "table": "customers", "column": "first_name"}],
               [{"table": "Customers", "column": "state", "operator": "=", "values": ["California"]}])
    assert g["tables"] == ["Customers"]
    assert g["select"][0]["column"] == "FirstName"
    assert g["filters"][0]["stored_values"] == ["CA"]
    assert not g["issues"]


def test_region_becomes_in_list(kb, db):
    g = ground(kb, db, ["Orders"], [{"kind": "aggregate", "aggregate": "COUNT", "table": "Orders",
                                     "column": "OrderID"}],
               [{"table": "Orders", "column": "ShipState", "operator": "=", "values": ["west coast"]}])
    f = g["filters"][0]
    assert f["operator"] == "IN" and f["stored_values"] == ["CA", "OR", "WA"]


def test_product_names_are_found_in_the_database(kb, db):
    g = ground(kb, db, ["Products"], [{"kind": "column", "table": "Products", "column": "ProductName"}],
               [{"table": "Products", "column": "ProductName", "operator": "=", "values": ["standing desks"]}])
    assert g["filters"][0]["stored_values"] == ["ErgoForm Standing Desk", "Oakridge Standing Desk"]


def test_bridge_tables_and_joins_are_added(kb, db):
    g = ground(kb, db, ["Customers", "Products"], [{"kind": "column", "table": "Products", "column": "Category"}])
    assert set(g["tables"]) == {"Customers", "Orders", "OrderItems", "Products"}
    assert len(g["joins"]) == 3


def test_metric_definition_is_attached(kb, db):
    g = ground(kb, db, ["Products"], [{"kind": "column", "table": "Products", "column": "Category"},
                                      {"kind": "metric", "metric": "revenue"}])
    assert g["metrics"][0]["name"] == "Net Revenue"
    assert "o.Status NOT IN ('Cancelled', 'Returned')" in g["metrics"][0]["default_filters"]


@pytest.mark.parametrize("filters, select, expect", [
    ([], [{"kind": "column", "table": "Employees", "column": "salary_band"}], "no 'Employees.salary_band' field"),
    ([{"table": "Employees", "column": "Department", "operator": "=", "values": ["Marketting"]}],
     [{"kind": "all_columns", "table": "Employees"}], "not a valid Department"),
    ([{"table": "Products", "column": "ProductName", "operator": "=", "values": ["Standng Dsk"]}],
     [{"kind": "all_columns", "table": "Products"}], "Did you mean"),
])
def test_unresolvable_parts_become_clarifications(kb, db, filters, select, expect):
    tables = sorted({s["table"] for s in select} | {f["table"] for f in filters})
    g = ground(kb, db, tables, select, filters)
    assert any(expect in issue for issue in g["issues"])


# ── model routing ────────────────────────────────────────────────────────────


def test_model_routing():
    s = Settings(llm_model_fast="fast/model", llm_model_main="main/model", _env_file=None,
                 model_routes={"generate_explanation": "pinned/model"}, sql_fast_model_max_complexity=1)
    router = ModelRouter(s)
    assert router.route("intent_detection").model == "fast/model"
    assert router.route("query_planner").model == "main/model"
    assert router.route("sql_generation", complexity=0).model == "fast/model"
    assert router.route("sql_generation", complexity=4).model == "main/model"
    assert router.route("sql_repair", attempt=2).model == "main/model"
    assert router.route("sql_generation", complexity=0, attempt=2).model == "main/model"
    assert router.route("generate_explanation").model == "pinned/model"


# ── cost estimation ──────────────────────────────────────────────────────────


def test_cost_estimate_and_index_recommendation(kb, db):
    est = CostEstimator(kb, db).estimate("SELECT * FROM Customers WHERE State = 'CA'")
    assert est.full_scans == ["Customers"]
    assert est.recommendations[0].ddl == "CREATE INDEX idx_customers_state ON Customers (State);"
    keyed = CostEstimator(kb, db).estimate("SELECT * FROM Orders WHERE OrderID = 5")
    assert keyed.level == "low" and not keyed.full_scans and not keyed.recommendations


# ── retrieval and examples ───────────────────────────────────────────────────


def test_swarm_selects_tables_and_examples(kb):
    examples = load_examples(get_settings().knowledge_dir)
    r = run_swarm(kb, examples, "What was the net revenue by product category in 2024?")
    assert set(r["tables"]) == {"Orders", "OrderItems", "Products"}
    assert "Net Revenue" in r["metrics"]
    assert r["examples"][0]["question"].startswith("What was the net revenue by product category")


def test_example_retriever_ignores_unrelated_questions():
    examples = load_examples(get_settings().knowledge_dir)
    assert example_retriever(examples, "Who won the FIFA World Cup?") == []


def test_every_example_is_valid_and_runs(kb, db):
    validator = SQLValidator(kb, db)
    for ex in load_examples(get_settings().knowledge_dir):
        report = validator.validate(ex["sql"])
        assert report.ok, f"{ex['question']}: {report.feedback()}"
        assert db.execute(ex["sql"]).row_count > 0, ex["question"]
