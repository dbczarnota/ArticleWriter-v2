from __future__ import annotations
import asyncio
import os
import re

from pydantic import BaseModel, Field
from pydantic_ai.messages import ModelMessage
from pydantic_graph import BaseNode, End, Graph, GraphRunContext
from pydantic_ai.models.openai import OpenAIModel

from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.providers.google_gla import GoogleGLAProvider
from pydantic_ai.exceptions import FallbackExceptionGroup, ModelHTTPError

from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai import Agent
from dataclasses import dataclass
import tiktoken
import logging
from typing import List, Literal, Optional
from searchandscrape import SearchAndScrape
from rich import print
from dotenv import load_dotenv
# from datetime import date, datetime, timedelta
from pydantic import field_validator # For Pydantic v2
from datetime import datetime, timedelta, date as date_type # alias date to avoid conflict
import abc
from html import escape
from example_articles import example_articles
from prompts import ( 
    research_agent_prompt, 
    llmknowledge_agent_prompt, 
    parsing_agent_prompt, 
    data_extraction_agent_prompt, 
    article_snippet, 
    article_snippet_short, 
    instructions_agent_prompt,
    writing_agent_prompt,
    reflection_agent_prompt,
    followup_agent_prompt
    )
from llm_models import setup_fallback_model
from tavily import TavilyClient
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import CrawlerRunConfig, CacheMode
from pydantic_ai.exceptions import FallbackExceptionGroup, ModelHTTPError

logger = logging.getLogger(__name__)
load_dotenv()
current_date = current_date_today = date_type.today()

###############################################################################
# Error handling class template
###############################################################################
class ResilientNode(BaseNode, abc.ABC):
    """
    A base node class that handles common execution logic like
    timeouts, retries, and error logging, designed to work with FallbackModel.
    """
    retry_counter_attr: str = ""
    max_retries: int = 1
    timeout_seconds: int = 600

    @abc.abstractmethod
    async def _execute(self, ctx: GraphRunContext[State]) -> BaseNode | End:
        """
        The core logic specific to the node.
        Subclasses MUST implement this method. It should instantiate
        a FallbackModel and use it within an Agent.
        It should return the next node instance, an End state,
        a node Type (to instantiate), or None if handled internally.
        """
        pass

    async def run(self, ctx: GraphRunContext[State]) -> BaseNode | End:
        """
        Runs the node's core logic (_execute) with timeout, retry,
        and enhanced error handling for FallbackModel.
        """
        if not self.retry_counter_attr:
            raise NotImplementedError(
                f"Node {self.__class__.__name__} must define 'retry_counter_attr'"
            )

        node_name = self.__class__.__name__
        current_retries = getattr(ctx.state, self.retry_counter_attr, 0)
        error_message = "Node execution failed" # Default error message

        try:
            logger.info(f"Running {node_name} (Attempt {current_retries + 1}/{self.max_retries + 1})...")
            # Wrap the specific logic execution with a timeout
            result = await asyncio.wait_for(
                self._execute(ctx), # This now uses FallbackModel internally
                timeout=self.timeout_seconds
            )
            # Optional: Reset retry counter on success
            # setattr(ctx.state, self.retry_counter_attr, 0)
            
            logger.info(f"{node_name} completed successfully.")
            return result # Return the next node or End

        except asyncio.TimeoutError:
            error_message = f"{node_name} timed out after {self.timeout_seconds} seconds on attempt {current_retries + 1}"
            logger.error(error_message)
            # Fall through to retry logic

        except FallbackExceptionGroup as feg:
            error_message = f"{node_name} failed on attempt {current_retries + 1}: All fallback models exhausted."
            logger.error(error_message)
            # Log details about each model's failure
            for i, exc in enumerate(feg.exceptions):
                model_name_info = f"Model {i+1}"
                # Attempt to get model name if available in the exception context
                if hasattr(exc, '__cause__') and hasattr(exc.__cause__, 'model_name'):
                     model_name_info = f"Model {i+1} ({exc.__cause__.model_name})" # Might need adjustment based on actual exception structure
                elif hasattr(exc, 'model_name'):
                     model_name_info = f"Model {i+1} ({exc.model_name})"

                logger.error(f"  - {model_name_info}: {type(exc).__name__}: {exc}")
            # You could potentially add more details from feg.exceptions to the main error_message
            # error_message += f" Errors: {[str(e) for e in feg.exceptions]}" # Example
             # Fall through to retry logic

        except ValueError as ve: # Catch specific errors like "No usable models"
            error_message = f"Configuration or setup error in {node_name} on attempt {current_retries + 1}: {str(ve)}"
            logger.error(error_message, exc_info=True) # Log traceback for value errors
             # Fall through to retry logic

        except Exception as e:
            error_message = f"Unexpected error in {node_name} on attempt {current_retries + 1}: {type(e).__name__}: {str(e)}"
            logger.exception(f"Caught unexpected exception in {node_name}") # Logs traceback
            # Fall through to retry logic

        # --- Common Error/Retry Handling ---
        ctx.state.add_error(node_name, error_message) # Log the specific error to state

        if current_retries < self.max_retries:
            setattr(ctx.state, self.retry_counter_attr, current_retries + 1)
            
            logger.warning(f"Retrying {node_name} (Attempt {current_retries + 2}/{self.max_retries + 1})...")
            return self.__class__()
        else:
            final_error_msg = f"ERROR: {node_name} failed permanently after {self.max_retries + 1} attempts. Last error: {error_message}"
            logger.error(final_error_msg)
            # Ensure state is saved with the final error logged
            
            # Append detailed error report from state to the End message
            error_report = self._generate_error_report(ctx.state.errors) # Assuming helper exists or add it
            return End(f"{final_error_msg}\n\nError Log:\n{error_report}")

    # Helper method to generate error report (similar to FollowUpNode)
    def _generate_error_report(self, errors: list[dict[str, str]]) -> str:
        """Generates a plain text error report."""
        if not errors:
            return "No errors reported during execution."
        report = ""
        for err in errors:
             report += f"- Node: {escape(err.get('node', 'Unknown Node'))}, Error: {escape(err.get('error', 'Unknown Error'))}\n"
        return report
    
# ###############################################################################
# # Centralized Model Initialization
# ###############################################################################
NODE_MODEL_CONFIG = {
    "SearchNode": ["gemini-2.0-flash", "gpt-5-mini"],
    "LlmKnowledgeNode": ["gemini-2.0-flash", "gpt-5-mini"],
    "ParsingNode": ["gemini-2.0-flash", "gpt-5-mini"],
    "DataExtractionNode": ["gemini-2.0-flash", "gemini-2.5-pro", "gpt-5"],
    "InstructionsNode": ["gemini-2.5-pro", "gpt-5"],
    "WritingNode": ["gemini-2.5-pro", "gpt-5"],
    "ReflectionNode": ["gemini-2.5-pro", "gpt-5"],
    "FollowUpNode": ["gemini-2.0-flash", "gemini-2.5-pro", "gpt-5"],
}



