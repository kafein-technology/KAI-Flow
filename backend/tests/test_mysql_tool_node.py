import json

import pytest
from langchain_core.tools import BaseTool

from app.nodes.integrations.mysql_tool_node import (
    MySQLToolNode,
    _case_insensitive_predicates,
    _referenced_tables,
    _statement_command,
    _validate_single_statement,
)


@pytest.fixture()
def tool_node():
    tool = MySQLToolNode()
    tool.user_data = {"credential_id": "mysql-credential"}
    tool.credentials = [{
        "id": "mysql-credential",
        "service_type": "mysql",
        "secret": {"host": "localhost", "database": "kai_demo", "username": "kai", "password": "kai"},
    }]
    return tool


def test_mysql_tool_metadata_has_only_tool_output(tool_node):
    assert tool_node.metadata.node_type.value == "provider"
    assert [output.name for output in tool_node.metadata.outputs] == ["tool"]
    assert tool_node.metadata.outputs[0].type == "BaseTool"
    property_names = {prop.name for prop in tool_node.metadata.properties}
    assert {
        "allow_read", "allow_insert", "allow_update", "allow_delete",
        "return_all_rows", "max_rows", "allowed_tables",
    } <= property_names
    # The WHERE guard is unconditional, so it must not be exposed as a toggle.
    assert "require_where_clause" not in property_names
    allow_read = next(prop for prop in tool_node.metadata.properties if prop.name == "allow_read")
    assert allow_read.default is True


def test_mysql_tool_returns_native_agent_tool_shape(tool_node):
    result = tool_node.execute()
    assert isinstance(result["mysql_database"]["tool"], BaseTool)
    assert result["mysql_database"]["tool"].name == "mysql_database"


def test_mysql_tool_rejects_writes_by_default_without_opening_database(tool_node):
    result = json.loads(tool_node.execute()["mysql_database"]["tool"].invoke("DELETE FROM customers"))
    assert "not allowed" in result["error"]


@pytest.mark.parametrize("query", ["SELECT 1; DROP TABLE customers", "SELECT 1; -- hidden", "SELECT 1 /* hidden */"])
def test_mysql_tool_rejects_stacked_or_commented_queries(query):
    with pytest.raises(ValueError):
        _validate_single_statement(query)


def test_mysql_tool_classifies_cte_by_effective_command():
    assert _statement_command("WITH recent AS (SELECT * FROM customers) SELECT * FROM recent") == "SELECT"
    assert _statement_command("WITH old AS (SELECT id FROM customers) DELETE FROM customers WHERE id IN (SELECT id FROM old)") == "DELETE"


def test_mysql_tool_finds_qualified_tables_without_treating_cte_as_a_table():
    tables = _referenced_tables(
        "WITH recent AS (SELECT * FROM kai_demo.customers) "
        "SELECT * FROM recent JOIN orders ON recent.id = orders.customer_id"
    )
    assert "kai_demo.customers" in tables
    assert "customers" in tables
    assert "orders" in tables
    assert "recent" not in tables


def test_mysql_tool_table_allowlist_rejects_other_tables_without_opening_database(tool_node):
    tool_node.user_data["allowed_tables"] = "customers"
    result = json.loads(tool_node.execute()["mysql_database"]["tool"].invoke("SELECT * FROM orders"))
    assert result == {"error": "Table access denied: orders"}


def test_mysql_tool_table_allowlist_rejects_unscoped_metadata_queries(tool_node):
    tool_node.user_data["allowed_tables"] = "customers"
    result = json.loads(tool_node.execute()["mysql_database"]["tool"].invoke("SHOW TABLES"))
    assert result == {"error": "Could not verify table access for this query."}


def test_mysql_tool_requires_where_clause_for_delete(tool_node):
    tool_node.user_data["allow_delete"] = True
    result = json.loads(tool_node.execute()["mysql_database"]["tool"].invoke("DELETE FROM customers"))
    assert "WHERE clause" in result["error"]


def test_mysql_tool_where_clause_requirement_cannot_be_switched_off(tool_node):
    tool_node.user_data["allow_update"] = True
    tool_node.user_data["require_where_clause"] = False
    result = json.loads(
        tool_node.execute()["mysql_database"]["tool"].invoke("UPDATE customers SET city = 'Bursa'")
    )
    assert "WHERE clause" in result["error"]


def test_where_text_comparisons_ignore_letter_case():
    rewritten = _case_insensitive_predicates(
        "UPDATE customers SET city = 'Bursa' WHERE city = 'ankara'"
    )
    # The assignment keeps the value the user typed, only the predicate is folded.
    assert rewritten == (
        "UPDATE customers SET city = 'Bursa' WHERE LOWER(city) = LOWER('ankara')"
    )


def test_where_rewrite_covers_like_not_equal_and_in_lists():
    assert _case_insensitive_predicates(
        "SELECT * FROM customers WHERE full_name LIKE '%demo%'"
    ) == "SELECT * FROM customers WHERE LOWER(full_name) LIKE LOWER('%demo%')"
    assert _case_insensitive_predicates(
        "DELETE FROM customers WHERE `city` != 'Ankara'"
    ) == "DELETE FROM customers WHERE LOWER(`city`) != LOWER('Ankara')"
    assert _case_insensitive_predicates(
        "SELECT * FROM customers WHERE c.city IN ('ankara', 'BURSA')"
    ) == "SELECT * FROM customers WHERE LOWER(c.city) IN (LOWER('ankara'), LOWER('BURSA'))"


def test_where_rewrite_leaves_dates_numbers_and_inserts_alone():
    date_query = "SELECT * FROM orders WHERE ordered_at = '2026-01-01 10:00:00'"
    assert _case_insensitive_predicates(date_query) == date_query
    numeric_query = "SELECT * FROM orders WHERE total_amount >= '100'"
    assert _case_insensitive_predicates(numeric_query) == numeric_query
    insert_query = "INSERT INTO customers (city) VALUES ('Ankara')"
    assert _case_insensitive_predicates(insert_query) == insert_query
