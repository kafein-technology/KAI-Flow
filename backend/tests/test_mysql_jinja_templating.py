from app.core.graph_builder.node_executor import NodeExecutor
from app.core.graph_builder.types import GraphNodeInstance
from app.core.state import FlowState
from app.core.templating import apply_jinja_to_inputs
from app.nodes.integrations.mysql_node import MySQLNode
from app.nodes.text_processing.string_input_node import StringInputNode


def test_jinja_resolves_mysql_table_property_from_upstream_string_input():
    source_id = "StringInputNode__mysql_jinja_table"
    source = StringInputNode()
    source.user_data = {"name": "mysql_jinja_table_source", "text_input": "customers"}
    source_graph_node = GraphNodeInstance(
        id=source_id,
        type="StringInputNode",
        node_instance=source,
        metadata={},
        user_data=source.user_data,
    )

    node = MySQLNode()
    node.user_data = {
        "name": "mysql_jinja_select",
        "operation": "select",
        "table": "{{mysql_jinja_table_source}}",
        "return_all": True,
    }
    target_graph_node = GraphNodeInstance(
        id="MySQL__mysql_jinja_select",
        type="MySQL",
        node_instance=node,
        metadata={},
        user_data=node.user_data,
    )
    state = FlowState(
        node_outputs={
            source_id: {
                "nodeId": source_id,
                "success": True,
                "output": "customers",
            }
        }
    )
    executor = NodeExecutor()
    executor._nodes_registry = {source_id: source_graph_node}

    inputs = executor.extract_user_inputs_for_processor(target_graph_node, state)
    rendered = apply_jinja_to_inputs(
        inputs, state, target_graph_node.id, executor._nodes_registry
    )

    assert rendered["table"] == "customers"
    assert node._build_queries("select", rendered, None)[0].sql == "SELECT * FROM `customers`"
