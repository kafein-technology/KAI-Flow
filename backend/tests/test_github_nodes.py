"""Focused GitHub node contracts; all API and model calls stay offline."""

import asyncio
import importlib
import json
from pathlib import Path
import sys
import types

import httpx
import pytest
from cryptography.fernet import Fernet
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parents[1]))
importlib.import_module("app.models")


@pytest.fixture
def nodes(monkeypatch):
    monkeypatch.setenv("DISABLE_DATABASE", "true")
    monkeypatch.setenv("LANGSMITH_TRACING_ENABLED", "false")
    monkeypatch.setenv("ENABLE_WORKFLOW_TRACING", "false")
    monkeypatch.setenv("CREDENTIAL_MASTER_KEY", Fernet.generate_key().decode())
    root = Path(__file__).parents[1] / "app" / "nodes"
    # Load the real node base without importing unrelated optional integrations.
    for name, path in (("app.nodes", root), ("app.nodes.tools", root / "tools"),
                       ("app.nodes.triggers", root / "triggers")):
        package = types.ModuleType(name)
        package.__path__ = [str(path)]
        monkeypatch.setitem(sys.modules, name, package)
    from app.nodes.base import BaseNode, NodeMetadata

    sys.modules["app.nodes"].BaseNode = BaseNode
    sys.modules["app.nodes"].NodeMetadata = NodeMetadata
    api = importlib.import_module("app.nodes.integrations.github_node")
    tool = importlib.import_module("app.nodes.tools.github_tool")
    return types.SimpleNamespace(api=api, tool=tool)


@pytest.fixture
def http_mock(monkeypatch):
    requests = []
    response = {"status": 200, "data": {"number": 7, "title": "Example", "state": "open",
                "html_url": "https://github.com/team/repo/issues/7"}, "headers": {}}
    real_client = httpx.AsyncClient

    def handler(request):
        requests.append(request)
        return httpx.Response(response["status"], json=response["data"], headers=response["headers"])

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    return requests, response


def credential():
    return {"id": "chosen", "service_type": "header_auth",
            "secret": {"header_name": "Authorization", "header_value": "Bearer never-echo-this"}}


@pytest.fixture
def tool_node(nodes):
    node = nodes.tool.GitHubToolNode()
    node.user_data = {"credential_id": "chosen", "repository": "team/repo"}
    node.credentials = [credential()]
    return node


@pytest.mark.parametrize("operation,method,suffix", [
    ("repository.get", "GET", ""), ("commit.list", "GET", "/commits"),
    ("commit.get", "GET", "/commits/main"), ("issue.list", "GET", "/issues"),
    ("issue.get", "GET", "/issues/7"), ("issue.create", "POST", "/issues"),
    ("issue.update", "PATCH", "/issues/7"), ("issue.comment", "POST", "/issues/7/comments"),
    ("pull_request.list", "GET", "/pulls"), ("pull_request.get", "GET", "/pulls/7"),
    ("pull_request.create", "POST", "/pulls"), ("pull_request.update", "PATCH", "/pulls/7"),
    ("pull_request.comment", "POST", "/issues/7/comments"),
])
def test_action_api_contract(nodes, http_mock, operation, method, suffix):
    requests, _ = http_mock
    values = {"repository": "team/repo", "operation": operation, "number": 7, "commit_sha": "main",
              "title": "Example", "body": "Body", "comment": "Comment", "head": "feature", "base": "main"}
    result = asyncio.run(nodes.api.GitHubClient({"access_token": "never-echo-this"}).action(values))
    assert result["success"] and result["provider"] == "github" and result["operation"] == operation
    assert requests[0].method == method and requests[0].url.path == "/repos/team/repo" + suffix
    assert requests[0].headers["Authorization"] == "Bearer never-echo-this"
    if operation.endswith("comment"):
        assert json.loads(requests[0].content) == {"body": "Comment"}


