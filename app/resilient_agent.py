import asyncio
import os
import logging
from typing import List, Optional, TypeVar, Type

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models import Model as PydanticAIModel
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.providers.openai import OpenAIProvider
from rich.logging import RichHandler
from rich import print

# Setup
load_dotenv()
logger = logging.getLogger(__name__)

# A generic type for the output model
T = TypeVar("T", bound=BaseModel)


class AllModelsFailedError(Exception):
    """Custom exception raised when all models in the retry loop have failed."""
    def __init__(self, message: str, errors: list[tuple[str, Exception]]):
        full_message = f"{message}\n"
        for model_name, error in errors:
            full_message += f"  - Model '{model_name}': {type(error).__name__}: {str(error)}\n"
        super().__init__(full_message)
        self.errors = errors


# --- Provider and Model Mappings ---
_OPENAI_MODELS = {"gpt-4o-mini", "o3-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1", "gpt-5", "gpt-5-mini"}
_GEMINI_MODELS = {"gemini-2.5-pro", "gemini-2.5-flash-preview-04-17", "gemini-2.0-flash", "gemini-2.5-pro-preview-05-06", "gemma-3-27b-it", "gemini-2.5-pro-preview-06-05"}
_GROQ_MODELS = {"meta-llama/llama-4-scout-17b-16e-instruct", "meta-llama/llama-4-maverick-17b-128e-instruct"}
_OPENROUTER_MODELS = {"google/gemma-3-27b-it", "qwen/qwen-vl-plus", "deepseek/deepseek-r1"}
_OLLAMA_MODELS = {"ollama/gemma3:4b", "ollama/gemma3:27b"}

# --- Provider Instances ---
_openai_provider = OpenAIProvider(api_key=os.getenv('OPENAI_API_KEY')) if os.getenv('OPENAI_API_KEY') else None
_gemini_provider = GoogleProvider(api_key=os.getenv('GEMINI_API_KEY')) if os.getenv('GEMINI_API_KEY') else None
_groq_provider = GroqProvider(api_key=os.getenv('GROQ_API_KEY')) if os.getenv('GROQ_API_KEY') else None
_openrouter_provider = OpenAIProvider(base_url="https://openrouter.ai/api/v1/chat/completions", api_key=os.getenv('OPENROUTER_API_KEY')) if os.getenv('OPENROUTER_API_KEY') else None
_ollama_provider = OpenAIProvider(base_url=os.getenv('OLLAMA_BASE_URL', 'https://z8dc1gdrcy9i17.proxy.runpod.net/v1'))


def create_model_instance(model_name: str) -> Optional[PydanticAIModel]:
    """
    Factory function to create an instance of a pydantic-ai model.
    Returns None if the provider for the model is not configured.
    """
    if model_name in _OPENAI_MODELS:
        if not _openai_provider:
            logger.warning(f"OpenAI provider not configured. Skipping model '{model_name}'.")
            return None
        return OpenAIModel(model_name, provider=_openai_provider)

    if model_name in _GEMINI_MODELS:
        if not _gemini_provider:
            logger.warning(f"Gemini provider not configured. Skipping model '{model_name}'.")
            return None
        return GoogleModel(model_name, provider=_gemini_provider)

    if model_name in _GROQ_MODELS:
        if not _groq_provider:
            logger.warning(f"Groq provider not configured. Skipping model '{model_name}'.")
            return None
        return GroqModel(model_name, provider=_groq_provider)

    if model_name in _OPENROUTER_MODELS:
        if not _openrouter_provider:
            logger.warning(f"OpenRouter provider not configured. Skipping model '{model_name}'.")
            return None
        return OpenAIModel(model_name, provider=_openrouter_provider)

    if model_name in _OLLAMA_MODELS:
        ollama_model_name = model_name.split('/', 1)[1]
        return OpenAIModel(ollama_model_name, provider=_ollama_provider)

    logger.error(f"Unknown model name '{model_name}' requested.")
    return None


async def run_with_retry(
    model_list: List[str],
    output_type: Type[T],
    user_prompt: str,
    system_prompt: Optional[str] = None,
    message_history: Optional[List[ModelMessage]] = None
) -> AgentRunResult[T]:
    """
    Runs a pydantic-ai Agent with a list of models, retrying on any failure.

    Args:
        model_list: A list of model name strings to try in order.
        output_type: The Pydantic model for the expected output.
        user_prompt: The prompt to send to the user.
        system_prompt: The system prompt for the agent.
        message_history: The message history for the agent.

    Raises:
        AllModelsFailedError: If all models in the list fail to produce a valid response.

    Returns:
        A successful AgentRunResult object from the first model that succeeds.
    """
    encountered_errors = []

    for i, model_name in enumerate(model_list):
        attempt_num = i + 1
        logger.info(f"Attempt {attempt_num}/{len(model_list)}: Using model '{model_name}'...")

        try:
            model_instance = create_model_instance(model_name)
            if not model_instance:
                error = ValueError(f"Provider for model '{model_name}' is not configured or available.")
                encountered_errors.append((model_name, error))
                continue

            agent_kwargs = {
                "model": model_instance,
                "output_type": output_type,
                "retries": 0,
            }
            if system_prompt:
                agent_kwargs["system_prompt"] = system_prompt

            agent = Agent(**agent_kwargs)

            result = await asyncio.wait_for(
                agent.run(
                    user_prompt=user_prompt,
                    message_history=message_history or []
                ),
                timeout=300.0  # 5-minute timeout per attempt
            )

            logger.info(f"Attempt {attempt_num} with model '{model_name}' succeeded.")
            return result, model_name

        except Exception as e:
            error_msg = f"Attempt {attempt_num} with model '{model_name}' failed. Error: {type(e).__name__}: {str(e)}"
            logger.warning(error_msg, exc_info=False)
            if isinstance(e, ValidationError):
                logger.warning(f"Validation errors for model '{model_name}': {e.errors()}")

            encountered_errors.append((model_name, e))

    raise AllModelsFailedError(
        message="All models failed to produce a valid response.",
        errors=encountered_errors
    )


# --- Example Usage ---
if __name__ == "__main__":
    # Configure logging for rich output
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(message)s",
        handlers=[RichHandler(rich_tracebacks=True, markup=True)],
    )

    # 1. Define the desired output structure
    class Joke(BaseModel):
        setup: str
        punchline: str

    # 2. Define the list of models to try, in order of preference
    # We include a fake model to demonstrate the retry mechanism.
    models_to_try = [
        "fake-model-that-will-fail",
        "fake-model-that-will-fail",
        "gpt-5-mini",
        "gemini-2.0-flash",
    ]

    # 3. Define the async main function
    async def main():
        print("[bold yellow]Running example: Getting a joke about programmers...[/bold yellow]")
        try:
            response = await run_with_retry(
                model_list=models_to_try,
                output_type=Joke,
                user_prompt="Tell me a short, classic joke about programmers.",
                system_prompt="You are a helpful assistant that tells jokes."
            )
            print("\n[bold green]Success![/bold green]")
            print("Setup:", response.output.setup)
            print("Punchline:", response.output.punchline)

        except AllModelsFailedError as e:
            print("\n[bold red]Error: All models failed.[/bold red]")
            print(e)

    # 4. Run the async function
    asyncio.run(main())