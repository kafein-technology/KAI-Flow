from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Mapping, Sequence
from typing import TYPE_CHECKING, Any, TypeVar

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.documents import Document
from langchain_core.documents.compressor import BaseDocumentCompressor
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseLanguageModel
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from pydantic import ConfigDict

from app.core.state import attach_runtime_execution_context, set_runtime_node_status

if TYPE_CHECKING:
    from app.core.graph_builder.exceptions import NodeExecutionError

KAI_NODE_ERROR_ATTRIBUTE = "_kai_node_execution_error"
KAI_ORIGIN_NODE_METADATA_KEY = "kai_origin_node_id"

T = TypeVar("T")


class RuntimeNodeTracker:
    """Own the runtime lifecycle of one lazy dependency node."""

    def __init__(
        self,
        *,
        node_id: str,
        node_type: str,
        state: Any,
        node_config: Mapping[str, Any] | None = None,
        input_connections: Mapping[str, Any] | None = None,
        output_connections: Mapping[str, Any] | None = None,
    ) -> None:
        self.node_id = node_id
        self.node_type = node_type
        self.state = state
        self.node_config = dict(node_config or {})
        self.input_connections = dict(input_connections or {})
        self.output_connections = dict(output_connections or {})
        self.failed = False

    def pending(self) -> None:
        if not self.failed:
            set_runtime_node_status(self.state, self.node_id, "pending")

    def success(self) -> None:
        if not self.failed:
            set_runtime_node_status(self.state, self.node_id, "success")

    def failure(self, error: BaseException) -> "NodeExecutionError":
        # Kept local to avoid importing the graph_builder package while its
        # node-handler registry is still being initialized.
        from app.core.graph_builder.exceptions import (
            NodeExecutionError,
            find_deepest_node_execution_error,
        )

        nested_error = find_deepest_node_execution_error(error)
        if nested_error is not None and nested_error.node_id != self.node_id:
            # A child dependency owns this failure. This wrapper only propagated it.
            self.success()
            self._attach_node_error(error, nested_error)
            return nested_error

        self.failed = True
        set_runtime_node_status(self.state, self.node_id, "failed")

        if nested_error is not None:
            node_error = nested_error
        else:
            original_error = (
                error if isinstance(error, Exception) else RuntimeError(str(error))
            )
            node_error = NodeExecutionError(
                node_id=self.node_id,
                node_type=self.node_type,
                original_error=original_error,
                node_config=self.node_config,
                input_connections=self.input_connections,
                output_connections=self.output_connections,
            )

        attach_runtime_execution_context(node_error, self.state)
        self._attach_node_error(error, node_error)
        return node_error

    @staticmethod
    def _attach_node_error(
        error: BaseException,
        node_error: "NodeExecutionError",
    ) -> None:
        try:
            setattr(error, KAI_NODE_ERROR_ATTRIBUTE, node_error)
        except Exception:
            # Some third-party exception implementations disallow attributes.
            pass

    def call(self, function, *args, **kwargs):
        self.pending()
        try:
            result = function(*args, **kwargs)
        except BaseException as error:
            node_error = self.failure(error)
            raise node_error from error
        self.success()
        return result

    async def acall(self, function, *args, **kwargs):
        self.pending()
        try:
            result = await function(*args, **kwargs)
        except BaseException as error:
            node_error = self.failure(error)
            raise node_error from error
        self.success()
        return result


class RuntimeNodeStatusCallback(BaseCallbackHandler):
    """Translate LangChain runtime callbacks into KAI node lifecycle events."""

    def __init__(self, tracker: RuntimeNodeTracker) -> None:
        super().__init__()
        self.tracker = tracker

    def on_chat_model_start(self, *args, **kwargs) -> None:
        self.tracker.pending()

    def on_llm_start(self, *args, **kwargs) -> None:
        self.tracker.pending()

    def on_llm_end(self, *args, **kwargs) -> None:
        self.tracker.success()

    def on_llm_error(self, error: BaseException, **kwargs) -> None:
        self.tracker.failure(error)

    def on_tool_start(self, *args, **kwargs) -> None:
        self.tracker.pending()

    def on_tool_end(self, *args, **kwargs) -> None:
        self.tracker.success()

    def on_tool_error(self, error: BaseException, **kwargs) -> None:
        self.tracker.failure(error)

    def on_retriever_start(self, *args, **kwargs) -> None:
        self.tracker.pending()

    def on_retriever_end(self, *args, **kwargs) -> None:
        self.tracker.success()

    def on_retriever_error(self, error: BaseException, **kwargs) -> None:
        self.tracker.failure(error)


class RuntimeTrackedArtifact:
    """Marker used to avoid re-wrapping a child dependency for its parent."""


class RuntimeTrackedEmbeddings(RuntimeTrackedArtifact, Embeddings):
    def __init__(self, delegate: Embeddings, tracker: RuntimeNodeTracker) -> None:
        self.delegate = delegate
        self.tracker = tracker

    def __getattr__(self, name: str) -> Any:
        return getattr(self.delegate, name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.tracker.call(self.delegate.embed_documents, texts)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self.tracker.acall(self.delegate.aembed_documents, texts)

    def embed_query(self, text: str) -> list[float]:
        return self.tracker.call(self.delegate.embed_query, text)

    async def aembed_query(self, text: str) -> list[float]:
        return await self.tracker.acall(self.delegate.aembed_query, text)


class RuntimeTrackedDocumentCompressor(
    RuntimeTrackedArtifact,
    BaseDocumentCompressor,
):
    delegate: BaseDocumentCompressor
    tracker: RuntimeNodeTracker

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def compress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks=None,
    ) -> Sequence[Document]:
        return self.tracker.call(
            self.delegate.compress_documents,
            documents,
            query,
            callbacks=callbacks,
        )

    async def acompress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks=None,
    ) -> Sequence[Document]:
        return await self.tracker.acall(
            self.delegate.acompress_documents,
            documents,
            query,
            callbacks=callbacks,
        )