###############################################################################
# State definition
###############################################################################
class Configuration(BaseModel):
    article_topic: str = ""
    domains: list[str] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)  # <-- new field
    number_of_queries: int = 2
    scraping_model: str = ""
    max_search_results: int = 3
    search_days: int = 30
    extraction_mode: Literal["markdown", "html", "llm"] = "markdown"
    provide_llm_facts: Literal["yes", "no"] = "yes"
    additional_instructions: Optional[str] = None


class ResearchPlan(BaseModel):
    queries: list[str] = Field(default_factory=list)
    plan: str = ""
    keywords: list[str] = Field(default_factory=list)


class ResearchedInfo(BaseModel):
    quotes: list[dict] = Field(default_factory=list) 
    facts: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    article_texts: Optional[str] = None
    facts_from_llm: list[FactFromLlm] = Field(default_factory=list)
    facts_from_articles: list[str] = Field(default_factory=list)


class FactFromLlm(BaseModel):
    fact_llm: Optional[str] = None
    source: Optional[str] = None


class State(BaseModel):
    current_date: date_type = current_date
    configuration: Configuration
    reflection_round: int = 0
    instructions: str = ""
    reflection_prompt: str = ""
    research_plan: ResearchPlan = None
    scraped_pages: list[dict] = Field(default_factory=list)
    researched_info: ResearchedInfo = ResearchedInfo()
    finished_article: str = ""
    sources: list[str] = Field(default_factory=list)
    messages: list[ModelMessage] = Field(default_factory=list)
    searchnode_tries: int = 0
    scrapingnode_tries: int = 0
    parsingnode_tries: int = 0
    dataextractionnode_tries: int = 0
    instructionsnode_tries: int = 0
    writingnode_tries: int = 0
    reflectionnode_tries: int = 0
    followupnode_tries: int = 0
    llmknowledgenode_tries: int = 0
    errors: list[dict[str, str]] = Field(default_factory=list, description="List of errors encountered during the graph run.")
    
    # --- Optional: Add helper to add errors ---
    def add_error(self, node_name: str, error_message: str):
        self.errors.append({"node": node_name, "error": error_message})
        
        
        

###############################################################################
# Nodes
###############################################################################
############################### Search Node ###################################

@dataclass
class SearchNode(ResilientNode):
    # --- Configure ResilientNode ---
    retry_counter_attr: str = "searchnode_tries"
    max_retries: int = 1
    timeout_seconds: int = 600

    async def _execute(self, ctx: GraphRunContext[State]) -> ScrapingNode | LlmKnowledgeNode | End:
        """
        Generates the research plan and queries based on the article topic,
        using a fallback model strategy.
        """
        node_name = self.__class__.__name__
        logger.info(f"Executing {node_name} logic...")


        # --- Instantiate Agent within _execute ---
        fallback_model = setup_fallback_model(NODE_MODEL_CONFIG[node_name])
        research_agent = Agent[None, ResearchPlan](
            model=fallback_model,
            output_type=ResearchPlan,
        )
        
        additional_instructions = ctx.state.configuration.additional_instructions
        if additional_instructions is not None and additional_instructions not in ["None", "none", ""]:
            additional_instructions_formatted = f"### Additional Instructions and Context:\nThese are additional instructions to follow or context to include while writing the article:\n{additional_instructions}\nThey are very important and must be included."
        else:
            additional_instructions_formatted = ""

        # --- Core Logic ---
        prompt = research_agent_prompt.format(
            current_date=ctx.state.current_date,
            article_topic=ctx.state.configuration.article_topic,
            number_of_queries=ctx.state.configuration.number_of_queries,
            additional_instructions_formatted=additional_instructions_formatted,
        )
        result = await research_agent.run(user_prompt=prompt)

        if not result or not result.output:
             raise ValueError(f"{node_name} agent run did not return valid data after attempting models.")

        # --- Update State ---
        ctx.state.research_plan = result.output
        ctx.state.research_plan.queries.append(ctx.state.configuration.article_topic)
        
        logger.info(f'Search queries generated: {ctx.state.research_plan.queries}')

        # --- Return Next Node INSTANCE --- <--- CORRECTED
        if ctx.state.configuration.provide_llm_facts == "yes":
            # Return an INSTANCE of the next node
            logger.info(f"Transitioning from {node_name} to LlmKnowledgeNode")
            return LlmKnowledgeNode() # Instantiate
        else:
            # Return an INSTANCE of the next node
            logger.info(f"Transitioning from {node_name} to ScrapingNode")
            return ScrapingNode() # Instantiate

###############################################################################
################################ LlmKnowledge Node ################################

@dataclass
class LlmKnowledgeNode(ResilientNode):
    # --- Configure ResilientNode ---
    retry_counter_attr: str = "llmknowledgenode_tries"
    max_retries: int = 1
    timeout_seconds: int = 600

    async def _execute(self, ctx: GraphRunContext[State]) -> ScrapingNode | End:
        """
        Retrieves and stores facts directly from the LLM based on the research plan,
        using a fallback model strategy.
        """
        node_name = self.__class__.__name__
        logger.info(f"Executing {node_name} logic...")




        fallback_model = setup_fallback_model(NODE_MODEL_CONFIG[node_name])
        llmknowledge_agent = Agent( 
            model=fallback_model,
            output_type=list[FactFromLlm]
        )

        # --- Core Logic ---
        # Ensure research_plan is not None before accessing attributes
        if ctx.state.research_plan is None:
            logger.error(f"Cannot execute {node_name}: research_plan is missing in state.")
            # Decide how to handle: raise error, or return End? Raising error lets ResilientNode handle retry/fail.
            raise ValueError(f"Cannot execute {node_name}: research_plan is missing.")

        prompt = llmknowledge_agent_prompt.format( # Ensure llmknowledge_agent_prompt is accessible
            article_topic=ctx.state.configuration.article_topic,
            # Use .get() with default for potentially missing plan parts, or check existence
            initial_plan=getattr(ctx.state.research_plan, 'plan', "No plan available"),
            search_queries=getattr(ctx.state.research_plan, 'queries', []),
            current_date=ctx.state.current_date # Use state's date
        )
        logger.debug(f'{node_name} prompt: {prompt[:300]}...')

        # Agent run uses the fallback sequence
        result = await llmknowledge_agent.run(user_prompt=prompt)

        # Check result validity
        if result is None or result.output is None: # Check for None data specifically
             # result.data could be an empty list [], which is valid, so check for None
             raise ValueError(f"{node_name} agent run did not return valid data after attempting models.")

        # --- Update State ---
        ctx.state.researched_info.facts_from_llm = result.data
        logger.info(f'LLM facts retrieved: {len(ctx.state.researched_info.facts_from_llm)} items.')

        

        # --- Return Next Node INSTANCE ---
        logger.info(f"Transitioning from {node_name} to ScrapingNode")
        return ScrapingNode() # Instantiate
            


