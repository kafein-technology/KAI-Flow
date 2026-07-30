from decimal import Decimal
import os
import pytest

from app.nodes.integrations.mysql_node import MySQLNode


@pytest.fixture()
def node():
    return MySQLNode()


def test_mysql_metadata_exposes_only_workflow_operations(node):
    operation = next(prop for prop in node.metadata.properties if prop.name == "operation")
    assert {option["value"] for option in operation.options} == {
        "delete_table",
        "execute_query",
        "insert",
        "upsert",
        "select",
        "update",
    }
    assert node.metadata.icon["path"] == "icons/mysql.svg"
    assert all(output.name != "rows" for output in node.metadata.outputs)
    assert [output.name for output in node.metadata.outputs] == ["output"]


def test_select_builds_filters_sort_distinct_and_limit(node):
    specs = node._build_queries(
        "select",
        {
            "table": "kai_demo.customers",
            "output_columns": "id,email",
            "select_distinct": True,
            "where": [
                {"column": "status", "condition": "=", "value": "active"},
                {"column": "lifetime_value", "condition": ">=", "value": "100"},
            ],
            "combine_conditions": "AND",
            "sort": [{"column": "created_at", "direction": "DESC"}],
            "return_all": False,
            "limit": 25,
        },
        None,
    )
    assert specs[0].sql == (
        "SELECT DISTINCT `id`, `email` FROM `kai_demo`.`customers` "
        "WHERE `status` = %s AND `lifetime_value` >= %s "
        "ORDER BY `created_at` DESC LIMIT %s"
    )
    assert specs[0].parameters == ["active", 100.0, 25]


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("drop", "DROP TABLE IF EXISTS `workflow_events`"),
        ("truncate", "TRUNCATE TABLE `workflow_events`"),
        ("delete", "DELETE FROM `workflow_events`"),
    ],
)
def test_delete_commands(node, command, expected):
    specs = node._build_queries(
        "delete_table",
        {"table": "workflow_events", "delete_command": command, "where": []},
        None,
    )
    assert specs[0].sql == expected


def test_insert_supports_multiple_rows_and_conflict_skip(node):
    specs = node._build_queries(
        "insert",
        {
            "table": "customers",
            "data_mode": "auto_map",
            "skip_on_conflict": True,
            "priority": "LOW_PRIORITY",
        },
        [
            {"email": "one@example.com", "status": "lead"},
            {"email": "two@example.com", "status": "active"},
        ],
    )
    assert len(specs) == 2
    assert specs[0].sql == "INSERT LOW_PRIORITY IGNORE INTO `customers` (`email`, `status`) VALUES (%s, %s)"
    assert specs[1].parameters == ["two@example.com", "active"]


def test_upsert_excludes_unique_match_column_from_updates(node):
    spec = node._build_queries(
        "upsert",
        {
            "table": "customers",
            "data_mode": "manual",
            "values": {"full_name": "Demo", "status": "active"},
            "match_column": "email",
            "match_value": "demo@example.com",
        },
        None,
    )[0]
    assert "ON DUPLICATE KEY UPDATE `full_name` = %s, `status` = %s" in spec.sql
    assert "`email` = %s" not in spec.sql.split("ON DUPLICATE KEY UPDATE", 1)[1]


def test_update_uses_match_column_but_does_not_change_it(node):
    spec = node._build_queries(
        "update",
        {
            "table": "customers",
            "data_mode": "auto_map",
            "match_column": "email",
        },
        {"email": "demo@example.com", "status": "inactive"},
    )[0]
    assert spec.sql == "UPDATE `customers` SET `status` = %s WHERE `email` = %s"
    assert spec.parameters == ["inactive", "demo@example.com"]


def test_execute_query_replaces_numbered_parameters_but_not_quoted_tokens(node):
    spec = node._build_queries(
        "execute_query",
        {
            "query": "SELECT '$1' literal, * FROM $1:name WHERE status = $2",
            "query_parameters": ["customers", "active"],
        },
        None,
    )[0]
    assert spec.sql == "SELECT '$1' literal, * FROM `customers` WHERE status = %s"
    assert spec.parameters == ["active"]