class RuntimeTrackedRunnable(RuntimeTrackedArtifact, Runnable):
    def __init__(self, delegate: Runnable, tracker: RuntimeNodeTracker) -> None:
        self.delegate = delegate
        self.tracker = tracker

    def __getattr__(self, name: str) -> Any:
        return getattr(self.delegate, name)

    def invoke(self, input: Any, config=None, **kwargs) -> Any:
        return self.tracker.call(
            self.delegate.invoke,
            input,
            config=config,
            **kwargs,
        )

    async def ainvoke(self, input: Any, config=None, **kwargs) -> Any:
        return await self.tracker.acall(
            self.delegate.ainvoke,
            input,
            config=config,
            **kwargs,
        )

    def stream(self, input: Any, config=None, **kwargs) -> Iterator[Any]:
        self.tracker.pending()
        try:
            yield from self.delegate.stream(input, config=config, **kwargs)
        except BaseException as error:
            node_error = self.tracker.failure(error)
            raise node_error from error
        self.tracker.success()

    async def astream(
        self,
        input: Any,
        config=None,
        **kwargs,
    ) -> AsyncIterator[Any]:
        self.tracker.pending()
        try:
            async for chunk in self.delegate.astream(input, config=config, **kwargs):
                yield chunk
        except BaseException as error:
            node_error = self.tracker.failure(error)
            raise node_error from error
        self.tracker.success()

    def bind_tools(self, *args, **kwargs):
        bound = self.delegate.bind_tools(*args, **kwargs)
        return RuntimeTrackedRunnable(bound, self.tracker)

    def with_structured_output(self, *args, **kwargs):
        structured = self.delegate.with_structured_output(*args, **kwargs)
        return RuntimeTrackedRunnable(structured, self.tracker)


def _attach_callback(
    value: BaseLanguageModel | BaseTool | BaseRetriever,
    callback: RuntimeNodeStatusCallback,
) -> Any:
    tracker = callback.tracker
    metadata = dict(getattr(value, "metadata", None) or {})
    existing_origin = metadata.get(KAI_ORIGIN_NODE_METADATA_KEY)

    if existing_origin and existing_origin != tracker.node_id:
        # Preserve the child dependency's ownership when a parent returns it.
        return value

    current_callbacks = getattr(value, "callbacks", None)
    if hasattr(current_callbacks, "handlers") and hasattr(
        current_callbacks, "add_handler"
    ):
        for handler in list(getattr(current_callbacks, "handlers", [])):
            if isinstance(handler, RuntimeNodeStatusCallback):
                try:
                    current_callbacks.remove_handler(handler)
                except Exception:
                    pass
        current_callbacks.add_handler(callback)
    else:
        callbacks = list(current_callbacks or [])
        callbacks = [
            handler
            for handler in callbacks
            if not isinstance(handler, RuntimeNodeStatusCallback)
        ]
        value.callbacks = [*callbacks, callback]

    metadata[KAI_ORIGIN_NODE_METADATA_KEY] = tracker.node_id
    value.metadata = metadata

    tags = list(getattr(value, "tags", None) or [])
    origin_tag = f"kai-node:{tracker.node_id}"
    value.tags = [*tags, origin_tag] if origin_tag not in tags else tags
    return value


def instrument_runtime_artifact(
    value: T,
    *,
    node_id: str,
    node_type: str,
    state: Any,
    node_config: Mapping[str, Any] | None = None,
    input_connections: Mapping[str, Any] | None = None,
    output_connections: Mapping[str, Any] | None = None,
) -> T:
    """Attach runtime ownership to lazy provider artifacts and nested containers."""
    tracker = RuntimeNodeTracker(
        node_id=node_id,
        node_type=node_type,
        state=state,
        node_config=node_config,
        input_connections=input_connections,
        output_connections=output_connections,
    )
    callback = RuntimeNodeStatusCallback(tracker)
    visited: set[int] = set()

    def instrument(item: Any) -> Any:
        if item is None or isinstance(item, RuntimeTrackedArtifact):
            return item

        item_identity = id(item)
        if item_identity in visited:
            return item
        visited.add(item_identity)

        if isinstance(item, Embeddings):
            return RuntimeTrackedEmbeddings(item, tracker)

        if isinstance(item, BaseDocumentCompressor):
            return RuntimeTrackedDocumentCompressor(
                delegate=item,
                tracker=tracker,
            )

        if isinstance(item, (BaseLanguageModel, BaseTool, BaseRetriever)):
            return _attach_callback(item, callback)

        if isinstance(item, dict):
            return {key: instrument(nested) for key, nested in item.items()}

        if isinstance(item, list):
            return [instrument(nested) for nested in item]

        if isinstance(item, tuple):
            return tuple(instrument(nested) for nested in item)

        inner_llm = getattr(item, "llm", None)
        if isinstance(inner_llm, BaseLanguageModel):
            _attach_callback(inner_llm, callback)
            return item

        if isinstance(item, Runnable):
            return RuntimeTrackedRunnable(item, tracker)

        return item

    return instrument(value)