###############################################################################
################################ Scraping Node ################################
@dataclass
class ScrapingNode(ResilientNode):
    # --- Configure ResilientNode ---
    retry_counter_attr: str = "scrapingnode_tries"
    max_retries: int = 1
    timeout_seconds: int = 900 # Increased timeout for potentially many pages

    async def _execute(self, ctx: GraphRunContext[State]) -> ParsingNode | End:
        """
        Performs web searches using Tavily, filters out irrelevant domains,
        and scrapes the content of the remaining URLs into clean markdown using Crawl4AI.
        """
        logger.info("Executing ScrapingNode logic...")

        # --- 1. Search Phase ---
        try:
            tavily_client = TavilyClient(api_key=os.getenv('TAVILY_API_KEY'))
        except Exception as e:
            raise ValueError(f"Failed to initialize TavilyClient. Ensure TAVILY_API_KEY is set. Error: {e}")

        unique_urls = set()
        url_to_description = {}
        
        logger.info(f"Generating search results for queries: {ctx.state.research_plan.queries}")
        for query in ctx.state.research_plan.queries:
            try:
                search_response = tavily_client.search(
                    query=query,
                    max_results=ctx.state.configuration.max_search_results,
                    days=ctx.state.configuration.search_days,
                    include_domains=ctx.state.configuration.domains or None
                )
                for result in search_response.get("results", []):
                    if url := result.get("url"):
                        unique_urls.add(url)
                        url_to_description[url] = result.get("content", "")
            except Exception as e:
                logger.warning(f"Tavily search failed for query '{query}'. Error: {e}")

        # Add manually provided URLs from the configuration
        if manual_urls := ctx.state.configuration.urls:
            unique_urls.update(manual_urls)
            # Add a placeholder description for manual URLs if not already present
            for url in manual_urls:
                url_to_description.setdefault(url, "Manually provided URL.")

        # --- 2. URL Filtering Phase ---
        EXCLUDED_DOMAINS = [
            'youtube.com', 'facebook.com', 'twitter.com', 'x.com', 
            'instagram.com', 'linkedin.com', 'tiktok.com'
        ]
        
        filtered_urls = {
            url for url in unique_urls 
            if not any(domain in url for domain in EXCLUDED_DOMAINS)
        }
        
        urls_to_scrape = list(filtered_urls)

        if not urls_to_scrape:
            logger.warning("No URLs to scrape after searching and filtering. Proceeding to ParsingNode.")
            return ParsingNode()

        logger.info(f"Identified {len(urls_to_scrape)} unique URLs to scrape after filtering.")

        # --- 3. Scraping Phase ---
        scraped_pages_data = []
        
        # Configure the crawler for clean, link-free markdown
        run_config = CrawlerRunConfig(
            extraction_strategy=None, # Use built-in markdown conversion
            excluded_tags=['nav', 'header', 'footer', 'aside', 'form', 'script', 'style'],
            remove_overlay_elements=True,
            process_iframes=False,
            cache_mode=CacheMode.BYPASS,
            word_count_threshold=10
        )
        
        logger.info("Starting web scraping with Crawl4AI...")
        async with AsyncWebCrawler() as crawler:
            results = await crawler.arun_many(urls=urls_to_scrape, config=run_config)

            for result in results:
                if result.success:
                    logger.debug(f"Successfully scraped: {result.url}")
                    # Create a dictionary matching the structure expected by downstream nodes
                    page_data = {
                        "url": result.url,
                        "title": result.metadata.get('title', 'Title not found'),
                        "article_body": result.markdown, # Use clean markdown as the body
                        "description": url_to_description.get(result.url, "")
                    }
                    scraped_pages_data.append(page_data)
                else:
                    logger.error(f"Failed to scrape {result.url}: {result.error_message}")

        # --- 4. Update State ---
        ctx.state.scraped_pages = scraped_pages_data
        logger.info(f"Scraping complete. Successfully processed {len(scraped_pages_data)} pages.")
        
        # Transition to the next node
        return ParsingNode()

###############################################################################
################################ Parsing Node #################################


class ParsedArticle(BaseModel):
    webpage_type: Literal['article', 'other']
    parsed_article: str

@dataclass
class ParsingNode(ResilientNode):
    # --- Configure ResilientNode ---
    retry_counter_attr: str = "parsingnode_tries"
    max_retries: int = 1
    timeout_seconds: int = 720 # 12 minutes

    async def _execute(self, ctx: GraphRunContext[State]) -> DataExtractionNode | End:
        """
        Parses the raw HTML of scraped pages to extract article text,
        handling token limits and using a fallback model strategy for each page.
        Includes a page-level retry mechanism for transient model errors.
        """
        node_name = self.__class__.__name__
        logger.info(f"Executing {node_name} logic...")

        enc = tiktoken.get_encoding("cl100k_base")
        MAX_TOKENS = 150_000

        pages_to_process = ctx.state.scraped_pages
        if not pages_to_process:
            logger.warning("No scraped pages found to parse. Proceeding.")
            return DataExtractionNode()

        tasks = []

        async def process_page(page: dict):
            """Inner function to process a single page with retries."""
            page_url = page.get('url', 'unknown URL')
            page_node_log_prefix = f"{node_name} - Page {page_url}:"
            
            # --- New: Page-level retry logic ---
            max_page_retries = 1 # Total of 2 attempts per page
            attempt = 0
            
            while attempt <= max_page_retries:
                try:
                    # On retry, log the attempt number
                    if attempt > 0:
                        logger.warning(f"{page_node_log_prefix} Retrying... (Attempt {attempt + 1}/{max_page_retries + 1})")

                    article_body = page.get("article_body", "")
                    if not article_body:
                        logger.warning(f"{page_node_log_prefix} No article_body found. Skipping.")
                        page['webpage_type'] = 'other'
                        page['parsed_article'] = None
                        return # Exit for this page, no need to retry empty body

                    # Initialize model and agent inside the loop to ensure fresh state on retry
                    fallback_model = setup_fallback_model(NODE_MODEL_CONFIG["ParsingNode"])
                    parsing_agent = Agent[None, ParsedArticle](
                        model=fallback_model,
                        output_type = ParsedArticle,
                        retries=1 # Agent-level retries (will try each model in fallback once)
                    )
                    
                    tokens = enc.encode(article_body)
                    if len(tokens) > MAX_TOKENS:
                        logger.warning(f"{page_node_log_prefix} Article has {len(tokens)} tokens, truncating.")
                        tokens = tokens[:MAX_TOKENS]
                        article_body = enc.decode(tokens)
                        page["article_body_truncated"] = True

                    prompt = parsing_agent_prompt.format(html=article_body, current_date=ctx.state.current_date)
                    result = await parsing_agent.run(user_prompt=prompt)

                    if result is None or result.output is None:
                         raise ValueError("Parsing agent run did not return valid data.")

                    # --- Success Case ---
                    page['webpage_type'] = result.output.webpage_type
                    page['parsed_article'] = result.output.parsed_article
                    page.pop('parsing_error', None) # Clear any previous error on success
                    logger.debug(f"{page_node_log_prefix} Successfully parsed.")
                    break # Exit the while loop on success

                except Exception as error:
                    attempt += 1
                    # If this was the last attempt, log final error and mark page as failed
                    if attempt > max_page_retries:
                        logger.error(f"{page_node_log_prefix} Failed permanently after {max_page_retries + 1} attempts: {error}", exc_info=True)
                        page['webpage_type'] = 'other'
                        page['parsed_article'] = None
                        page['parsing_error'] = str(error)
                        break # Exit the loop, the page has failed
                    else:
                        # Log the temporary error and allow the loop to continue for another attempt
                        logger.warning(f"{page_node_log_prefix} Encountered temporary error: {error}. Preparing to retry.")
                        await asyncio.sleep(1) # Small delay before retrying

        # Create and run tasks
        for page in pages_to_process:
            tasks.append(process_page(page))
        await asyncio.gather(*tasks)

        successful_parses = sum(1 for p in pages_to_process if 'parsing_error' not in p and p.get('parsed_article') is not None)
        failed_parses = len(pages_to_process) - successful_parses
        logger.info(f"Parsing finished for {len(pages_to_process)} pages. Successful: {successful_parses}, Failed: {failed_parses}.")

        logger.info(f"Transitioning from {node_name} to DataExtractionNode")
        return DataExtractionNode()


