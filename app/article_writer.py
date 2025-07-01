from __future__ import annotations
import asyncio
import os
import re
from typing import List, Literal, Optional, Dict, Type
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
from llm_models import setup_fallback_model


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
            # save_state(ctx.state)
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
            save_state(ctx.state) # Save state after incrementing counter and adding error
            logger.warning(f"Retrying {node_name} (Attempt {current_retries + 2}/{self.max_retries + 1})...")
            return self.__class__()
        else:
            final_error_msg = f"ERROR: {node_name} failed permanently after {self.max_retries + 1} attempts. Last error: {error_message}"
            logger.error(final_error_msg)
            # Ensure state is saved with the final error logged
            save_state(ctx.state)
            # Append detailed error report from state to the End message
            error_report = self._generate_error_report(ctx.state.errors) # Assuming helper exists or add it
            return End(f"{final_error_msg}\n\nError Log:\n{error_report}")

    # Helper method to generate error report (similar to FollowUpNode)
    def _generate_error_report(self, errors: List[Dict[str, str]]) -> str:
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
#SearchNode
model_names = ["gpt-4.1-mini", "gemini-2.5-flash-preview-04-17"]
logger.info(f"--- Using FallbackModel for SearchNode with models: {model_names} ---")
search_node_fallback_model = setup_fallback_model(model_names)

#LlmKnowledgeNode
model_names = ["gpt-4.1-mini", "gemini-2.5-flash-preview-04-17"]
logger.info(f"--- Using FallbackModel for LlmKnowledgeNode with models: {model_names} ---")
llmknowledge_node_fallback_model = setup_fallback_model(model_names)

#ParsingNode
model_names = ["gemini-2.5-pro-preview-06-05", "o3-mini", "gemini-2.5-flash-preview-04-17"]
logger.info(f"--- Using FallbackModel for ParsingNode with models: {model_names} ---")
parsing_node_fallback_model = setup_fallback_model(model_names)

#DataExtractionNode
model_names = ["gemini-2.5-pro-preview-06-05", "o3-mini", "gemini-2.5-flash-preview-04-17"]
logger.info(f"--- Using FallbackModel for DataExtractionNode with models: {model_names} ---")
dataextraction_node_fallback_model = setup_fallback_model(model_names)

#InstructionsNode
model_names = ["gemini-2.5-pro-preview-06-05", "o3-mini", "gemini-2.5-flash-preview-04-17"]
logger.info(f"--- Using FallbackModel for InstructionsNode with models: {model_names} ---")
instructions_node_fallback_model = setup_fallback_model(model_names)

#WritingNode
model_names = ["gemini-2.5-pro-preview-06-05", "gpt-4.1"]
logger.info(f"--- Using FallbackModel for WritingNode with models: {model_names} ---")
writing_node_fallback_model = setup_fallback_model(model_names)

#ReflectionNode
model_names = ["gemini-2.5-pro-preview-06-05", "gpt-4.1"]
logger.info(f"--- Using FallbackModel for ReflectionNode with models: {model_names} ---")
reflection_node_fallback_model = setup_fallback_model(model_names)

#FollowUpNode
model_names = ["gemini-2.5-pro-preview-06-05", "o3-mini", "gemini-2.5-flash-preview-04-17"]
logger.info(f"--- Using FallbackModel for FollowUpNode with models: {model_names} ---")
followUp_node_fallback_model = setup_fallback_model(model_names)

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
    provide_llm_facts: Literal["yes", "no"] = "yes",



class ResearchPlan(BaseModel):
    queries: list[str] = Field(default_factory=list)
    plan: str = ""
    keywords: list[str] = Field(default_factory=list)



class Quote(BaseModel):
    text: str | None
    speaker: str | None
    source: str | None


class ResearchedInfo(BaseModel):
    quotes: list[Quote] | None = None
    facts: list[str] | None = None
    keywords: list[str] | None = None
    article_texts: str | None = None
    facts_from_llm: list[FactFromLlm] | None  = None
    facts_from_articles: list[str] | None = None


class FactFromLlm(BaseModel):
    fact_llm: str | None
    source: str | None


class State(BaseModel):
    current_date: date_type = current_date
    configuration: Configuration
    reflection_round: int = 0
    instructions: str = ""
    reflection_prompt: str = ""
    research_plan: ResearchPlan = None
    scraped_pages: list[Dict] = Field(default_factory=list)
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
    errors: List[Dict[str, str]] = Field(default_factory=list, description="List of errors encountered during the graph run.")
    
    # --- Optional: Add helper to add errors ---
    def add_error(self, node_name: str, error_message: str):
        self.errors.append({"node": node_name, "error": error_message})
        
        
        
###############################################################################
# Helper functions
###############################################################################
def get_state_file_path(filename: str = "state.json") -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, filename)

