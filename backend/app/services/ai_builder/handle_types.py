from enum import Enum
from typing import Set, Dict


class HandleType(str, Enum):
    LLM = "languagemodel"
    EMBEDDINGS = "embeddings"
    MEMORY = "memory"
    TOOL = "tool"
    DOCUMENT = "document"
    DATA = "data"
    ANY = "any"


# ─── Type Resolution Table ───
# Map node metadata raw string to HandleType enum
_TYPE_ALIASES: Dict[str, HandleType] = {
    # LLM aliases
    "baselanguagemodel": HandleType.LLM,
    "languagemodel": HandleType.LLM,
    "llm": HandleType.LLM,
    # Embeddings aliases
    "embeddings": HandleType.EMBEDDINGS,
    "embedder": HandleType.EMBEDDINGS,
    "baseembeddings": HandleType.EMBEDDINGS,
    # Memory aliases
    "memory": HandleType.MEMORY,
    "basememory": HandleType.MEMORY,
    # Tool aliases
    "tool": HandleType.TOOL,
    "basetool": HandleType.TOOL,
    "sequence[basetool]": HandleType.TOOL,
    # Document aliases
    "document": HandleType.DOCUMENT,
    "documents": HandleType.DOCUMENT,
    "chunks": HandleType.DOCUMENT,
    # Data aliases
    "string": HandleType.DATA,
    "str": HandleType.DATA,
    "int": HandleType.DATA,
    "float": HandleType.DATA,
    "dict": HandleType.DATA,
    "list": HandleType.DATA,
    "bool": HandleType.DATA,
    # Any
    "any": HandleType.ANY,
}


# ─── Compatibility Matrix ───
# Defines which handle types can be connected
COMPATIBILITY_MATRIX: Dict[HandleType, Set[HandleType]] = {
    HandleType.LLM: {HandleType.LLM},
    HandleType.EMBEDDINGS: {HandleType.EMBEDDINGS},
    HandleType.MEMORY: {HandleType.MEMORY},
    HandleType.TOOL: {HandleType.TOOL},
    HandleType.DOCUMENT: {HandleType.DOCUMENT},
    HandleType.DATA: {HandleType.DATA, HandleType.DOCUMENT},
    HandleType.ANY: set(HandleType),
}


def resolve_handle_type(raw: str) -> HandleType:
    return _TYPE_ALIASES.get(raw.lower().strip(), HandleType.DATA)


def are_handles_compatible(output_type: str, input_type: str) -> bool:
    out_t = resolve_handle_type(output_type)
    in_t = resolve_handle_type(input_type)

    if out_t == HandleType.ANY or in_t == HandleType.ANY:
        return True

    return in_t in COMPATIBILITY_MATRIX.get(out_t, set())