def test_action_credentials_and_connected_input(nodes, http_mock):
    node = nodes.api.GitHubNode()
    node.credentials = [credential()]
    properties = {prop.name: prop for prop in node.metadata.properties}
    assert properties["credential_id"].serviceType == "header_auth"
    assert not {"app_id", "instance_id", "installation_id", "webhook_url", "webhook_secret"} & properties.keys()
    result = asyncio.run(node.execute({"credential_id": "chosen", "repository": "team/repo", "operation": "issue.create"},
                                      {"input": {"title": "Connected title"}}))
    assert result["output"]["success"]
    assert json.loads(http_mock[0][0].content) == {"title": "Connected title"}
    with pytest.raises(nodes.api.GitHubError):
        asyncio.run(node.execute({"credential_id": "missing", "repository": "team/repo"}))


@pytest.mark.parametrize("change", [{"repository": "../private"}, {"operation": "issue.delete"},
                                   {"per_page": 101}, {"title": ""}, {"timeout": True}])
def test_invalid_action_makes_no_requests(nodes, http_mock, change):
    node = nodes.api.GitHubNode()
    node.credentials = [credential()]
    with pytest.raises(nodes.api.GitHubError):
        asyncio.run(node.execute({"credential_id": "chosen", "repository": "team/repo",
                                 "operation": "issue.create", "title": "Example", **change}))
    assert not http_mock[0]


@pytest.mark.parametrize("extra", ["{bad", "[1]", 7])
def test_invalid_additional_fields(nodes, http_mock, extra):
    node = nodes.api.GitHubNode()
    node.credentials = [credential()]
    with pytest.raises(nodes.api.GitHubError):
        asyncio.run(node.execute({"credential_id": "chosen", "repository": "team/repo", "additional_fields": extra}))
    assert not http_mock[0]


@pytest.mark.parametrize("url", ["http://github.com", "https://untrusted.test", "https://u:p@github.com",
                                "https://github.com/?secret=value", "https://github.com:8443", "https://github.com/../admin"])
def test_server_boundaries(nodes, url):
    with pytest.raises(nodes.api.GitHubError):
        nodes.api.GitHubClient({"access_token": "test-token", "server_url": url})


def test_enterprise_server_allowlist(nodes, monkeypatch):
    monkeypatch.setenv("GIT_PROVIDER_ALLOWED_HOSTS", "git.company.test")
    client = nodes.api.GitHubClient({"access_token": "test-token", "server_url": "https://git.company.test"})
    assert client.base_url == "https://git.company.test/api/v3"


@pytest.mark.parametrize("token", ["", None, "has whitespace"])
def test_invalid_tokens(nodes, http_mock, token):
    with pytest.raises(nodes.api.GitHubError):
        nodes.api.GitHubClient({"access_token": token})
    assert not http_mock[0]


@pytest.mark.parametrize("status", [302, 401, 403, 429, 500])
def test_provider_errors_do_not_expose_secrets(nodes, http_mock, status):
    http_mock[1].update(status=status, data={"message": "never-echo-this"},
                        headers={"Location": "https://untrusted.test"})
    with pytest.raises(nodes.api.GitHubError, match=str(status)) as error:
        asyncio.run(nodes.api.GitHubClient({"access_token": "never-echo-this"}).action({"repository": "team/repo"}))
    assert "never-echo-this" not in str(error.value)
    assert len(http_mock[0]) == 1


def test_tool_is_read_only_and_fixed_to_selected_repository(nodes, tool_node, http_mock):
    read, = tool_node.execute()["tools"]
    assert read.name == "github_read" and not http_mock[0]
    for arguments in ({"operation": "issue.create"}, {"operation": "repository.get", "repository": "other/private"},
                      {"operation": "repository.get", "credential_id": "other"},
                      {"operation": "issue.list", "per_page": 21}, {"operation": "issue.get", "number": 0}):
        with pytest.raises(ValidationError):
            read.invoke(arguments)
    assert not http_mock[0]