def save_state(state: State, filename: str = "state.json") -> None:
    file_path = get_state_file_path(filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(state.model_dump_json())

def load_state(filename: str = "state.json") -> State:
    file_path = get_state_file_path(filename)
    with open(file_path, "r", encoding="utf-8") as f:
        state_json = f.read()
    return State.model_validate_json(state_json)

###############################################################################
# Nodes
###############################################################################
############################### Search Node ###################################




research_agent_prompt = """You are a research assistant supporting an article writer. 
Your role is to create a well-structured, high-level plan for a short web article based on the provided topic.

Your response should follow this structure:

### Outline of Key Points:
- Provide a clear and concise outline of the main ideas and subtopics that should be covered in the article.
- Begin with an **engaging article lead** that introduces the story or topic in a way that captures the reader’s interest but does not reveal everything upfront.
- Organize the main points logically for an engaging and informative read, ensuring smooth transitions between sections.
- Focus on delivering value to the target audience, making the article both informative and compelling.

### Compelling Headlines:
- Suggest at least two engaging and click-worthy article titles.
- Titles should be optimized for user engagement and search engine visibility.

### SEO Keywords:
- List relevant high-search-volume keywords that will help the article rank better in search engines.
- Ensure a mix of short-tail and long-tail keywords.

### Research Queries:
- Provide exactly {number_of_queries} well-crafted Google search queries to assist with further research.
- The queries should be diverse and structured to yield a broad range of valuable insights.

### Language:
- Write your entire response in the language relevant to the article topic.
- Maintain a professional yet engaging tone.

### Date:
- Consider the current date: {current_date} when making suggestions to ensure relevance.

### Article Topic:
{article_topic}

### All output must always be in the language of the article topic.
"""



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
        research_agent = Agent[None, ResearchPlan](
            model=search_node_fallback_model,
            result_type=ResearchPlan,
            # retries=1 # Optional
        )

        # --- Core Logic ---
        prompt = research_agent_prompt.format(
            current_date=ctx.state.current_date,
            article_topic=ctx.state.configuration.article_topic,
            number_of_queries=ctx.state.configuration.number_of_queries
        )
        result = await research_agent.run(user_prompt=prompt)

        if not result or not result.data:
             raise ValueError(f"{node_name} agent run did not return valid data after attempting models.")

        # --- Update State ---
        ctx.state.research_plan = result.data
        ctx.state.research_plan.queries.append(ctx.state.configuration.article_topic)
        save_state(ctx.state)
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

llmknowledge_agent_prompt = """
You are a meticulous research assistant providing facts to support an article.

### Article Information:
- General Topic: {article_topic}
- Research Queries: {search_queries}

### Guidelines:
- Provide verified facts.
- Ensure all information is CURRENT (consider today's date: {current_date}).
- If solid information is unavailable, explicitly state "No verified information found."
- Provide a credible facts you provide (domain or citation).


Your accuracy and clarity are essential. Give everything that is relevant and can be used to write the article.
"""


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




        # --- Instantiate Agent within _execute ---
        # Use the FallbackModel instance for the agent
        llmknowledge_agent = Agent( # Agent variable is local to _execute
            model=llmknowledge_node_fallback_model,
            result_type=List[FactFromLlm] # Ensure FactFromLlm is imported/defined
            # retries=1 # Optional agent-level retries
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
        if result is None or result.data is None: # Check for None data specifically
             # result.data could be an empty list [], which is valid, so check for None
             raise ValueError(f"{node_name} agent run did not return valid data after attempting models.")

        # --- Update State ---
        ctx.state.researched_info.facts_from_llm = result.data
        logger.info(f'LLM facts retrieved: {len(ctx.state.researched_info.facts_from_llm)} items.')

        # Save state
        save_state(ctx.state)

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
    # Potentially longer timeout for scraping multiple sites? Adjust as needed.
    timeout_seconds: int = 720 # Example: 12 minutes

    # --- Corrected signature ---
    async def _execute(self, ctx: GraphRunContext[State]) -> ParsingNode | End:
        """
        Searches for relevant URLs using generated queries and scrapes their content.
        """
        logger.info("Executing ScrapingNode logic...")
        # ctx.state = load_state() # Generally not needed here

        # Initialize scraper
        scraper = SearchAndScrape(
            search_domains=ctx.state.configuration.domains,
            max_results=ctx.state.configuration.max_search_results,
            days=ctx.state.configuration.search_days,
            model=ctx.state.configuration.scraping_model,
            # Ensure extraction_mode is set correctly if needed by SearchAndScrape init
            extraction_mode=ctx.state.configuration.extraction_mode
        )

        # Define search tasks using asyncio.to_thread for potentially blocking calls
        search_tasks = [
            asyncio.create_task(asyncio.to_thread(scraper.search_urls, query))
            for query in ctx.state.research_plan.queries
        ]
        # Gather search results
        search_results = await asyncio.gather(*search_tasks)

        # Process search results to get unique URLs and descriptions
        unique_urls = set()
        combined_descriptions = {}
        for urls, desc_map in search_results:
            if urls: # Check if urls list is not None or empty
               unique_urls.update(urls)
            if desc_map: # Check if desc_map is not None or empty
                combined_descriptions.update(desc_map)

        # Add manually provided URLs
        unique_urls.update(ctx.state.configuration.urls)
        # Convert set to list for scraping, filtering out any empty or None URLs
        urls_to_scrape = [url for url in unique_urls if url]

        if not urls_to_scrape:
            logger.warning("No unique URLs found or provided to scrape. Moving to ParsingNode.")
            # We can proceed to ParsingNode which should handle empty input gracefully,
            # or decide to end here if scraping is essential. Let's proceed for now.
            # Optionally save state if needed even with no scraping.
            # save_state(ctx.state)
            return ParsingNode()

        logger.info(f"Scraping {len(urls_to_scrape)} unique URLs...")

        # Scrape the identified URLs
        # Assuming scrape_urls is async; if not, wrap in asyncio.to_thread
        scrape_result = await scraper.scrape_urls(urls_to_scrape, description_mapping=combined_descriptions)

        # Update state with scraped pages
        ctx.state.scraped_pages = scrape_result.get("aggregated_results", []) # Use .get for safety
        logger.info(f"Scraping complete. Found {len(ctx.state.scraped_pages)} pages.")

        # Save state on successful completion
        save_state(ctx.state)

        # Return INSTANCE of the next node
        return ParsingNode()


###############################################################################
################################ Parsing Node #################################


class ParsedArticle(BaseModel):
    webpage_type: Literal['article', 'other']
    parsed_article: str

parsing_agent_prompt = """**Task:** Extract the **article text** from the provided HTML, if and only if it is an article.  

---

### Step 1: Determine if the Content is an Article  
The content should be classified as an **article** if it meets **all** of the following conditions:  
- Contains a **clear article title** (e.g., in `<h1>`, `<title>`, or similar).  
- Contains **multiple paragraphs** (`<p>`) that form a coherent text.  
- May include **publication date** and an **article lead** (optional but helpful).  
- Structured with **headings** (`<h2>`, `<h3>`, `<h4>`) where applicable.  

If these conditions **are not met**, classify the content as `"other"` and return `parsed_article = None`.

---

### Step 2: Extract the Article Text  
If the content is classified as an **article**, extract and preserve:  
- **Publication date** (if present).  For the reference today's date is {current_date}
- **Article title** (if present).  
- **Article lead** (the introductory section setting up the topic).  
- **Headings** (`<h2>`, `<h3>`, `<h4>`) to maintain structure.  
- **Paragraphs** (verbatim, without modifications).  
- **Strong/emphasized text** (`<strong>`, `<em>` tags should be retained).  

---

### Step 3: Formatting Rules  
- **Preserve HTML structure** for headings, bold/strong text, and other inline elements.  
- **Do NOT** modify, summarize, or interpret the article—extract it **exactly as written**.  
- **Remove**:
  - Hyperlinks
  - Images
  - Author information
  - Advertisements
  - Navigation elements  

---

### Input:
The following HTML content should be parsed:
{html}
"""


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
        """
        node_name = self.__class__.__name__
        logger.info(f"Executing {node_name} logic...")

        enc = tiktoken.get_encoding("cl100k_base")
        MAX_TOKENS = 150_000

        pages_to_process = ctx.state.scraped_pages
        if not pages_to_process:
            logger.warning("No scraped pages found to parse. Proceeding.")
            return DataExtractionNode() # Instantiate

        tasks = []

        async def process_page(page: dict):
            """Inner function to process a single page using FallbackModel."""
            page_url = page.get('url', 'unknown URL')
            page_node_log_prefix = f"{node_name} - Page {page_url}:"

            try:
                article_body = page.get("article_body", "")
                if not article_body:
                    logger.warning(f"{page_node_log_prefix} No article_body found. Skipping parsing.")
                    page['webpage_type'] = 'other'
                    page['parsed_article'] = None
                    return

                parsing_agent = Agent( # Agent is local to this page processing task
                    model=parsing_node_fallback_model,
                    result_type=ParsedArticle, # Ensure ParsedArticle is defined/imported
                    retries=1 # Optional: Agent retries *before* falling back
                )
                # --------------------------------------------------------------

                tokens = enc.encode(article_body)
                token_count = len(tokens)

                if token_count > MAX_TOKENS:
                    logger.warning(
                        f"{page_node_log_prefix} Article has {token_count} tokens, exceeding {MAX_TOKENS}. Truncating."
                    )
                    tokens = tokens[:MAX_TOKENS]
                    article_body = enc.decode(tokens)
                    page["article_body_truncated"] = True

                prompt = parsing_agent_prompt.format(html=article_body, current_date=ctx.state.current_date,) # Ensure prompt is accessible

                # Run agent - it will use the fallback sequence
                result = await parsing_agent.run(user_prompt=prompt)

                if result is None or result.data is None:
                     raise ValueError("Parsing agent run did not return valid data after attempting models.")

                # Update the page dictionary directly
                page['webpage_type'] = result.data.webpage_type
                page['parsed_article'] = result.data.parsed_article
                logger.debug(f"{page_node_log_prefix} Successfully parsed as {result.data.webpage_type}")

            except FallbackExceptionGroup as feg:
                # Catch fallback errors specific to this page
                error_message = f"All fallback models failed for page {page_url}."
                logger.error(f"{page_node_log_prefix} {error_message}")
                for i, exc in enumerate(feg.exceptions):
                     # Log details without crashing the whole node
                     logger.error(f"  - Model {i+1}: {type(exc).__name__}: {exc}")
                page['webpage_type'] = 'other'
                page['parsed_article'] = None
                page['parsing_error'] = error_message # Store specific error

            except Exception as error:
                # Catch other errors for this page (incl. ValueError from model check)
                logger.error(f"{page_node_log_prefix} Error processing: {error}", exc_info=True)
                page['webpage_type'] = 'other'
                page['parsed_article'] = None
                page['parsing_error'] = str(error)

        # Create tasks for processing pages
        for page in pages_to_process:
            tasks.append(process_page(page))

        # Run all parsing tasks concurrently
        await asyncio.gather(*tasks)

        # Filter out pages that failed parsing before saving state? Optional.
        # Currently, failed pages are marked with 'parsing_error'.
        successful_parses = sum(1 for p in pages_to_process if 'parsing_error' not in p and p.get('parsed_article') is not None)
        failed_parses = len(pages_to_process) - successful_parses
        logger.info(f"Parsing finished for {len(pages_to_process)} pages. Successful: {successful_parses}, Failed: {failed_parses}.")

        # Save the updated state (including pages with errors)
        save_state(ctx.state)

        # Proceed to the next node
        logger.info(f"Transitioning from {node_name} to DataExtractionNode")
        return DataExtractionNode() # Instantiate


###############################################################################
############################# DataExtraction Node #############################



data_extraction_agent_prompt = """
Your task is to analyze text and determine whether it is an **article** or another type of page (e.g., main page, category page, tag page, etc.), then extract key information.

### Step 1: Identify Webpage Type
- If the webpage contains an **article title, lead, and main text**, classify it as **"article"**.
- If the page lacks these elements (e.g., homepage, category page, listing page), classify it as **"other"**.

### Step 2: Extract Key Information (for articles only)
1. **Facts**:
   - Extract as many verifiable facts as possible from the article.
   - Ensure accuracy and objectivity.
   - Facts should be concise and reflect the original content.

2. **Quotes**:
   - Identify all direct quotes in the article.
   - Each quote must:
     - Be an **exact citation** from the article.
     - Have a **specific speaker** (not the article's author).
     - Include the **source** if available.

3. **SEO Keywords**:
   - Identify **important high-search-volume Google keywords** used within the article.
   - Focus on keywords relevant to the article topic.
   - Include a mix of **short-tail** and **long-tail** keywords.

4. **Publication Date**

### Step 3: Decide if it is relevant for the topic below (for articles only)
{topic}

### Text:
{text}

Output must be in the language of the text.
"""

article_snippet = """URL: {url}
------------------------------
TITLE: {title}
------------------------------
DESCRIPTION: {description}
------------------------------
ARTICLE TEXT:
{article_text}
==============================
"""

article_snippet_short = """TITLE: {title}
------------------------------
ARTICLE TEXT:
{article_text}
==============================
"""

class ResearchedArticle(BaseModel):
    webpage_type: Literal['article', 'other']
    relevant: Literal['yes', 'no']
    publication_date: date_type
    facts: Optional[List[str]]
    quotes: Optional[List[Quote]]
    keywords: Optional[List[str]]
    
    
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
        model strategy for each relevant page, filters, and aggregates data.
        """
        node_name = self.__class__.__name__
        logger.info(f"Executing {node_name} logic...")

        # Filter pages with actual parsed content first, excluding those with parsing errors
        pages_to_process = [
            page for page in ctx.state.scraped_pages
            if page and page.get('parsed_article') and not page.get('parsing_error')
        ]

        if not pages_to_process:
            logger.warning(f"{node_name}: No successfully parsed pages found to extract data from.")
            if not ctx.state.researched_info.facts_from_llm:
                 logger.error(f"{node_name}: No parsed pages AND no LLM facts found. Ending run.")
                 ctx.state.add_error(node_name, "No content (parsed pages or LLM facts) available for processing.")
                 save_state(ctx.state)
                 error_report = self._generate_error_report(ctx.state.errors)
                 return End(f"ERROR: No content available to write an article.\n\nError Log:\n{error_report}")
            else:
                logger.info(f"{node_name}: Proceeding with only LLM facts.")
                llm_facts_preserved = ctx.state.researched_info.facts_from_llm or []
                llm_fact_strings = [f.fact_llm for f in llm_facts_preserved if f.fact_llm]
                manual_urls = set(ctx.state.configuration.urls or [])
                ctx.state.researched_info = ResearchedInfo(
                     facts=llm_fact_strings,
                     facts_from_articles=[],
                     facts_from_llm=llm_facts_preserved,
                     quotes=[],
                     keywords=[],
                     article_texts=""
                )
                ctx.state.sources = list(manual_urls)
                save_state(ctx.state)
                logger.info(f"Transitioning from {node_name} to InstructionsNode (only LLM facts)")
                return InstructionsNode()

        tasks = []

        async def process_page(page: dict):
            # ... (the process_page inner function remains unchanged)
            page_url = page.get('url', 'unknown URL')
            page_node_log_prefix = f"{node_name} - Page {page_url}:"

            try:
                parsed_article = page.get("parsed_article", "")

                data_extraction_agent = Agent(
                    model=dataextraction_node_fallback_model,
                    result_type=ResearchedArticle,
                    retries=1
                )

                title_match = re.search(r"<h1.*?>(.*?)</h1>", parsed_article, re.IGNORECASE | re.DOTALL)
                title = title_match.group(1).strip() if title_match else page.get('title', "Title not found")
                article_text_no_h1 = re.sub(r"<h1.*?>.*?</h1>", "", parsed_article, flags=re.IGNORECASE | re.DOTALL).strip()

                page['formated_article'] = article_snippet.format(
                    url=page_url,
                    title=title,
                    description=page.get("description", "No description available"),
                    article_text=article_text_no_h1
                )
                page['formated_article_short'] = article_snippet_short.format(
                    title=title,
                    article_text=article_text_no_h1
                )
                prompt = data_extraction_agent_prompt.format(
                    text=page['formated_article'],
                    topic=ctx.state.configuration.article_topic
                )
                researched_article_result = await data_extraction_agent.run(user_prompt=prompt)

                if researched_article_result is None or researched_article_result.data is None:
                     raise ValueError("Data extraction agent run did not return valid data after attempting models.")

                data = researched_article_result.data
                page['webpage_type'] = data.webpage_type
                page['relevant'] = data.relevant
                page['facts'] = data.facts
                page['quotes'] = [q.model_dump() for q in data.quotes] if data.quotes else []
                page['keywords'] = data.keywords
                page['publication_date'] = data.publication_date
                logger.debug(f"{page_node_log_prefix} Successfully extracted data.")

            except FallbackExceptionGroup as feg:
                error_message = f"All fallback models failed for data extraction on page {page_url}."
                logger.error(f"{page_node_log_prefix} {error_message}")
                for i, exc in enumerate(feg.exceptions):
                     logger.error(f"  - Model {i+1}: {type(exc).__name__}: {exc}")
                page['extraction_error'] = error_message
                page.setdefault('webpage_type', 'other')
                page.setdefault('relevant', 'no')
                page.setdefault('publication_date', None)
                page.setdefault('facts', [])
                page.setdefault('quotes', [])
                page.setdefault('keywords', [])

            except Exception as error:
                logger.error(f"{page_node_log_prefix} Error extracting data: {error}", exc_info=True)
                page['extraction_error'] = str(error)
                page.setdefault('webpage_type', 'other')
                page.setdefault('relevant', 'no')
                page.setdefault('publication_date', None)
                page.setdefault('facts', [])
                page.setdefault('quotes', [])
                page.setdefault('keywords', [])

        for page in pages_to_process:
            tasks.append(process_page(page))
        await asyncio.gather(*tasks)

        successful_extractions = sum(1 for p in pages_to_process if 'extraction_error' not in p)
        failed_extractions = len(pages_to_process) - successful_extractions
        logger.info(f"Data extraction finished processing {len(pages_to_process)} pages. Successful: {successful_extractions}, Failed: {failed_extractions}.")

        # --- Filtering and Aggregation Logic ---
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

            ### FIX 1: Force-include manual URLs, bypassing other checks ###
            if is_manual_url:
                logger.info(f"{log_prefix} Force-including as it is a manually provided URL.")
                filter_reason = "Included (Manual URL)"
                page['filter_reason'] = filter_reason
                articles.append(page)
                continue # Skip all other checks for this manual URL

            # --- These checks now ONLY apply to non-manual URLs ---
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

            # If all checks passed for a non-manual URL
            logger.debug(f"{log_prefix} Included.")
            page['filter_reason'] = filter_reason
            articles.append(page)

        ### FIX 2: Check for ANY available facts before proceeding. ###
        llm_facts_available = ctx.state.researched_info.facts_from_llm or []
        if not articles and not llm_facts_available:
            error_message = "No relevant articles were found after filtering and no LLM facts are available. Cannot write an article without source material."
            logger.error(f"{node_name}: {error_message}")
            ctx.state.add_error(node_name, error_message)
            save_state(ctx.state)
            error_report = self._generate_error_report(ctx.state.errors)
            return End(f"ERROR: Process stopped. No content available to write an article.\n\nError Log:\n{error_report}")
        
        # This handles the case where there are no articles, but there ARE LLM facts.
        if not articles:
            logger.warning("No relevant articles found after filtering. Proceeding to InstructionsNode with only LLM facts.")
            llm_fact_strings = [f.fact_llm for f in llm_facts_available if f.fact_llm]
            ctx.state.researched_info = ResearchedInfo(
                 facts=llm_fact_strings,
                 facts_from_articles=[],
                 facts_from_llm=llm_facts_available,
                 quotes=[],
                 keywords=[],
                 article_texts=""
            )
            ctx.state.sources = list(manual_urls) # Keep only manual URLs if no articles used
            save_state(ctx.state)
            logger.info(f"Transitioning from {node_name} to InstructionsNode (no relevant articles found)")
            return InstructionsNode()


        # --- Aggregate Data from Filtered Articles ---
        # (This section remains largely the same, but now it operates on a correctly filtered list)
        existing_facts_from_llm = ctx.state.researched_info.facts_from_llm or []
        llm_fact_strings = [fact.fact_llm for fact in existing_facts_from_llm if fact.fact_llm]

        facts_from_articles = []
        combined_quotes_data = []
        combined_keywords = set()
        article_sources = set(manual_urls) # Start with manual URLs
        article_texts_snippets = []

        for article in articles:
            if facts := article.get('facts'):
                 if isinstance(facts, list): facts_from_articles.extend(facts)
            if quotes_data := article.get('quotes'):
                 if isinstance(quotes_data, list): combined_quotes_data.extend(quotes_data)
            if keywords := article.get('keywords'):
                 if isinstance(keywords, list): combined_keywords.update(keywords)
            if url := article.get('url'): article_sources.add(url) # Add URL of used article
            if snippet := article.get('formated_article_short'): article_texts_snippets.append(snippet)

        combined_quotes = []
        for q_data in combined_quotes_data:
             if isinstance(q_data, dict):
                 try: combined_quotes.append(Quote(**q_data))
                 except Exception as e: logger.warning(f"Could not create Quote object from data: {q_data}. Error: {e}")
             elif isinstance(q_data, Quote): combined_quotes.append(q_data)

        combined_facts = llm_fact_strings + facts_from_articles
        if not combined_facts:
            logger.warning("No facts found (LLM or Article) after filtering. Proceeding, but article quality may suffer.")

        ctx.state.researched_info.quotes = combined_quotes if combined_quotes else None
        ctx.state.researched_info.facts = combined_facts
        ctx.state.researched_info.facts_from_articles = facts_from_articles
        ctx.state.researched_info.keywords = list(combined_keywords)
        ctx.state.researched_info.article_texts = "\n\n==============================\n\n".join(article_texts_snippets)
        ctx.state.sources = sorted(list(article_sources))

        logger.info(f"Aggregated data: {len(combined_facts)} facts, {len(combined_quotes)} quotes, {len(ctx.state.sources)} sources.")
        save_state(ctx.state)
        logger.info(f"Transitioning from {node_name} to InstructionsNode")
        return InstructionsNode()





###############################################################################
############################## Instructions Node ##############################


instructions_agent_prompt = """
You are an **Editor-in-Chief**. Your task is to provide detailed, structured instructions for a journalist to write a **high-quality web article**.

### Key Requirements:
- Be **very specific** about:
  - **H1 Title**: The main title should be **highly clickbaity** to drive engagement but **must not be misleading**. The titles from the reference articles are a good benchmark.
  - **Structure**: Outline headings (H1, H2), article lead and how to break the content into sections. No table of contents is needed.
  - **Paragraphs & Flow**: Guide how information should be introduced, expanded, and concluded.
  - **Writing Style**: Define the tone, voice, and style (e.g., engaging, authoritative, casual, data-driven). Emphasize that general and meaningless words like 'summary', 'introduction', 'final remarks" etc. should be avoided (especially in headings) - writer should go straight to the point.
  - **SEO Best Practices**: Recommend keyword usage, readability strategies, and search engine optimization techniques.
  - **User Engagement**: Detail how to captivate readers, apply storytelling, and **use clickbait techniques effectively without misleading**.
  - **Driving Users Into the Story**: Suggest hooks, suspenseful openings, and compelling transitions.

### Constraints:
- The instructions should focus **only on text** (no images, polls, quizzes, embeds, meta descriptions, or link placements).
- The article should **align with the style and format** of similar articles from the provided references.

### Style and structure:
These are example, published articles from your web magazine covering different topics. The **style, tone, format, structure and length** of the new article should be similar:
{example_articles}


### Article Topic:
The article will be about:
{topic}

### Initial Plan:
The following plan was proposed for the article:
{plan}
- You **do not need to strictly follow the plan**, but use it as guidance.

### Reference Articles:
These are articles on the similar topic written by our competitors. Make sure your journalist will make a better job:
{article_texts}

### Output Format:
Write the instructions as a **prompt** for an AI writing agent, ensuring clarity, specificity, and completeness. **No additional comments are needed**—just the structured prompt itself.

Be **very detailed** and **ensure that the instructions are AI-friendly**, making it easy for a writing assistant to generate a compelling, well-optimized article.
Write it in the language of the Article Topic, no additional comments are needed.
"""

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
        instructions_agent = Agent( # Agent local to this execution
            model=instructions_node_fallback_model,
            result_type=str, # Expecting plain string instructions
            retries=1 # Optional agent retries before fallback
        )
        # --------------------------------------------------------------

        # --- Core Logic ---
        article_texts = ctx.state.researched_info.article_texts or "No reference articles available."
        research_plan = ctx.state.research_plan.plan if ctx.state.research_plan else "No initial plan provided."
        topic = ctx.state.configuration.article_topic

        if not topic:
            # This error will be caught by ResilientNode.run
            raise ValueError(f"{node_name}: Article topic is missing in configuration.")

        user_prompt = instructions_agent_prompt.format( # Ensure prompt is accessible
            article_texts=article_texts,
            plan=research_plan,
            topic=topic,
            example_articles=example_articles
        )
        # logger.debug(f"{node_name} prompt snippet: {user_prompt[:300]}...")

        # Run agent - uses fallback
        result = await instructions_agent.run(user_prompt=user_prompt)

        if result is None or not result.data: # Check for None or empty string
             raise ValueError(f"{node_name} agent run did not return valid data (instructions) after attempting models.")

        # --- Update State ---
        ctx.state.instructions = result.data
        logger.info("Successfully generated writing instructions.")

        # Save state
        save_state(ctx.state)

        # --- Return Next Node INSTANCE ---
        logger.info(f"Transitioning from {node_name} to WritingNode")
        return WritingNode() # Instantiate


###############################################################################
################################ Writing Node #################################

writing_agent_prompt = """You are an **editor for a web magazine**. Your task is to write a **high-quality web article** on the following topic:

### Article Topic:
{topic}

### Available Information:
Use the following **facts** (if relevant):
{facts}
Use these **quotes** where appropriate:
{quotes}
Incorporate these **important keywords** for SEO (where appropriate):
{keywords}

### Writing Guidelines:
- Follow these **detailed instructions** carefully:
{instructions}

Moreover:
- **Do not make up facts**—use only the provided information.
- **Infuse your writing with wit, charm, and humor**
- Use **simple HTML tags** for formatting:
  - `<h1>` for the main title
  - `<h2>` for subheadings
  - `<strong>` for emphasis
  - `<blockquote>` for quotes
- Do not use any other formatting (e.g. markdown) but html tags(e.g. <strong>Strong</strong>, not **Strong**)
- You always need `<h1>`, article lead, at least 2 `<h2>`
- Keep **paragraphs between 3-5 sentences** for readability.
- Keep in mind current date: {current_date}
- Return **only the article**—**no additional comments** or explanations are necessary.

These are example, published articles from your web magazine covering different topics. The **style, tone, format, structure and length** of the new article should be similar:
{example_articles}

"""

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
        writing_agent = Agent[None, str]( # Agent local to this execution
            model=writing_node_fallback_model,
            result_type=str, # Expecting the article as a string
            retries=1 # Optional agent retries before fallback
        )
        # --------------------------------------------------------------

        # --- Determine Prompt ---
        if ctx.state.reflection_round == 0:
            # Initial writing round
            facts_list = ctx.state.researched_info.facts or []
            facts_str = "\n - ".join(facts_list) if facts_list else "No facts available."
            keywords_list = ctx.state.researched_info.keywords or []
            keywords_str = ", ".join(keywords_list) if keywords_list else "N/A"
            quotes_list = ctx.state.researched_info.quotes or []
            quotes_str = "\n".join([f'"{escape(q.text or "")}" - {escape(q.speaker or "Unknown")} (Source: {escape(q.source or "N/A")})' for q in quotes_list]) \
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
        try:
            result = await writing_agent.run(
                user_prompt=user_prompt,
                # Pass message history only if it's not empty, otherwise default might be used
                message_history=ctx.state.messages if ctx.state.messages else None
            )
        except FallbackExceptionGroup as feg:
             # Re-raise to be caught by ResilientNode's run method
             logger.error(f"{node_name} failed: All fallback models exhausted during agent run.")
             raise feg
        except Exception as agent_error:
            # Catch other potential agent errors and re-raise for ResilientNode
            logger.error(f"{node_name} agent run failed: {agent_error}", exc_info=True)
            raise agent_error

        if result is None or not result.data: # Check for None or empty string result
            raise ValueError(f"{node_name} agent run did not return valid data (article) after attempting models.")

        # --- Update State ---
        # Update message history ALWAYS after a successful agent call
        ctx.state.messages = result.all_messages()

        # --- Determine Next Step ---
        if ctx.state.reflection_round > 0:
            # This was the revision round based on reflection
            ctx.state.finished_article = result.data # Store final article
            logger.info(f"Article revision complete (Round {ctx.state.reflection_round}). Proceeding to FollowUpNode.")
            save_state(ctx.state) # Save state including the finished article
            logger.info(f"Transitioning from {node_name} to FollowUpNode")
            return FollowUpNode() # Instantiate
        else:
            # This was the first writing round
            # Draft is in result.data (and messages). Don't set finished_article yet.
            logger.info("Initial article draft complete. Proceeding to ReflectionNode.")
            save_state(ctx.state) # Save state including the updated message history
            logger.info(f"Transitioning from {node_name} to ReflectionNode")
            return ReflectionNode() # Instantiate


###############################################################################
############################### Reflection Node ###############################


reflection_agent_prompt = """You are an **Editor-in-Chief**. Your task is to **review the article** written by the editor agent and provide **detailed, relevant, and actionable feedback**. Your output must consist solely of a structured AI prompt for a writing agent—do not include any additional commentary or explanations. The entire feedback must be written in the same language as the revised article.

###Your review must:
- **Identify issues and provide clear instructions on what to improve and how.**
- **Be based on your previous instructions**
- **Take high-quality benchmark articles into account** - use them to compare and score revised article against them as well as to co suggest enhancements
- **Avoid instructing the other agent to verify or double-check any details; it is your job so do it and solely provide actionable advice.**
- **Check the style** - it should be similar to style of the high-quality benchmark articles and not overly flowery and to the point.

### Actionable Instructions for the AI Writing Agent:
- **Do not include any commentary or meta discussion beyond this prompt.**
- **Address specific sentences, sections, or paragraphs and provide clear, step-by-step instructions on how to improve them.**
- **Clearly specify what to change and how to change it by targeting particular parts of the article.**
- **If certain elements are missing, instruct the agent on what should be added and why, using examples inspired by benchmark articles.**
- **Focus on providing precise, detailed instructions that are easy to implement.**
- **Remind not to include publication date in the final article**


### Article Rating
- **A the end always rate the article as 2/5. Demand 5/5**

### Style and structure:
These are example, published articles from your web magazine covering different topics. The **style, tone, format, structure and length** of the new article should be similar:
{example_articles}

### Reference Articles:
These are articles on the similar topic written by our competitors. Make sure your journalist will make a better job:
{benchmark_articles}
"""

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
        reflection_agent = Agent( # Agent local to this execution
            model=reflection_node_fallback_model,
            result_type=str, # Expecting feedback string
            retries=1 # Optional agent retries before fallback
        )
        # --------------------------------------------------------------

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


        if result is None or not result.data: # Check for None or empty feedback
            raise ValueError(f"{node_name} agent run did not return valid data (feedback) after attempting models.")

        # --- Process Result & Update State ---
        feedback = result.data
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

        # Save state
        save_state(ctx.state)

        # --- Return Next Node INSTANCE ---
        logger.info(f"Transitioning from {node_name} back to WritingNode")
        return WritingNode() # Instantiate for revision round

###############################################################################
############################## Follow up Node ##############################


followup_agent_prompt = """You are given a finished article (referred to as "finished_article"). Please analyze it thoroughly and perform the following steps:

1. Propose 10 clickbait-style alternative titles that capture attention. Each title should:
   - Highlight at least one unique or intriguing detail from the article.
   - Pose some form of puzzle, mystery, or question to entice readers.
   - Differ from each other in style, tone, or focus.
    
    You can find examples of good titles for various articles—use their style and structure for inspiration:
    #####
    Imię słowiańskiej bogini powoli się odradza. Ma ciekawe znaczenie i nosi je już 47 Polek
    W PRL-u wszyscy się nimi zajadali. Zrobisz je szybko i za grosze
    To warzywo jest kopalnią witamin. Jednak Polacy kręcą na nie nosem
    Najtańsza odżywka do storczyka. Wystarczy odrobina, by utonął w kwiatach
    Tu poczujesz się jak w alpejskim kurorcie. Raj nie tylko dla narciarzy, organizm będzie ci wdzięczny
    Nowe egzotyczne połączenie z polskiego lotniska. Turyści już szykują kapelusze i kremy z filtrem
    Wcale nie bombki. Tuż za granicą Polski na choince wieszają coś innego, aż zapierają dech w piersi
    Nigdy nie dodawaj tego składnika do sałatki greckiej. Grecy poczują się urażeni
    Nie Bułgaria i nie Turcja. Oto 3 pomysły na tanie wakacje samolotem
    Baśniowa kraina tuż przy polskiej granicy – to jedynie 3,5 godziny jazdy z Krakowa
    Było symbolem Malty. 8 lat temu runęło do morza
    Zakwitły już nad Bałtykiem. Są piękne, ale śmiertelnie niebezpieczne
    Jak nie robić zdjęć w podróży. Takie zachowanie to naruszenie zasad
    #####
    
2. Suggest 5 new article topics that relate—directly or loosely—to the content of the "finished_article." Each topic should:
   - Be interesting enough to link from or to the original article.
   - Offer a fresh perspective or expand on the ideas mentioned.


The article:
{finished_article}

"""
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
            save_state(ctx.state)
            error_report = self._generate_error_report(ctx.state.errors) # Use helper from ResilientNode
            return End(f"ERROR: Finished article missing.\n\nError Log:\n{error_report}")

        followup_agent = Agent( # Agent local to this execution
            model=followUp_node_fallback_model,
            result_type=FollowUp, # Ensure FollowUp model is defined/imported
            retries=1 # Optional agent retries before fallback
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
            if result is None or result.data is None:
                    logger.warning(f"{node_name} agent run succeeded but returned no data. Proceeding without suggestions.")
                    follow_up_data = FollowUp(alternative_titles=[], followup_articles=[])
                    ctx.state.add_error(node_name, "Follow-up agent returned no suggestions (result was None or empty).")
            else:
                    follow_up_data = result.data

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
        save_state(ctx.state)
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

    def _generate_quotes_html(self, quotes: Optional[List[Quote]]) -> str:
        """Generates HTML for the quotes section."""
        title = "Cytaty"
        if not quotes:
            content = "<ul><li>No quotes available.</li></ul>"
        else:
            list_items = "".join(
                f"<li>{escape(q.text or 'N/A')} - {escape(q.speaker or 'Unknown')} (Źródło: {escape(q.source or 'N/A')})</li>"
                for q in quotes
            )
            content = f"<ul>{list_items}</ul>"
        return f"<section><h2>{escape(title)}</h2>{content}</section>"

    def _generate_llm_facts_html(self, llm_facts: Optional[List[FactFromLlm]]) -> str:
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

    def _generate_error_report_html(self, errors: List[Dict[str, str]]) -> str:
        """Generates an HTML section reporting errors logged during the run."""
        if not errors: return ""
        title = "Execution Errors Report"
        list_items = "".join(
            f"<li><strong>{escape(err.get('node', 'Unknown Node'))}:</strong> {escape(err.get('error', 'Unknown Error'))}</li>"
            for err in errors
        )
        content = f"<ul>{list_items}</ul>"
        return f"<section class='error-report'><h2>{escape(title)}</h2>{content}</section>"

    def _generate_error_report(self, errors: List[Dict[str, str]]) -> str:
        """Generates a plain text error report."""
        # Ensure this helper is present if needed by the error check at the start
        if not errors: return "No errors reported."
        report = ""
        for err in errors:
             report += f"- Node: {escape(err.get('node', 'Unknown Node'))}, Error: {escape(err.get('error', 'Unknown Error'))}\n"
        return report

    def _generate_detailed_sources_html(self, title: str, all_pages: List[Dict]) -> str:
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
        domains: List[str],
        urls: List[str] = None,  # <-- new parameter
        number_of_queries: int = 2,
        scraping_model: str = "",
        max_search_results: int = 4,
        search_days: int = 500,
        provide_llm_facts: Literal["yes", "no"] = "no",
        extraction_mode: Literal["markdown", "html", "llm"] = "markdown",
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
        article_topic="Potwierdziły się doniesienia ws. syna Nawrockiej. Prawda wyszła na jaw",
        domains=[],  # example domains
        urls=['https://www.pomponik.pl/plotki/news-potwierdzily-sie-doniesienia-ws-syna-nawrockiej-prawda-wyszl,nId,7989757'],       # example URLs
        number_of_queries=2,
        scraping_model="",        # specify your scraping model if needed
        max_search_results=4,
        search_days=10,
        extraction_mode="markdown",
        provide_llm_facts="no"
    )
    print(article)

