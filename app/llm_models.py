#WERSJA Z DNIA 21.06.2025

import os
from dotenv import load_dotenv
from typing import List, Optional
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.models.fallback import FallbackModel
from httpx import AsyncClient
import logging

logger = logging.getLogger("llm_models")

load_dotenv()



def setup_fallback_model(
    models: Optional[List[str]] = None,
    openai_api_key: Optional[str] = None,
    gemini_api_key: Optional[str] = None,
    groq_api_key: Optional[str] = None,
    openrouter_api_key: Optional[str] = None,
    ollama_base_url: Optional[str] = None,
):
    """
    Initialize fallback LLM model based on a list of model names.
    Providers are only initialized if at least one requested model comes from them.
    If `models` is None or an empty list, uses default internal models.
    
    API keys and base URLs can be passed directly. If not, they are sourced
    from environment variables or hardcoded defaults.

    Args:
        models (Optional[List[str]]): List of strings representing the desired model names.
        openai_api_key (Optional[str]): OpenAI API key.
        gemini_api_key (Optional[str]): Google Gemini API key.
        groq_api_key (Optional[str]): Groq API key.
        openrouter_api_key (Optional[str]): OpenRouter API key.
        ollama_base_url (Optional[str]): Base URL for Ollama service.

    Returns:
        FallbackModel instance if any models were initialized successfully,
        otherwise returns "classification_failed_no_models".
    """
    
    internal_default_models = ["gpt-4.1-mini", "gemini-2.0-flash"] # Define internal default
    
    models_to_actually_use = models
    if not models: # Handles if models is None or an empty list []
        models_to_actually_use = internal_default_models
        logger.info(f"No specific models provided (or list was empty) for FallbackModel setup. Using internal defaults: {internal_default_models}")
 
    logger.debug("\n[bold blue]--- FallbackModel Initialization Start ---[/bold blue]")
    logger.debug(f"Attempting to initialize FallbackModel with: {models_to_actually_use}")

    # Define which models depend on which provider.
    openai_models = {"gpt-4o-mini", "o3-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1", "gpt-5","gpt-5-mini"}
    gemini_models = {"gemini-flash-latest", "gemini-3-flash-preview", "gemini-2.5-pro", "gemini-2.5-flash-preview-04-17", "gemini-2.5-flash", "gemini-2.5-pro-preview-05-06", "gemma-3-27b-it", "gemini-2.5-pro-preview-06-05"}
    groq_models   = {"meta-llama/llama-4-scout-17b-16e-instruct", "meta-llama/llama-4-maverick-17b-128e-instruct"}
    openrouter_models = {"google/gemma-3-27b-it", "qwen/qwen-vl-plus", "deepseek/deepseek-r1"}
    ollama_models = {"ollama/gemma3:4b", "ollama/gemma3:27b"}



    # Determine if a provider is needed based on the input list.
    need_openai = any(model in openai_models for model in models_to_actually_use)
    need_gemini = any(model in gemini_models for model in models_to_actually_use)
    need_groq = any(model in groq_models for model in models_to_actually_use)
    need_openrouter = any(model in openrouter_models for model in models_to_actually_use)
    need_ollama  = any(model in ollama_models for model in models_to_actually_use)


    # --- Providers Initialization ---
    # OpenAI Provider
    openai_provider = None
    if need_openai:
        effective_openai_api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        if effective_openai_api_key:
            try:
                custom_http_client = AsyncClient(timeout=30)
                openai_provider = OpenAIProvider(api_key=effective_openai_api_key, http_client=custom_http_client)
                logger.debug("OpenAI Provider initialized successfully.")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI Provider: {e}", exc_info=True)
        else:
            logger.warning("OPENAI_API_KEY not found in args or env. Skipping OpenAI provider initialization.")
    else:
        logger.debug("OpenAI Provider not required by requested models.")

    # Gemini Provider (Google GLA)
    gemini_provider = None
    if need_gemini:
        effective_gemini_api_key = gemini_api_key or os.getenv('GEMINI_API_KEY')
        if effective_gemini_api_key:
            try:
                gemini_provider = GoogleProvider(api_key=effective_gemini_api_key)
                logger.debug("Google GLA Provider initialized successfully.")
            except Exception as e:
                logger.warning(f"Failed to initialize Google GLA Provider: {e}", exc_info=True)
        else:
            logger.warning("GEMINI_API_KEY not found in args or env. Skipping Gemini provider initialization.")
    else:
        logger.debug("Gemini Provider not required by requested models.")

    # Groq Provider
    groq_provider = None
    if need_groq:
        effective_groq_api_key = groq_api_key or os.getenv('GROQ_API_KEY')
        if effective_groq_api_key:
            try:
                groq_provider = GroqProvider(api_key=effective_groq_api_key)
                logger.debug("Groq Provider initialized successfully.")
            except Exception as e:
                logger.warning(f"Failed to initialize Groq Provider: {e}", exc_info=True)
        else:
            logger.warning("GROQ_API_KEY not found in args or env. Skipping Groq provider initialization.")
    else:
        logger.debug("Groq Provider not required by requested models.")
        
    
    # Openrouter Provider
    openrouter_provider = None
    if need_openrouter:
        effective_openrouter_api_key = openrouter_api_key or os.getenv('OPENROUTER_API_KEY')
        if effective_openrouter_api_key:
            try:
                custom_http_client = AsyncClient(timeout=30)
                openrouter_provider = OpenAIProvider(
                # base_url='https://openrouter.ai/api/v1',
                base_url="https://openrouter.ai/api/v1/chat/completions",
                api_key=effective_openrouter_api_key,
                http_client=custom_http_client
                # client_kwargs={'timeout': 30.0}
                )
                
                logger.debug("Openrouter Provider initialized successfully.")
            except Exception as e:
                logger.warning(f"Failed to initialize Openrouter Provider: {e}", exc_info=True)
        else:
            logger.warning("OPENROUTER_API_KEY not found in args or env. Skipping Openrouter provider initialization.")
    else:
        logger.debug("Openrouter Provider not required by requested models.")
    
    
    # Ollama Provider - set up on runpod
    ollama_provider = None
    if need_ollama:
        # Prioritize passed base_url, then fallback to hardcoded default
        effective_ollama_base_url = ollama_base_url or 'https://z8dc1gdrcy9i17.proxy.runpod.net/v1'
        try:
            ollama_provider = OpenAIProvider(
            base_url=effective_ollama_base_url,
            )
            
            logger.debug("Ollama Provider initialized successfully.")
        except Exception as e:
            logger.warning(f"Failed to initialize Ollama Provider: {e}", exc_info=True)

    else:
        logger.debug("Ollama Provider not required by requested models.")

    # --- Define a Mapping of Model Initializers ---
    # This section programmatically builds the initializers to reduce code duplication.
    model_initializers = {}

    # Group model definitions by provider to simplify initialization.
    # Structure: (provider_instance, ModelClass, set_of_model_name_strings)
    model_definition_groups = [
        (openai_provider, OpenAIChatModel, openai_models),
        (gemini_provider, GoogleModel, gemini_models),
        (groq_provider, GroqModel, groq_models),
        (openrouter_provider, OpenAIChatModel, openrouter_models),
        (ollama_provider, OpenAIChatModel, ollama_models),
    ]

    for provider, model_class, model_names in model_definition_groups:
        for model_name in model_names:
            # The model name passed to the constructor might differ from the key.
            # e.g., for Ollama, the key is 'ollama/gemma3:4b' but the model needs 'gemma3:4b'.
            model_name_for_constructor = model_name
            if provider is ollama_provider and model_name.startswith("ollama/"):
                model_name_for_constructor = model_name.split('/', 1)[1]

            # Use default arguments in the lambda to capture current loop values.
            # This lambda structure correctly mirrors the original '... if provider else None' logic.
            model_initializers[model_name] = (
                lambda m_name=model_name_for_constructor, m_class=model_class, p=provider:
                    m_class(m_name, provider=p) if p else None
            )

    # --- Initialize Only the Requested Models ---
    available_models = []
    for model_str in models_to_actually_use:
        initializer = model_initializers.get(model_str)
        if initializer is None:
            logger.warning(f"Model '{model_str}' is not recognized. Skipping it.")
        else:
            try:
                model_instance = initializer()
                if model_instance:
                    available_models.append(model_instance)
                    logger.debug(f"Model '{model_str}' initialized successfully.")
                else:
                    logger.warning(f"Provider not available for model '{model_str}'. Skipping it.")
            except Exception as e:
                logger.warning(f"Failed to initialize model '{model_str}': {e}", exc_info=True)

    logger.debug("[bold blue]--- Initialization Complete ---[/bold blue]\n")
    if not available_models:
        logger.error("No LLM models available after initialization.")
        return "classification_failed_no_models"

    model_names = [getattr(m, 'model_name', 'UnknownModel') for m in available_models]
    logger.info(f"Using fallback model with available models: {model_names}")

    fallback_model = FallbackModel(*available_models)
    return fallback_model


if __name__ == "__main__":
    
    # ──────────────────────────────  logging  ──────────────────────────────
    from rich import traceback
    from rich.logging import RichHandler
    from datetime import datetime
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[RichHandler(rich_tracebacks=True, markup=True)],
    )
    logger = logging.getLogger(__name__)
    traceback.install()

    def now_timestamp() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # up to milliseconds
    
    
    # Define which models to initialize.
    models_to_initialize = [
        # "ollama/gemma3:27b",
        # "ollama/gemma3:4b",
        # "google/gemma-3-27b-it",
        "gpt-4o-mini",
        "o3-mini",
        "gemini-2.5-flash",
        "meta-llama/llama-4-scout-17b-16e-instruct"
    ]
    
    fallback_model = setup_fallback_model(models_to_initialize)
    
    from pydantic_ai import Agent
    agent = Agent(model=fallback_model, system_prompt="Concisely answer the user prompt in user prompt language")
    
    
    # Output the result.
    logger.info(f"Agent START at {now_timestamp()}")
    logger.info(f'Agent output: {agent.run_sync("Cześć witam! mówisz po polsku?")}')
    logger.info(f"Agent STOP at {now_timestamp()}")
