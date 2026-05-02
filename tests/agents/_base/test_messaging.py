"""Tests for the message-construction helpers in agents/_base/messaging.py.

Critical invariant: when re-running the same agent with its own prior message history
(e.g. writer in revision rounds 2+), `prepend_system()` must NOT compound system prompts.
"""

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)

from agents._base.messaging import (
    build_system_message,
    build_user_message,
    prepend_system,
)


def test_build_system_message_creates_model_request_with_only_system_part():
    msg = build_system_message("you are a journalist")
    assert isinstance(msg, ModelRequest)
    assert len(msg.parts) == 1
    assert isinstance(msg.parts[0], SystemPromptPart)
    assert msg.parts[0].content == "you are a journalist"


def test_build_user_message_creates_model_request_with_only_user_part():
    msg = build_user_message("topic: dawid podsiadlo")
    assert isinstance(msg, ModelRequest)
    assert len(msg.parts) == 1
    assert isinstance(msg.parts[0], UserPromptPart)
    assert msg.parts[0].content == "topic: dawid podsiadlo"


def test_prepend_system_with_no_history():
    out = prepend_system("system prompt")
    assert len(out) == 1
    assert isinstance(out[0], ModelRequest)
    assert isinstance(out[0].parts[0], SystemPromptPart)
    assert out[0].parts[0].content == "system prompt"


def test_prepend_system_with_history_that_has_no_leading_system():
    history = [
        ModelRequest(parts=[UserPromptPart(content="hello")]),
        ModelResponse(parts=[TextPart(content="hi")]),
    ]
    out = prepend_system("sys", history)
    assert len(out) == 3
    assert isinstance(out[0].parts[0], SystemPromptPart)
    assert out[0].parts[0].content == "sys"
    # original history follows
    assert isinstance(out[1].parts[0], UserPromptPart)


def test_prepend_system_drops_existing_leading_system_to_prevent_compounding():
    """The fix for the writer.revise duplicate-system-prompt bug.

    When the writer's prior run history is fed back in (because we want the model to see
    its earlier draft), that history ALREADY starts with a SystemPromptPart from the
    previous run. Without dedupe, the next prepend_system would put two system messages
    at the head of history and waste input tokens linearly with revision count.
    """
    prior_history = [
        ModelRequest(parts=[SystemPromptPart(content="OLD writer system prompt")]),
        ModelRequest(parts=[UserPromptPart(content="round 1 user prompt")]),
        ModelResponse(parts=[TextPart(content="round 1 article draft")]),
    ]

    out = prepend_system("NEW writer system prompt", prior_history)

    # Exactly one system prompt at the head.
    system_messages = [
        m
        for m in out
        if isinstance(m, ModelRequest)
        and m.parts
        and all(isinstance(p, SystemPromptPart) for p in m.parts)
    ]
    assert len(system_messages) == 1, f"expected 1 system message, got {len(system_messages)}"
    assert system_messages[0].parts[0].content == "NEW writer system prompt"

    # User and assistant turns from prior history are preserved.
    assert any(
        isinstance(m, ModelRequest) and any(isinstance(p, UserPromptPart) for p in m.parts)
        for m in out
    )
    assert any(isinstance(m, ModelResponse) for m in out)