def test_execute_query_without_parameters_preserves_literal_percent(node):
    spec = node._build_queries(
        "execute_query",
        {
            "query": "DELETE FROM customers WHERE email LIKE 'mysql-suite-%'",
            "query_parameters": [],
        },
        None,
    )[0]

    assert spec.sql == "DELETE FROM customers WHERE email LIKE 'mysql-suite-%'"
    assert spec.parameters == []


def test_serializes_mysql_specific_values(node):
    row = node._serializable_row(
        {"amount": Decimal("12.50"), "huge": 9223372036854775807},
        {"decimal_numbers": False, "large_numbers_output": "text"},
    )
    assert row == {"amount": "12.50", "huge": "9223372036854775807"}


def test_rejects_invalid_where_operator(node):
    with pytest.raises(ValueError, match="Unsupported Select Rows operator"):
        node._build_queries(
            "select",
            {"table": "customers", "where": [{"column": "id", "condition": "IN", "value": [1]}]},
            None,
        )


def test_select_supports_case_sensitive_contains(node):
    spec = node._build_queries(
        "select",
        {
            "table": "customers",
            "where": [{"column": "full_name", "condition": "LIKE BINARY", "value": "%Demo%"}],
            "return_all": True,
        },
        None,
    )[0]
    assert spec.sql == "SELECT * FROM `customers` WHERE `full_name` LIKE BINARY %s"
    assert spec.parameters == ["%Demo%"]


@pytest.mark.skipif(not os.getenv("MYSQL_SMOKE_HOST"), reason="requires the local MySQL demo container")
def test_all_operations_against_local_mysql(node):
    node.credentials = [
        {
            "id": "mysql-smoke",
            "service_type": "mysql",
            "secret": {
                "host": os.environ["MYSQL_SMOKE_HOST"],
                "port": int(os.getenv("MYSQL_SMOKE_PORT", "3306")),
                "database": os.getenv("MYSQL_SMOKE_DATABASE", "kai_demo"),
                "username": os.getenv("MYSQL_SMOKE_USER", "kai"),
                "password": os.getenv("MYSQL_SMOKE_PASSWORD", "kai"),
            },
        }
    ]

    base = {"credential_id": "mysql-smoke", "table": "customers"}
    cleanup = {
        **base,
        "operation": "delete_table",
        "delete_command": "delete",
        "where": [{"column": "email", "condition": "=", "value": "node-smoke@example.com"}],
    }
    node.execute(cleanup, {})

    inserted = node.execute(
        {
            **base,
            "operation": "insert",
            "data_mode": "manual",
            "values": {
                "email": "node-smoke@example.com",
                "full_name": "Node Smoke",
                "status": "lead",
                "country_code": "TR",
            },
        },
        {},
    )
    assert inserted["affected_rows"] == 1

    upserted = node.execute(
        {
            **base,
            "operation": "upsert",
            "data_mode": "manual",
            "match_column": "email",
            "match_value": "node-smoke@example.com",
            "values": {"full_name": "Node Smoke Upserted", "status": "active", "country_code": "TR"},
        },
        {},
    )
    assert upserted["affected_rows"] >= 1

    updated = node.execute(
        {
            **base,
            "operation": "update",
            "data_mode": "manual",
            "match_column": "email",
            "match_value": "node-smoke@example.com",
            "values": {"lifetime_value": 321.45},
        },
        {},
    )
    assert updated["affected_rows"] == 1

    selected = node.execute(
        {
            **base,
            "operation": "select",
            "where": [{"column": "email", "condition": "=", "value": "node-smoke@example.com"}],
            "output_columns": "email,full_name,status,lifetime_value",
            "return_all": True,
        },
        {},
    )
    assert selected["rows"][0]["full_name"] == "Node Smoke Upserted"
    assert selected["rows"][0]["lifetime_value"] == "321.45"

    queried = node.execute(
        {
            "credential_id": "mysql-smoke",
            "operation": "execute_query",
            "query": "SELECT COUNT(*) AS total FROM customers WHERE status = $1",
            "query_parameters": ["active"],
        },
        {},
    )
    assert queried["rows"][0]["total"] >= 1

    deleted = node.execute(cleanup, {})
    assert deleted["affected_rows"] == 1