###############################################################################
############################# DataExtraction Node #############################

class Quote(BaseModel):
    text: Optional[str] = None
    speaker: Optional[str] = None
    source: Optional[str] = None
    
class ResearchedArticle(BaseModel):
    webpage_type: Literal['article', 'other']
    relevant: Literal['yes', 'no']
    publication_date: date_type
    facts: list[str] = Field(default_factory=list)
    quotes: list[Quote] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    
    
    @field_validator('publication_date', mode='before')
    @classmethod
    def parse_publication_date(cls, value):
        if value is None:
            # If the field were Optional[date], we might return None.
            # Since it's 'date', a value is expected.
            # If LLM *can* return null/None for this, the field should be Optional.
            # For now, if LLM is guaranteed to provide a date string, this path might not be hit often.
            # However, if it does send an explicit null, Pydantic might complain earlier
            # or this validator needs to handle it by raising ValueError or returning a default if appropriate.
            # Given the error is about format, let's assume a string or date object is usually passed.
            raise ValueError("Publication date cannot be None") # Or handle as per desired logic for None

        if isinstance(value, date_type):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            try:
                # Attempt to parse ISO format string, including those with 'T' and time
                dt_obj = datetime.fromisoformat(value.replace('Z', '+00:00')) # Handles 'Z' for UTC
                return dt_obj.date()
            except ValueError:
                # Fallback for simple "YYYY-MM-DD" or other common formats
                for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d"): # Add other formats if LLM uses them
                    try:
                        return datetime.strptime(value, fmt).date()
                    except ValueError:
                        continue
                raise ValueError(f"Invalid date format: {value}. Expected ISO format or YYYY-MM-DD.")
        raise TypeError(f"Invalid type for date: {type(value)}. Expected str, date, or datetime.")