def test_tool_pagination_filters_prs_and_private_fields(tool_node, http_mock):
    requests, response = http_mock
    response.update(data=[{"number": 7, "title": "Issue", "temp_clone_token": "private-token"},
                          {"number": 8, "pull_request": {}}],
                    headers={"Link": '<https://api.github.com/repos/team/repo/issues?page=2>; rel="next"'})
    result = tool_node.execute()["tools"][0].invoke({"operation": "issue.list"})
    assert result["data"] == [{"number": 7, "title": "Issue"}]
    assert result["next_page"] == 2 and result["has_next_page"]
    assert requests[0].url.params["per_page"] == "10"
    response.update(data={"head": {"ref": "feature", "repo": {"temp_clone_token": "private-token"}}, "number": 7})
    result = tool_node.execute()["tools"][0].invoke({"operation": "pull_request.get", "number": 7})
    assert result["data"]["head"] == {"ref": "feature"}
    assert "private-token" not in json.dumps(result)


def test_explicit_issue_creation_uses_selected_repository(tool_node, http_mock):
    tool_node.user_data["allow_issue_creation"] = True
    http_mock[1]["data"]["temp_clone_token"] = "private-token"
    create = tool_node.execute()["tools"][1]
    result = create.invoke({"title": "Chat issue", "body": "Created from chat"})
    assert http_mock[0][0].method == "POST" and http_mock[0][0].url.path == "/repos/team/repo/issues"
    assert json.loads(http_mock[0][0].content) == {"title": "Chat issue", "body": "Created from chat"}
    assert result["number"] == 7 and "private-token" not in json.dumps(result)


@pytest.mark.parametrize("change", [{"credential_id": "missing"}, {"repository": "../private"}, {"allow_issue_creation": "false"}])
def test_invalid_tool_configuration(nodes, tool_node, http_mock, change):
    tool_node.user_data.update(change)
    with pytest.raises(nodes.api.GitHubError):
        tool_node.execute()
    assert not http_mock[0]


@pytest.mark.parametrize("service,secret", [("gitlab", {"access_token": "test-token"}),
                                          ("header_auth", {"header_name": "X-Custom", "header_value": "test-token"})])
def test_wrong_credential_is_rejected(nodes, tool_node, http_mock, service, secret):
    tool_node.credentials = [{"id": "chosen", "service_type": service, "secret": secret}]
    with pytest.raises(nodes.api.GitHubError):
        tool_node.execute()
    assert not http_mock[0]


def test_existing_github_token_credential_still_works(tool_node, http_mock):
    tool_node.credentials = [{"id": "chosen", "service_type": "github", "secret": {"access_token": "test-token"}}]
    tool_node.execute()["tools"][0].invoke({"operation": "repository.get"})
    assert http_mock[0][0].headers["Authorization"] == "Bearer test-token"


def test_existing_registry_discovers_both_nodes(nodes, monkeypatch):
    from app.core import node_registry as module

    root = Path(__file__).parents[1] / "app" / "nodes"
    monkeypatch.setattr(module.os, "walk", lambda path: [
        (str(root / "integrations"), [], ["github_node.py"]), (str(root / "tools"), [], ["github_tool.py"])])
    registry = module.NodeRegistry()
    registry.discover_nodes()
    assert registry.get_node("GitHub") is nodes.api.GitHubNode
    assert registry.get_node("GitHubTool") is nodes.tool.GitHubToolNode
    assert {node.name for node in registry.get_all_nodes()} == {"GitHub", "GitHubTool"}


def test_action_runs_in_existing_workflow_engine(nodes, http_mock):
    from app.core.graph_builder import GraphBuilder
    from app.nodes.default.start_node import StartNode
    from app.nodes.default.end_node import EndNode

    builder = GraphBuilder({"StartNode": StartNode, "EndNode": EndNode, "GitHub": nodes.api.GitHubNode})
    builder.build_from_flow({"nodes": [
        {"id": "start", "type": "StartNode", "data": {}},
        {"id": "github", "type": "GitHub", "data": {"credential_id": "chosen", "repository": "team/repo"}},
        {"id": "end", "type": "EndNode", "data": {}}],
        "edges": [
            {"id": "start-github", "source": "start", "target": "github", "sourceHandle": "output", "targetHandle": "input"},
            {"id": "github-end", "source": "github", "target": "end", "sourceHandle": "output", "targetHandle": "target"}]})
    builder.nodes["github"].node_instance.credentials = [credential()]
    result = asyncio.run(builder.execute({"input": "Read repository"}))
    assert not result["state"]["errors"]
    assert "github" in result["state"]["executed_nodes"] and len(http_mock[0]) == 1


