"""The knowledge base matches the database, and the resolver grounds questions correctly."""

import sqlite3

import pytest

from agent.knowledge.kb_resolver import get_kb
from utils.config import BACKEND_DIR

DB_PATH = BACKEND_DIR / "data" / "company.db"


@pytest.fixture(scope="module")
def kb():
    return get_kb()


# ── the knowledge base agrees with the database ──────────────────────────────


def test_every_database_column_is_documented(kb):
    con = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    for table in kb.tables:
        db_cols = [r[1] for r in con.execute(f'PRAGMA table_info("{table}")')]
        assert list(kb.tables[table]["columns"]) == db_cols
        for col in kb.tables[table]["columns"].values():
            assert col["description"]
    con.close()


def test_metrics_and_terms_were_validated(kb):
    assert kb.metrics and all(m["sql"] and m["value_at_snapshot"] is not None for m in kb.metrics.values())
    assert all("matching_rows_at_snapshot" in g for g in kb.glossary.values() if g.get("sql"))


def test_relationships_come_from_foreign_keys(kb):
    assert {r["id"] for r in kb.relationships} == {
        "Customers.AccountManagerID", "Employees.ManagerID", "Orders.CustomerID",
        "Orders.EmployeeID", "OrderItems.OrderID", "OrderItems.ProductID"}


# ── value grounding ──────────────────────────────────────────────────────────


def values_for(kb, text):
    return {(e["table"], e["column"], e.get("value") or tuple(e.get("values", ())))
            for m in kb.match_values(text) for e in m.entries}


def test_state_name_maps_to_code(kb):
    assert ("Customers", "State", "CA") in values_for(kb, "customers from California")


def test_state_group_maps_to_codes(kb):
    assert ("Orders", "ShipState", ("CA", "OR", "WA")) in values_for(kb, "orders shipped to the West Coast")


def test_lowercase_words_are_not_state_codes(kb):
    assert values_for(kb, "orders placed in or after 2024") == set()
    assert ("Customers", "State", "IN") in values_for(kb, "customers in IN")


def test_synonym_maps_to_stored_value(kb):
    assert ("Orders", "Status", "Cancelled") in values_for(kb, "canceled orders")
    assert ("Customers", "Segment", "Small Business") in values_for(kb, "SMB customers")


def test_longest_phrase_wins(kb):
    phrases = [m.phrase for m in kb.match_values("revenue for the west coast")]
    assert phrases == ["west coast"]


# ── identifier resolution ────────────────────────────────────────────────────


def test_resolve_table_by_synonym(kb):
    assert kb.resolve_table("customer") == "Customers"
    assert kb.resolve_table("ORDERS") == "Orders"
    assert kb.resolve_table("invoices_table") is None


def test_resolve_column_tolerates_case_and_underscores(kb):
    assert kb.resolve_column("hire_date") == [("Employees", "HireDate")]
    assert kb.resolve_column("hiredate") == [("Employees", "HireDate")]
    assert kb.resolve_column("state", ["Customers"]) == [("Customers", "State")]
    assert kb.resolve_column("salary_band") == []


# ── retrieval and join planning ──────────────────────────────────────────────


@pytest.mark.parametrize("question, expected", [
    ("Show all employees hired after January 2024.", {"Employees"}),
    ("Total revenue by product category in 2025", {"Orders", "OrderItems", "Products"}),
    ("Which customers bought standing desks?", {"Customers", "Orders", "OrderItems", "Products"}),
    ("List customers with their account manager", {"Customers", "Employees"}),
    # "products" names the table, not the 'Product' department value ...
    ("Which products have never been ordered?", {"Products", "OrderItems"}),
    # ... but next to its own column name, "Product" is that value.
    ("List employees in the Product department", {"Employees"}),
    ("Headcount in the Sales department", {"Employees"}),
])
def test_relevant_tables(kb, question, expected):
    assert set(kb.relevant_tables(question).tables) == expected


def test_connect_adds_bridge_tables(kb):
    tables, joins = kb.connect(["Customers", "Products"])
    assert set(tables) == {"Customers", "Orders", "OrderItems", "Products"}
    assert len(joins) == 3


def test_connect_prefers_mentioned_relationship(kb):
    _, joins = kb.connect(["Customers", "Employees", "Orders"], {"Orders.EmployeeID"})
    assert "Orders.EmployeeID = Employees.EmployeeID" in joins
    assert "Customers.AccountManagerID = Employees.EmployeeID" not in joins


def test_two_ways_to_link_customers_and_employees(kb):
    ambiguous = kb.ambiguous_links(["Customers", "Employees"])
    assert len(ambiguous) == 1 and len(ambiguous[0]["options"]) == 2


def test_schema_context_is_grounded(kb):
    text = kb.schema_context(["Customers"])
    assert "TABLE Customers" in text and "2-letter state codes" in text
    assert "'Consumer' = Individual shopper" in text
    assert "TABLE Orders" not in text  # only summarised, not detailed