@dataclass
class DataExtractionNode(ResilientNode):
    # --- Configure ResilientNode ---
    retry_counter_attr: str = "dataextractionnode_tries"
    max_retries: int = 1
    timeout_seconds: int = 900 # 15 minutes

    async def _execute(self, ctx: GraphRunContext[State]) -> InstructionsNode | End:
        """
        Extracts structured information from parsed articles using a fallback
        model strategy for each relevant page, with page-level retries.
        It then filters and aggregates the data.
        """
        node_name = self.__class__.__name__
        logger.info(f"Executing {node_name} logic...")

        pages_to_process = [
            page for page in ctx.state.scraped_pages
            if page and page.get('article_body') and not page.get('parsing_error')
        ]

        if not pages_to_process:
            logger.warning(f"{node_name}: No successfully parsed pages to extract data from.")
            if not ctx.state.researched_info.facts_from_llm:
                 logger.error(f"{node_name}: No parsed pages AND no LLM facts found. Ending run.")
                 ctx.state.add_error(node_name, "No content available for processing.")
                 error_report = self._generate_error_report(ctx.state.errors)
                 return End(f"ERROR: No content to write an article.\n\nError Log:\n{error_report}")
            else:
                # If there are only LLM facts, we can proceed.
                logger.info(f"{node_name}: Proceeding with only LLM facts.")
                # The filtering logic below will handle this case gracefully.

        tasks = []

        async def process_page(page: dict):
            """Inner function to process a single page with retries."""
            page_url = page.get('url', 'unknown URL')
            page_node_log_prefix = f"{node_name} - Page {page_url}:"
            
            # Page-level retry logic
            max_page_retries = 1
            attempt = 0
            
            while attempt <= max_page_retries:
                try:
                    if attempt > 0:
                        logger.warning(f"{page_node_log_prefix} Retrying... (Attempt {attempt + 1}/{max_page_retries + 1})")

                    parsed_article_body = page.get("article_body", "")

                    # Format article for the prompt
                    title = page.get('title', "Title not found")
                    article_text_for_prompt = article_snippet.format(
                        url=page_url,
                        title=title,
                        description=page.get("description", "No description available"),
                        article_text=parsed_article_body
                    )
                    page['formated_article'] = article_text_for_prompt
                    page['formated_article_short'] = article_snippet_short.format(
                        title=title,
                        article_text=parsed_article_body
                    )
                    
                    # Initialize model and agent inside the loop for fresh state
                    fallback_model = setup_fallback_model(NODE_MODEL_CONFIG[node_name])
                    data_extraction_agent = Agent[None, ResearchedArticle](
                        model=fallback_model,
                        output_type=ResearchedArticle,
                        retries=1
                    )
                    
                    prompt = data_extraction_agent_prompt.format(
                        text=article_text_for_prompt,
                        topic=ctx.state.configuration.article_topic
                    )
                    
                    researched_article_result = await data_extraction_agent.run(user_prompt=prompt)

                    if researched_article_result is None or researched_article_result.output is None:
                         raise ValueError("Data extraction agent run did not return valid data.")

                    # --- Success Case ---
                    data = researched_article_result.output
                    page['webpage_type'] = data.webpage_type
                    page['relevant'] = data.relevant
                    page['facts'] = data.facts
                    page['publication_date'] = data.publication_date
                    page['keywords'] = data.keywords
                    
                    if data.quotes:
                        page['quotes'] = [q.model_dump() for q in data.quotes]
                        for quote_dict in page['quotes']:
                            quote_dict['page_url'] = page_url
                    else:
                        page['quotes'] = []
                    
                    page.pop('extraction_error', None) # Clear previous errors
                    logger.debug(f"{page_node_log_prefix} Successfully extracted data.")
                    break # Exit loop on success

                except Exception as error:
                    raw_response = None
                    if isinstance(error, FallbackExceptionGroup):
                        # Find the first inner exception that has a response body
                        for inner_exc in error.exceptions:
                            if hasattr(inner_exc, 'response') and getattr(inner_exc, 'response', None):
                                raw_response = getattr(inner_exc, 'response')
                                break
                    elif hasattr(error, 'response') and getattr(error, 'response', None):
                        raw_response = getattr(error, 'response')

                    if raw_response:
                        logger.warning(f"{page_node_log_prefix} Model returned a response that caused an error. Raw response: {raw_response}")

                    attempt += 1
                    if attempt > max_page_retries:
                        logger.error(f"{page_node_log_prefix} Failed permanently after {max_page_retries + 1} attempts: {error}", exc_info=True)
                        page['extraction_error'] = str(error)
                        page.setdefault('webpage_type', 'other')
                        page.setdefault('relevant', 'no')
                        break # Exit loop, page has failed
                    else:
                        logger.warning(f"{page_node_log_prefix} Encountered temporary error: {error}. Preparing to retry.")
                        await asyncio.sleep(1)
        
        # Create and run tasks
        for page in pages_to_process:
            tasks.append(process_page(page))
        await asyncio.gather(*tasks)

        successful_extractions = sum(1 for p in pages_to_process if 'extraction_error' not in p)
        failed_extractions = len(pages_to_process) - successful_extractions
        logger.info(f"Data extraction finished. Successful: {successful_extractions}, Failed: {failed_extractions}.")

        # --- Filtering and Aggregation Logic (remains the same) ---
        logger.info("Filtering and aggregating extracted data...")
        x_days = ctx.state.configuration.search_days
        cutoff_date = datetime.now().date() - timedelta(days=x_days)
        logger.info(f'Filtering articles published on or after: {cutoff_date} (or manually specified URLs)')

        def parse_pub_date(pub_date):
            if isinstance(pub_date, date_type): return pub_date
            if isinstance(pub_date, str):
                for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d"):
                    try: return datetime.strptime(pub_date, fmt).date()
                    except ValueError: pass
            logger.debug(f"Could not parse date: {pub_date}")
            return None

        articles = []
        logger.info(f"Starting filter process on {len(ctx.state.scraped_pages)} total pages (including failures).")
        manual_urls = set(ctx.state.configuration.urls or [])

        for page in ctx.state.scraped_pages:
            page_url = page.get('url', 'unknown URL')
            log_prefix = f"Filtering '{page_url}':"
            filter_reason = "Included"
            
            if page is None:
                logger.debug(f"{log_prefix} Skipping None page object.")
                continue

            if parse_err_msg := page.get('parsing_error'):
                 logger.info(f"{log_prefix} Excluded - Parsing error: {parse_err_msg}")
                 page['filter_reason'] = f"Parsing error: {escape(parse_err_msg)}"
                 continue

            if extract_err_msg := page.get('extraction_error'):
                logger.info(f"{log_prefix} Excluded - Extraction error: {extract_err_msg}")
                page['filter_reason'] = f"Extraction error: {escape(extract_err_msg)}"
                continue
            
            is_manual_url = page_url in manual_urls

            if is_manual_url:
                logger.info(f"{log_prefix} Force-including as it is a manually provided URL.")
                filter_reason = "Included (Manual URL)"
                page['filter_reason'] = filter_reason
                articles.append(page)
                continue

            page_type = page.get('webpage_type')
            if page_type != "article":
                logger.info(f"{log_prefix} Excluded - Not classified as 'article' (Type: {page_type}).")
                filter_reason = f"Not classified as 'article' (Type: {escape(str(page_type))})"
                page['filter_reason'] = filter_reason
                continue

            relevance = page.get('relevant')
            if relevance != "yes":
                logger.info(f"{log_prefix} Excluded - Not marked as 'relevant' (Relevance: {relevance}).")
                filter_reason = f"Not marked as 'relevant' (Relevance: {escape(str(relevance))})"
                page['filter_reason'] = filter_reason
                continue

            publication_date_obj = parse_pub_date(page.get('publication_date'))
            pub_date_str = page.get('publication_date', 'N/A')

            if publication_date_obj is None:
                logger.info(f"{log_prefix} Excluded - Could not parse publication date ('{pub_date_str}').")
                filter_reason = f"Could not parse publication date ('{escape(str(pub_date_str))}')"
                page['filter_reason'] = filter_reason
                continue
            if publication_date_obj < cutoff_date:
                logger.info(f"{log_prefix} Excluded - Publication date {publication_date_obj} is older than cutoff {cutoff_date}.")
                filter_reason = f"Publication date {publication_date_obj} older than cutoff {cutoff_date}"
                page['filter_reason'] = filter_reason
                continue

            logger.debug(f"{log_prefix} Included.")
            page['filter_reason'] = filter_reason
            articles.append(page)

        llm_facts_available = ctx.state.researched_info.facts_from_llm or []
        if not articles and not llm_facts_available:
            error_message = "No relevant articles found after filtering and no LLM facts available."
            logger.error(f"{node_name}: {error_message}")
            ctx.state.add_error(node_name, error_message)
            error_report = self._generate_error_report(ctx.state.errors)
            return End(f"ERROR: No content to write an article.\n\nError Log:\n{error_report}")
        
        # Aggregate Data
        existing_facts_from_llm = ctx.state.researched_info.facts_from_llm or []
        llm_fact_strings = [fact.fact_llm for fact in existing_facts_from_llm if fact.fact_llm]

        facts_from_articles = []
        combined_quotes_data = []
        combined_keywords = set()
        article_sources = set(manual_urls)
        article_texts_snippets = []

        for article in articles:
            if facts := article.get('facts'): facts_from_articles.extend(facts)
            if quotes := article.get('quotes'): combined_quotes_data.extend(quotes)
            if keywords := article.get('keywords'): combined_keywords.update(keywords)
            if url := article.get('url'): article_sources.add(url)
            if snippet := article.get('formated_article_short'): article_texts_snippets.append(snippet)

        combined_facts = llm_fact_strings + facts_from_articles
        if not combined_facts:
            logger.warning("No facts found after filtering. Article quality may suffer.")

        ctx.state.researched_info.quotes = combined_quotes_data or None
        ctx.state.researched_info.facts = combined_facts
        ctx.state.researched_info.facts_from_articles = facts_from_articles
        ctx.state.researched_info.keywords = list(combined_keywords)
        ctx.state.researched_info.article_texts = "\n\n==============================\n\n".join(article_texts_snippets)
        ctx.state.sources = sorted(list(article_sources))

        logger.info(f"Aggregated data: {len(combined_facts)} facts, {len(combined_quotes_data)} quotes, {len(ctx.state.sources)} sources.")
        return InstructionsNode()





###############################################################################
############################## Instructions Node ##############################