class OfflineChatModel(BaseChatModel):
    create_issue: bool = False

    @property
    def _llm_type(self):
        return "offline-github-node-test"

    def bind_tools(self, tools, **kwargs):
        expected = "github_create_issue" if self.create_issue else "github_read"
        assert expected in {tool.name for tool in tools}
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if isinstance(messages[-1], ToolMessage):
            result = json.loads(messages[-1].content)
            assert result["success"]
            issue = result if self.create_issue else result["data"]
            reply = AIMessage(content=f"Issue #{issue['number']}: {issue['html_url']}")
        else:
            arguments = {"title": "Chat issue", "body": "Created from chat"} if self.create_issue else {"operation": "issue.get", "number": 7}
            reply = AIMessage(content="", tool_calls=[{"name": "github_create_issue" if self.create_issue else "github_read",
                                                       "args": arguments, "id": "test-github-call", "type": "tool_call"}])
        return ChatResult(generations=[ChatGeneration(message=reply)])


@pytest.mark.parametrize("create_issue", [False, True])
def test_existing_agent_calls_github_from_chat(nodes, tool_node, http_mock, create_issue):
    from app.core.graph_builder import GraphBuilder
    from app.nodes.base import ProviderNode, NodeOutput, NodeType
    from app.nodes.agents.react_agent import ReactAgentNode
    from app.nodes.default.start_node import StartNode
    from app.nodes.default.end_node import EndNode

    class OfflineModelNode(ProviderNode):
        def __init__(self):
            super().__init__()
            self._metadata = {"name": "OfflineModel", "description": "Offline tool-calling model.", "category": "LLM",
                              "node_type": NodeType.PROVIDER, "inputs": [], "properties": [],
                              "outputs": [NodeOutput(name="llm", type="BaseLanguageModel", description="Offline model", is_connection=True)]}

        def execute(self, **kwargs):
            return OfflineChatModel(create_issue=create_issue)

    flow = {"nodes": [{"id": "start", "type": "StartNode", "data": {}},
                      {"id": "agent", "type": "Agent", "data": {}},
                      {"id": "end", "type": "EndNode", "data": {}},
                      {"id": "model", "type": "OfflineModel", "data": {}},
                      {"id": "github", "type": "GitHubTool", "data": {**tool_node.user_data, "allow_issue_creation": create_issue}}],
            "edges": [{"id": f"{source}-{target}-{target_handle}", "source": source, "target": target,
                       "sourceHandle": source_handle, "targetHandle": target_handle}
                      for source, source_handle, target, target_handle in [
                          ("start", "output", "agent", "input"), ("model", "llm", "agent", "llm"),
                          ("github", "tools", "agent", "tools"), ("agent", "output", "end", "target")]]}
    builder = GraphBuilder({"StartNode": StartNode, "EndNode": EndNode, "Agent": ReactAgentNode,
                            "GitHubTool": nodes.tool.GitHubToolNode, "OfflineModel": OfflineModelNode})
    builder.build_from_flow(flow)
    builder.nodes["github"].node_instance.credentials = tool_node.credentials
    result = asyncio.run(builder.execute({"input": "Create an issue" if create_issue else "Read issue 7"}))
    assert not result["state"]["errors"]
    assert "Issue #7" in result["state"]["last_output"]
    assert "https://github.com/team/repo/issues/7" in result["state"]["last_output"]
    assert len(http_mock[0]) == 1 and http_mock[0][0].method == ("POST" if create_issue else "GET")
