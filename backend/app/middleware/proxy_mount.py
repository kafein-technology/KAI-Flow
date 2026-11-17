"""Keep ASGI paths consistent when a proxy strips the configured mount.

Uvicorn's --root-path includes the mount in scope.path. FastAPI(root_path=...)
only sets scope.root_path. Support both launch styles so Starlette can build
public slash redirects even when ROOT_PATH is configured on the application.
"""

from starlette.types import ASGIApp, Receive, Scope, Send


class ProxyMountMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in {"http", "websocket"}:
            root = scope.get("root_path", "").rstrip("/")
            path = scope.get("path", "")
            if root and path != root and not path.startswith(root + "/"):
                scope = dict(scope)
                scope["path"] = root + path
                if "raw_path" in scope:
                    scope["raw_path"] = root.encode("utf-8") + scope["raw_path"]
        await self.app(scope, receive, send)