@dataclass
class InstructionsNode(ResilientNode):
    # --- Configure ResilientNode ---
    retry_counter_attr: str = "instructionsnode_tries"
    max_retries: int = 1
    timeout_seconds: int = 600

    async def _execute(self, ctx: GraphRunContext[State]) -> WritingNode | End:
        """
        Generates detailed writing instructions using a fallback model strategy.
        """
        node_name = self.__class__.__name__
        logger.info(f"Executing {node_name} logic...")


        # --- Instantiate Agent within _execute ---
        fallback_model = setup_fallback_model(NODE_MODEL_CONFIG[node_name])
        instructions_agent = Agent( 
            model=fallback_model,
            output_type=str,
            retries=1
        )

        # --- Core Logic ---
        article_texts = ctx.state.researched_info.article_texts or "No reference articles available."
        research_plan = ctx.state.research_plan.plan if ctx.state.research_plan else "No initial plan provided."
        topic = ctx.state.configuration.article_topic
        additional_instructions = ctx.state.configuration.additional_instructions

        if not topic:
            # This error will be caught by ResilientNode.run
            raise ValueError(f"{node_name}: Article topic is missing in configuration.")
        
        if additional_instructions is not None and additional_instructions not in ["None", "none", ""]:
            additional_instructions_formatted = f"### Additional Instructions and Context:\nThese are additional instructions to follow or context to include while writing the article:\n{additional_instructions}\nThey are very important and must be included."
        else:
            additional_instructions_formatted = ""
        
        user_prompt = instructions_agent_prompt.format( # Ensure prompt is accessible
            article_texts=article_texts,
            plan=research_plan,
            topic=topic,
            example_articles=example_articles,
            additional_instructions_formatted=additional_instructions_formatted,
        )
        # logger.debug(f"{node_name} prompt snippet: {user_prompt[:300]}...")

        # Run agent - uses fallback
        result = await instructions_agent.run(user_prompt=user_prompt)

        if result is None or not result.output: # Check for None or empty string
             raise ValueError(f"{node_name} agent run did not return valid data (instructions) after attempting models.")

        # --- Update State ---
        ctx.state.instructions = result.output
        logger.info("Successfully generated writing instructions.")


        # --- Return Next Node INSTANCE ---
        logger.info(f"Transitioning from {node_name} to WritingNode")
        return WritingNode() # Instantiate


###############################################################################
################################ Writing Node #################################


@dataclass
class WritingNode(ResilientNode):
    # --- Configure ResilientNode ---
    retry_counter_attr: str = "writingnode_tries"
    max_retries: int = 1
    timeout_seconds: int = 900 # 15 minutes

    async def _execute(self, ctx: GraphRunContext[State]) -> ReflectionNode | FollowUpNode | End:
        """
        Writes or revises the article using a fallback model strategy.
        Manages the reflection loop state.
        """
        node_name = self.__class__.__name__
        logger.info(f"Executing {node_name} logic (Round: {ctx.state.reflection_round})...")


        # --- Instantiate Agent within _execute ---
        fallback_model = setup_fallback_model(NODE_MODEL_CONFIG[node_name])
        writing_agent = Agent[None, str](
            model=fallback_model,
            output_type=str,
            retries=1
        )

        # --- Determine Prompt ---
        if ctx.state.reflection_round == 0:
            # Initial writing round
            facts_list = ctx.state.researched_info.facts or []
            facts_str = "\n - ".join(facts_list) if facts_list else "No facts available."
            keywords_list = ctx.state.researched_info.keywords or []
            keywords_str = ", ".join(keywords_list) if keywords_list else "N/A"
            quotes_list = ctx.state.researched_info.quotes or []
            
            quotes_str = "\n".join([f'"{escape(q.get("text") or "")}" - {escape(q.get("speaker") or "Unknown")} (Source: {escape(q.get("source") or "N/A")})' for q in quotes_list]) \
                         if quotes_list else "No quotes available."

            if not ctx.state.instructions:
                raise ValueError(f"{node_name}: Writing instructions are missing for initial draft.")

            user_prompt = writing_agent_prompt.format( # Ensure prompt is accessible
                topic=ctx.state.configuration.article_topic,
                facts=facts_str,
                keywords=keywords_str,
                quotes=quotes_str,
                instructions=ctx.state.instructions,
                current_date=ctx.state.current_date,
                example_articles=example_articles      
            )
            logger.info("Using initial writing prompt.")
        else:
            # Reflection round
            if not ctx.state.reflection_prompt:
                 raise ValueError(f"{node_name}: Reflection prompt is missing for round {ctx.state.reflection_round}.")

            user_prompt = ctx.state.reflection_prompt
            logger.info(f"Using reflection prompt for round {ctx.state.reflection_round}.")

        # logger.debug(f"Writer prompt (Round {ctx.state.reflection_round}) snippet: {user_prompt[:300]}...")

        # --- Run Agent ---
        # Run the agent, passing the current message history if it exists
        # The agent will use the fallback model sequence
        # logger.info(f'!!!ctx.state.messages: {ctx.state.messages}')
        try:
            result = await writing_agent.run(
                user_prompt=user_prompt,
                # Pass message history only if it's not empty, otherwise default might be used
                message_history=ctx.state.messages #if ctx.state.messages else None
            )
        except FallbackExceptionGroup as feg:
             # Re-raise to be caught by ResilientNode's run method
             logger.error(f"{node_name} failed: All fallback models exhausted during agent run.")
             raise feg
        except Exception as agent_error:
            # Catch other potential agent errors and re-raise for ResilientNode
            logger.error(f"{node_name} agent run failed: {agent_error}", exc_info=True)
            raise agent_error

        if result is None or not result.output: # Check for None or empty string result
            raise ValueError(f"{node_name} agent run did not return valid data (article) after attempting models.")

        # --- Update State ---
        # Update message history ALWAYS after a successful agent call
        ctx.state.messages = result.all_messages()

        # --- Determine Next Step ---
        if ctx.state.reflection_round > 0:
            # This was the revision round based on reflection
            ctx.state.finished_article = result.output # Store final article
            logger.info(f"Article revision complete (Round {ctx.state.reflection_round}). Proceeding to FollowUpNode.")
            
            logger.info(f"Transitioning from {node_name} to FollowUpNode")
            return FollowUpNode() # Instantiate
        else:
            # This was the first writing round
            # Draft is in result.data (and messages). Don't set finished_article yet.
            logger.info("Initial article draft complete. Proceeding to ReflectionNode.")
            
            logger.info(f"Transitioning from {node_name} to ReflectionNode")
            return ReflectionNode() # Instantiate


###############################################################################
############################### Reflection Node ###############################


@dataclass
class ReflectionNode(ResilientNode):
    # --- Configure ResilientNode ---
    retry_counter_attr: str = "reflectionnode_tries"
    max_retries: int = 1
    timeout_seconds: int = 600

    async def _execute(self, ctx: GraphRunContext[State]) -> WritingNode | End:
        """
        Analyzes the draft article, generates feedback using a fallback model strategy,
        and prepares the prompt for the next writing round.
        """
        node_name = self.__class__.__name__
        logger.info(f"Executing {node_name} logic...")

        # --- Instantiate Agent within _execute ---
        fallback_model = setup_fallback_model(NODE_MODEL_CONFIG[node_name])
        reflection_agent = Agent(
            model=fallback_model,
            output_type=str, 
            retries=1
        )

        # --- Prepare Prompt ---
        benchmark_articles = ctx.state.researched_info.article_texts or "No benchmark articles available."
        user_prompt = reflection_agent_prompt.format( 
            benchmark_articles=benchmark_articles,
            example_articles=example_articles 
        )
        # logger.debug(f"{node_name} prompt snippet: {user_prompt[:300]}...")

        # --- Run Agent ---
        # Crucially, run the agent with the message history which contains the draft
        if not ctx.state.messages:
             # This indicates a likely logic error earlier in the graph.
             raise ValueError(f"{node_name}: Message history is empty. Cannot perform reflection.")

        try:
            result = await reflection_agent.run(
                user_prompt=user_prompt,
                message_history=ctx.state.messages # Pass history including the draft
            )
        except FallbackExceptionGroup as feg:
             # Re-raise for ResilientNode
             logger.error(f"{node_name} failed: All fallback models exhausted during agent run.")
             raise feg
        except Exception as agent_error:
            # Re-raise other agent errors for ResilientNode
            logger.error(f"{node_name} agent run failed: {agent_error}", exc_info=True)
            raise agent_error


        if result is None or not result.output: # Check for None or empty feedback
            raise ValueError(f"{node_name} agent run did not return valid data (feedback) after attempting models.")

        # --- Process Result & Update State ---
        feedback = result.output
        # Construct the full feedback prompt for the next WritingNode execution
        full_reflection_prompt = (
            f'Follow these instructions to improve your article:\n{feedback}\n\n'
            f'--- Benchmark Articles for Reference ---\n'
            f'{benchmark_articles}'
        )

        ctx.state.reflection_prompt = full_reflection_prompt
        ctx.state.reflection_round += 1 # Increment the round counter
        # Don't update ctx.state.messages here unless you want reflection in history

        logger.info(f"Reflection complete. Generated feedback prompt for round {ctx.state.reflection_round}.")



        # --- Return Next Node INSTANCE ---
        logger.info(f"Transitioning from {node_name} back to WritingNode")
        return WritingNode() # Instantiate for revision round

