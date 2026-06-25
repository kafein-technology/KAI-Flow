import pytest
from app.services.ai_builder.handle_types import HandleType, are_handles_compatible

def test_handle_types_compatibility():
    # LLM handle compatibility
    assert are_handles_compatible("languagemodel", "llm") is True
    assert are_handles_compatible("baselanguagemodel", "languagemodel") is True
    assert are_handles_compatible("llm", "tool") is False

    # Embeddings compatibility
    assert are_handles_compatible("embeddings", "embedder") is True
    assert are_handles_compatible("embeddings", "embeddings") is True

    # ANY type compatibility
    assert are_handles_compatible("any", "llm") is True
    assert are_handles_compatible("languagemodel", "any") is True

    # Tool compatibility
    assert are_handles_compatible("tool", "tool") is True
    assert are_handles_compatible("basetool", "tool") is True
    assert are_handles_compatible("sequence[basetool]", "tool") is True
