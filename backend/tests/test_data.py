"""The sample database is consistent and supports the assignment's example questions."""

import sqlite3

import pytest

from utils.config import BACKEND_DIR

DB_PATH = BACKEND_DIR / "data" / "company.db"


@pytest.fixture(scope="module")
def db():
    con = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    yield con
    con.close()


def scalar(db, sql):
    return db.execute(sql).fetchone()[0]


def test_exactly_five_tables(db):
    tables = {r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")}
    assert tables == {"Customers", "Employees", "Products", "Orders", "OrderItems"}


def test_referential_integrity(db):
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    assert scalar(db, "PRAGMA integrity_check") == "ok"


def test_every_order_has_lines(db):
    assert scalar(db, "SELECT COUNT(*) FROM Orders o WHERE NOT EXISTS "
                      "(SELECT 1 FROM OrderItems oi WHERE oi.OrderID = o.OrderID)") == 0


def test_pdf_example_employees_hired_after_jan_2024(db):
    assert scalar(db, "SELECT COUNT(*) FROM Employees WHERE HireDate >= '2024-01-01'") > 0


def test_pdf_example_customers_in_california(db):
    assert scalar(db, "SELECT COUNT(*) FROM Customers WHERE State = 'CA'") > 0
    # State is stored as a code, never the full name — the grounding step depends on this.
    assert scalar(db, "SELECT COUNT(*) FROM Customers WHERE State = 'California'") == 0


def test_status_dates_are_consistent(db):
    assert scalar(db, "SELECT COUNT(*) FROM Orders WHERE Status IN ('Delivered','Returned') "
                      "AND DeliveredDate IS NULL") == 0
    assert scalar(db, "SELECT COUNT(*) FROM Orders WHERE Status IN ('Pending','Processing','Cancelled') "
                      "AND ShippedDate IS NOT NULL") == 0
    assert scalar(db, "SELECT COUNT(*) FROM Orders WHERE Status = 'Returned' "
                      "AND PaymentStatus <> 'Refunded'") == 0


def test_terminated_employees_have_termination_date(db):
    assert scalar(db, "SELECT COUNT(*) FROM Employees WHERE (Status = 'Terminated') "
                      "<> (TerminationDate IS NOT NULL)") == 0


def test_only_the_ceo_has_no_manager(db):
    assert scalar(db, "SELECT COUNT(*) FROM Employees WHERE ManagerID IS NULL") == 1


def test_edge_cases_exist_for_left_join_questions(db):
    assert scalar(db, "SELECT COUNT(*) FROM Customers c WHERE NOT EXISTS "
                      "(SELECT 1 FROM Orders o WHERE o.CustomerID = c.CustomerID)") > 0
    assert scalar(db, "SELECT COUNT(*) FROM Products p WHERE NOT EXISTS "
                      "(SELECT 1 FROM OrderItems oi WHERE oi.ProductID = p.ProductID)") > 0


def test_sale_price_differs_from_list_price(db):
    # Order lines carry the historical price, so revenue must use OrderItems.UnitPrice.
    assert scalar(db, "SELECT COUNT(*) FROM OrderItems oi JOIN Products p ON p.ProductID = oi.ProductID "
                      "WHERE ABS(oi.UnitPrice - p.UnitPrice) > 0.01") > 0