###############################################################################
############################## Follow up Node ##############################

class FollowUp(BaseModel):
    alternative_titles: list[str] = Field(default_factory=list)
    followup_articles: list[str] = Field(default_factory=list)



@dataclass
class FollowUpNode(ResilientNode):
    # --- Configure ResilientNode ---
    retry_counter_attr: str = "followupnode_tries"
    max_retries: int = 1
    timeout_seconds: int = 600

    async def _execute(self, ctx: GraphRunContext[State]) -> End:
        """
        Generates follow-up content using a fallback model strategy and
        formats the final output.
        """
        node_name = self.__class__.__name__
        logger.info(f"Executing {node_name} logic...")

        if not ctx.state.finished_article:
            error_msg = f"{node_name}: Finished article is missing in state. Cannot generate follow-up content."
            logger.error(error_msg)
            ctx.state.add_error(node_name, "Finished article missing in state.")
           
            error_report = self._generate_error_report(ctx.state.errors) # Use helper from ResilientNode
            return End(f"ERROR: Finished article missing.\n\nError Log:\n{error_report}")

        fallback_model = setup_fallback_model(NODE_MODEL_CONFIG[node_name])
        followup_agent = Agent(
            model=fallback_model,
            output_type=FollowUp,
            retries=1
        )
        # --------------------------------------------------------------

        # --- Prepare Prompt ---
        user_prompt = followup_agent_prompt.format( # Ensure prompt is accessible
            finished_article=ctx.state.finished_article
        )
        # logger.debug(f"{node_name} prompt snippet: {user_prompt[:300]}...")

        # --- Run Agent ---
        try:
            result = await followup_agent.run(user_prompt=user_prompt)
            # Handle case where agent runs but returns None or no data
            if result is None or result.output is None:
                    logger.warning(f"{node_name} agent run succeeded but returned no data. Proceeding without suggestions.")
                    follow_up_data = FollowUp(alternative_titles=[], followup_articles=[])
                    ctx.state.add_error(node_name, "Follow-up agent returned no suggestions (result was None or empty).")
            else:
                    follow_up_data = result.output

        except FallbackExceptionGroup as feg:
            # Log the error, add to state, but proceed without follow-up suggestions
            error_message = f"All fallback models failed for follow-up generation."
            logger.error(f"{node_name}: {error_message}")
            ctx.state.add_error(node_name, error_message)
            for i, exc in enumerate(feg.exceptions):
                logger.error(f"  - Model {i+1}: {type(exc).__name__}: {exc}")
            follow_up_data = FollowUp(alternative_titles=[], followup_articles=[]) # Default to empty

        except Exception as agent_error:
            # Log other agent errors, add to state, proceed without suggestions
            error_message = f"Unexpected error during follow-up agent run: {agent_error}"
            logger.error(f"{node_name}: {error_message}", exc_info=True)
            ctx.state.add_error(node_name, error_message)
            follow_up_data = FollowUp(alternative_titles=[], followup_articles=[]) # Default to empty


        # --- Construct the final HTML Output ---
        # (This part remains the same, using follow_up_data which is now guaranteed to exist)
        logger.info("Constructing final HTML output...")

        article_html = f"<article>\n{ctx.state.finished_article}\n</article>" 
        titles_html = self._generate_list_html("Alternatywne tytuły", follow_up_data.alternative_titles)
        topics_html = self._generate_list_html("Tematy do rozważenia", follow_up_data.followup_articles)
        sources_html = self._generate_detailed_sources_html(
            "Źródła i Status Przetwarzania",
            ctx.state.scraped_pages
        )
        quotes_html = self._generate_quotes_html(ctx.state.researched_info.quotes)
        article_facts_html = self._generate_list_html("Fakty z artykułów źródłowych", ctx.state.researched_info.facts_from_articles)
        llm_facts_html = self._generate_llm_facts_html(ctx.state.researched_info.facts_from_llm)
        error_report_html = self._generate_error_report_html(ctx.state.errors) # Use helper

        full_result = f"""<!DOCTYPE html>
<html>
<head>
<title>Article Result</title>
<meta charset="UTF-8">
<style>
  body {{ font-family: sans-serif; margin: 20px; }}
  article {{ border: 1px solid #ccc; padding: 15px; margin-bottom: 20px; background-color: #f9f9f9; }}
  section {{ margin-bottom: 20px; border: 1px solid #eee; padding: 0 15px 15px 15px; }}
  h1, h2 {{ color: #333; }}
  h1 {{ border-bottom: 2px solid #ccc; padding-bottom: 5px; }}
  h2 {{ border-bottom: 1px solid #eee; padding-bottom: 3px; }}
  ul {{ list-style-type: disc; margin-left: 20px; }}
  li {{ margin-bottom: 5px; }}
  blockquote {{ border-left: 3px solid #ccc; padding-left: 10px; margin-left: 0; font-style: italic; color: #555; }}
  strong {{ font-weight: bold; }}
  .source-item {{ margin-bottom: 8px; }}
  .source-url {{ font-weight: bold; }}
  .source-status {{ font-style: italic; margin-left: 10px; padding: 2px 5px; border-radius: 3px; }}
  .status-included {{ color: #2a8a2a; background-color: #e9f5e9; }}
  .status-excluded {{ color: #b95000; background-color: #fff8e1; }}
  .status-error {{ color: #c00; background-color: #fdecea; }} /* For extraction/parsing errors */
  .error-report {{ border-color: #d32f2f; background-color: #ffebee; }} /* Style error report section */
  .error-report h2 {{ color: #c00; }}
</style>
</head>
<body>
{article_html}
{error_report_html}
{titles_html}
{topics_html}
{sources_html}
{quotes_html}
{article_facts_html}
{llm_facts_html}
</body>
</html>
"""
        # Save final state including any errors added in this node
    
        logger.info("FollowUpNode complete. Returning final output.")
        # This node always ends the graph
        return End(full_result)


    # --- Helper methods for HTML generation ---
    # (Keep these helpers as they were: _generate_list_html, _generate_quotes_html,
    #  _generate_llm_facts_html, _generate_error_report_html, _generate_detailed_sources_html)
    # Make sure _generate_error_report is also defined if used in initial check

    def _generate_list_html(self, title: str, items: Optional[List[str]]) -> str:
        """Generates HTML for a simple list section."""
        if not items:
            content = "<ul><li>No items available.</li></ul>"
        else:
            list_items = "".join(f"<li>{escape(item)}</li>" for item in items)
            content = f"<ul>{list_items}</ul>"
        return f"<section><h2>{escape(title)}</h2>{content}</section>"

    def _generate_quotes_html(self, quotes: Optional[list[dict]]) -> str:
        """Generates HTML for the quotes section."""
        title = "Cytaty"
        if not quotes:
            content = "<ul><li>No quotes available.</li></ul>"
        else:
            list_items = []
            for q in quotes:

                source_parts = []
                if original_source := q.get('source'):
                    source_parts.append(escape(original_source))
                
                if page_url := q.get('page_url'):
                    page_link = f'<a href="{escape(page_url)}" target="_blank">znaleziono na stronie</a>'
                    source_parts.append(page_link)

                source_details = ' / '.join(source_parts) or 'N/A'

                # Use `or` fallback to prevent escaping None values.
                list_items.append(
                    f"<li>{escape(q.get('text') or 'N/A')} - {escape(q.get('speaker') or 'Unknown')} (Źródło: {source_details})</li>"
                )

            content = f"<ul>{''.join(list_items)}</ul>"
        return f"<section><h2>{escape(title)}</h2>{content}</section>"

    def _generate_llm_facts_html(self, llm_facts: Optional[list[FactFromLlm]]) -> str:
        """Generates HTML for the LLM facts section."""
        title = "LLM Fakty i ich źródła"
        if not llm_facts:
            content = "<ul><li>No LLM facts available.</li></ul>"
        else:
            list_items = "".join(
                f"<li>{escape(f.fact_llm or 'N/A')} (Źródło: {escape(f.source or 'N/A')})</li>"
                for f in llm_facts
            )
            content = f"<ul>{list_items}</ul>"
        return f"<section><h2>{escape(title)}</h2>{content}</section>"

    def _generate_error_report_html(self, errors: list[dict[str, str]]) -> str:
        """Generates an HTML section reporting errors logged during the run."""
        if not errors: return ""
        title = "Execution Errors Report"
        list_items = "".join(
            f"<li><strong>{escape(err.get('node', 'Unknown Node'))}:</strong> {escape(err.get('error', 'Unknown Error'))}</li>"
            for err in errors
        )
        content = f"<ul>{list_items}</ul>"
        return f"<section class='error-report'><h2>{escape(title)}</h2>{content}</section>"

    def _generate_error_report(self, errors: list[dict[str, str]]) -> str:
        """Generates a plain text error report."""
        # Ensure this helper is present if needed by the error check at the start
        if not errors: return "No errors reported."
        report = ""
        for err in errors:
             report += f"- Node: {escape(err.get('node', 'Unknown Node'))}, Error: {escape(err.get('error', 'Unknown Error'))}\n"
        return report

    def _generate_detailed_sources_html(self, title: str, all_pages: list[dict]) -> str:
        """Generates HTML for sources, showing status and filter reason."""
        if not all_pages:
            content = "<ul><li>No sources were processed.</li></ul>"
        else:
            list_items = ""
            # Sort by URL for consistent output
            for page in sorted(all_pages, key=lambda p: p.get('url', '') if p else ''):
                if not page: continue

                url = page.get('url', 'N/A')
                reason = page.get('filter_reason', 'Status unknown')
                
                # ### FIX: Updated logic to correctly classify and display status ###
                status_class = ""
                status_text = ""

                # Check for inclusion first (covers manual and regular inclusion)
                if reason.startswith("Included"):
                    status_class = "status-included" # Green style
                    if reason == "Included (Manual URL)":
                        status_text = "Included (Manually Provided)"
                    else:
                        status_text = "Included in final article"
                # Check for processing errors
                elif "error" in reason.lower():
                    status_class = "status-error" # Red style
                    status_text = f"Processing Error ({escape(reason)})"
                # All other cases are considered excluded
                else:
                    status_class = "status-excluded" # Orange/Yellow style
                    status_text = f"Excluded ({escape(reason)})"

                list_items += (
                    f"<li class='source-item'>"
                    f"<span class='source-url'>{escape(url)}</span>"
                    f" - <span class='source-status {status_class}'>{status_text}</span>"
                    f"</li>"
                )

            content = f"<ul>{list_items}</ul>"
        return f"<section><h2>{escape(title)}</h2>{content}</section>"


