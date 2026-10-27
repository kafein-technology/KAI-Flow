import json

from app.core.git_provider_api import GitProviderClient, GitProviderError
from app.nodes.base import BaseNode, NodeInput, NodeOutput, NodeProperty, NodePropertyType, NodeType


GITHUB_OPERATIONS = [{"value": "repository.get", "label": "Get Repository"}] + [
    {"value": f"{resource}.{operation}", "label": f"{operation.title()} {label}"}
    for resource, label in (("commit", "Commit"), ("issue", "Issue"), ("pull_request", "Pull Request"))
    for operation in (["list", "get"] if resource == "commit" else ["list", "get", "create", "update", "comment"])
]


class GitHubNode(BaseNode):
    provider = "github"

    def __init__(self):
        super().__init__()
        name = "GitHub"
        pr = "Pull Request"
        properties = [
            NodeProperty(name="credential_id", displayName="Credential", type=NodePropertyType.CREDENTIAL_SELECT,
                         serviceType=self.provider, description=f"Select or create a {name} access token credential."),
            NodeProperty(name="repository", displayName="Repository",
                         type=NodePropertyType.TEXT, placeholder="owner/repository"),
            NodeProperty(name="operation", displayName="Operation", type=NodePropertyType.SELECT, default="repository.get",
                         options=GITHUB_OPERATIONS),
        ]
        for field, label, kind in [("number", "Issue / PR Number", NodePropertyType.NUMBER),
                                   ("commit_sha", "Commit SHA / Ref", NodePropertyType.TEXT),
                                   ("title", "Title", NodePropertyType.TEXT),
                                   ("body", "Description", NodePropertyType.TEXT_AREA),
                                   ("comment", "Comment", NodePropertyType.TEXT_AREA),
                                   ("head", "Source Branch", NodePropertyType.TEXT),
                                   ("base", "Target Branch", NodePropertyType.TEXT),
                                   ("state", "State Filter / State", NodePropertyType.TEXT)]:
            properties.append(NodeProperty(name=field, displayName=label, type=kind, required=False))
        properties += [
            NodeProperty(name="additional_fields", displayName="Additional Fields (JSON)", type=NodePropertyType.JSON_EDITOR,
                         required=False, default="{}", description="Operation fields such as labels, assignees or draft. Connected JSON input can also supply operation fields."),
            NodeProperty(name="page", displayName="Page", type=NodePropertyType.NUMBER, default=1, min=1, required=False),
            NodeProperty(name="per_page", displayName="Results per Page", type=NodePropertyType.NUMBER, default=30, min=1, max=100, required=False),
            NodeProperty(name="timeout", displayName="Timeout (seconds)", type=NodePropertyType.NUMBER, default=30, min=5, max=120, required=False),
        ]
        self._metadata = dict(name=name, display_name=name, description=f"Read repositories and commits; manage issues and {pr.lower()}s with a saved credential.",
                              category="Integrations", node_type=NodeType.PROCESSOR,
                              icon={"name": self.provider, "path": f"icons/{self.provider}.svg", "alt": name},
                              colors=["slate-400", "orange-500"],
                              inputs=[NodeInput(name="input", type="any", description="Connected JSON operation fields", required=False, is_connection=True)],
                              outputs=[NodeOutput(name="output", type="json", description="Git provider API result and pagination", is_connection=True)], properties=properties)

    async def execute(self, inputs, connected_nodes=None, **kwargs):
        credential = self.get_credential(inputs.get("credential_id"))
        if not credential or credential.get("service_type") != self.provider:
            raise GitProviderError(f"Select a valid {self.provider.title()} credential.")
        extra = inputs.get("additional_fields") or {}
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except ValueError:
                raise GitProviderError("Additional fields must be a JSON object.") from None
        if not isinstance(extra, dict):
            raise GitProviderError("Additional fields must be a JSON object.")
        connected = (connected_nodes or {}).get("input", inputs.get("input", {}))
        if isinstance(connected, dict) and isinstance(connected.get("output"), dict):
            connected = connected["output"]
        values = {**(connected if isinstance(connected, dict) else {}), **extra,
                  **{k: v for k, v in inputs.items() if v not in (None, "")}}
        client = GitProviderClient(self.provider, credential.get("secret", {}), inputs.get("timeout", 30))
        return {"output": await client.action(values)}
