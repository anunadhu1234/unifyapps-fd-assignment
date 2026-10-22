"""The deterministic SQL validator (requirement 3.2 and guardrails)."""

import pytest

from agent.exec.sqlite_runner import ReadOnlyDatabase
from agent.guardrails.sql_validator import SQLValidator
from agent.knowledge.kb_resolver import get_kb
from utils.config import get_settings


@pytest.fixture(scope="module")
def validator():
    return SQLValidator(get_kb(), ReadOnlyDatabase(get_settings().database_path))


def codes(report):
    return [f.code for f in report.findings if f.severity == "error"]


@pytest.mark.parametrize("sql", [
    "SELECT * FROM Employees WHERE HireDate >= '2024-01-01';",
    "SELECT c.FirstName, SUM(oi.Quantity * oi.UnitPrice) AS revenue FROM Customers c "
    "JOIN Orders o ON o.CustomerID = c.CustomerID JOIN OrderItems oi ON oi.OrderID = o.OrderID "
    "GROUP BY c.CustomerID ORDER BY revenue DESC LIMIT 5",
    "WITH t AS (SELECT CustomerID, COUNT(*) AS n FROM Orders GROUP BY CustomerID) "
    "SELECT c.FirstName, t.n FROM t JOIN Customers c ON c.CustomerID = t.CustomerID",
    "SELECT e.FirstName, m.FirstName AS manager FROM Employees e LEFT JOIN Employees m ON m.EmployeeID = e.ManagerID",
    "SELECT Segment, COUNT(*) AS n FROM Customers GROUP BY Segment ORDER BY n DESC",
    "SELECT p.ProductName FROM Products p WHERE NOT EXISTS "
    "(SELECT 1 FROM OrderItems oi WHERE oi.ProductID = p.ProductID)",
    "SELECT State FROM Customers UNION SELECT ShipState FROM Orders",
])
def test_valid_queries_pass(validator, sql):
    report = validator.validate(sql)
    assert report.ok, report.feedback()


@pytest.mark.parametrize("sql, code", [
    ("DELETE FROM Customers", "sql.not_read_only"),
    ("UPDATE Products SET UnitPrice = 0", "sql.not_read_only"),
    ("INSERT INTO Customers (CustomerID) VALUES (1)", "sql.not_read_only"),
    ("DROP TABLE Orders", "sql.not_read_only"),
    ("ALTER TABLE Orders ADD COLUMN x INT", "sql.not_read_only"),
    ("TRUNCATE TABLE Orders", "sql.not_read_only"),
    ("SELECT 1; DROP TABLE Customers", "sql.multiple_statements"),
    ("PRAGMA table_info(Customers)", "sql.not_read_only"),
    ("SELECT load_extension('evil')", "sql.not_read_only"),
])
def test_writes_are_blocked(validator, sql, code):
    report = validator.validate(sql)
    assert code in codes(report)
    assert report.blocked_write


def test_unknown_table(validator):
    report = validator.validate("SELECT * FROM Invoices")
    assert codes(report) == ["sql.table.unknown"]


def test_unknown_column_gets_suggestion(validator):
    report = validator.validate("SELECT hire_date FROM Employees")
    assert codes(report) == ["sql.column.unknown"]
    assert "Employees.HireDate" in report.findings[0].hint


def test_column_from_wrong_table(validator):
    report = validator.validate("SELECT FirstName FROM Customers ORDER BY OrderDate")
    assert codes(report) == ["sql.column.unknown"]


@pytest.mark.parametrize("sql, hint", [
    ("SELECT * FROM Customers WHERE State = 'California'", "'CA'"),
    ("SELECT * FROM Orders WHERE Status = 'Canceled'", "'Cancelled'"),
    ("SELECT * FROM Customers WHERE Segment = 'corporate'", "'Corporate'"),
    ("SELECT * FROM Customers WHERE State IN ('CA', 'Texas')", "'TX'"),
])
def test_values_must_be_stored_values(validator, sql, hint):
    report = validator.validate(sql)
    assert codes(report) == ["sql.value.unknown"]
    assert hint in report.findings[0].hint


def test_hallucinated_join_is_rejected(validator):
    report = validator.validate("SELECT * FROM Orders o JOIN Customers c ON o.EmployeeID = c.CustomerID")
    assert codes(report) == ["sql.join.invalid"]
    assert "Orders.CustomerID = Customers.CustomerID" in report.findings[0].hint


def test_cartesian_join_is_a_warning(validator):
    report = validator.validate("SELECT * FROM Customers c, Orders o")
    assert report.ok and [f.code for f in report.findings] == ["sql.join.cartesian"]


def test_syntax_error(validator):
    assert codes(validator.validate("SELECT * FROM Customers WHERE")) == ["sql.syntax"]


def test_plan_filter_must_be_applied(validator):
    report = validator.validate("SELECT * FROM Customers",
                                plan_filters=[{"table": "Customers", "column": "State", "operator": "=",
                                               "values": ["CA"]}])
    assert codes(report) == ["sql.plan.filter_missing"]


def test_markdown_fences_and_semicolon_are_stripped(validator):
    report = validator.validate("```sql\nSELECT * FROM Customers;\n```")
    assert report.ok and report.sql == "SELECT * FROM Customers"