###############################################################################
# Class wrapper so you can use it in other parts of your code
###############################################################################
class ArticleWriter:
    @staticmethod
    def write_article(
        article_topic: str,
        domains: list[str] = [],
        urls: list[str] = [],  # <-- new parameter
        number_of_queries: int = 2,
        scraping_model: str = "",
        max_search_results: int = 4,
        search_days: int = 500,
        provide_llm_facts: Literal["yes", "no"] = "no",
        extraction_mode: Literal["markdown", "html", "llm"] = "markdown",
        additional_instructions: Optional[str] = None,
    ) -> str:
        async def _run_graph():
            state = State(
                configuration=Configuration(
                    article_topic=article_topic,
                    domains=domains,
                    urls=urls or [],  # <-- assign to config
                    number_of_queries=number_of_queries,
                    scraping_model=scraping_model,
                    max_search_results=max_search_results,
                    search_days=search_days,
                    extraction_mode=extraction_mode,
                    provide_llm_facts=provide_llm_facts,
                    additional_instructions = additional_instructions

                )
            )
            graph = Graph(nodes=(
                SearchNode, ScrapingNode, ParsingNode,
                DataExtractionNode, InstructionsNode,
                WritingNode, ReflectionNode, FollowUpNode, LlmKnowledgeNode
            ))
            response = await graph.run(SearchNode(), state=state)
            return response.output

        final_article = asyncio.run(_run_graph())
        return final_article



###############################################################################
# Main
###############################################################################
if __name__ == "__main__":
    article = ArticleWriter.write_article(
        article_topic="Ludzie przetarli oczy ze zdumienia. Zobaczyli, co Nawrocki założył na mecz i zawrzało",
        domains=[],  # example domains
        urls=['https://swiatgwiazd.pl/ludzie-nie-wierza-co-nawrocki-wlozyl-na-siebie-na-mecz-zapomnial-ze-jest-prezydentem-ks-mjj-120825'],       # example URLs
        number_of_queries=1,
        scraping_model="",        # specify your scraping model if needed
        max_search_results=2,
        search_days=30,
        extraction_mode="markdown",
        provide_llm_facts="no",
        additional_instructions = None
    )
    print(article)

