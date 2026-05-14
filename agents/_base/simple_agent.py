"""Boilerplate-eliminator for tiny LLM agents that follow the standard
contract: render a prompt, run with fallback chain, record token usage,
return the typed Pydantic output.

The three discovery agents (classifier, topic_matcher, topic_writer)
all looked nearly identical before this helper. They differed only in
output_type, prompt template name, and agent_name string.

Pattern: define a small Pydantic OutputType, render a Jinja prompt
template, accept config + user_prompt, return OutputType. This helper
covers all of that."""

import pathlib
import time
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent

from agents._base.config import ExtractionAgentConfig
from agents._base.prompt_renderer import model_format_style, render_prompt
from agents._base.resilient import run_with_fallback
from agents._base.run_context import record_agent_call


async def run_simple_agent[T: BaseModel](
    *,
    prompts_dir: pathlib.Path,
    prompt_name: str,
    output_type: type[T],
    agent_name: str,
    user_prompt: str,
    config: ExtractionAgentConfig,
    _agent: Agent[Any, Any] | None = None,
    **prompt_vars: Any,
) -> tuple[T, str, int, int]:
    """Run a one-shot LLM agent with the project's standard fallback +
    usage-tracking pattern. Returns (output, model_used, input_tokens,
    output_tokens). Caller is responsible for any post-processing /
    validation of the output (e.g. filtering hallucinated category
    names, raising on empty fields, etc).

    Pass `_agent` to inject a TestModel-backed Agent for unit tests;
    when None the production fallback chain is used."""
    if _agent is not None:
        _t0 = time.perf_counter()
        result = await _agent.run(user_prompt)
        model_used = config.model
    else:

        def _factory(m: str) -> tuple[Agent[Any, Any], str]:
            sys_prompt = render_prompt(
                prompts_dir / prompt_name,
                format_style=model_format_style(m),
                **prompt_vars,
            )
            return Agent(m, output_type=output_type), sys_prompt

        _t0 = time.perf_counter()
        result, model_used = await run_with_fallback(
            (config.model, *config.fallback_models),
            agent_factory=_factory,
            user_prompt=user_prompt,
            agent_name=agent_name,
        )

    usage = result.usage
    input_tokens = usage.input_tokens or 0
    output_tokens = usage.output_tokens or 0
    record_agent_call(
        agent_name,
        model_used,
        input_tokens,
        output_tokens,
        (time.perf_counter() - _t0) * 1000,
    )
    return result.output, model_used, input_tokens, output_tokens
