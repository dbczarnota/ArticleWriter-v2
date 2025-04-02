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
from datetime import date, datetime, timedelta
import abc
from html import escape


logger = logging.getLogger(__name__)
load_dotenv()
current_date = current_date_today = date.today()

###############################################################################
# Error handling class template
###############################################################################
class ResilientNode(BaseNode, abc.ABC):
    """
    A base node class that handles common execution logic like
    timeouts, retries, and error logging.
    """
    # --- Node specific configuration (must be set in subclasses) ---
    # Example: retry_counter_attr = "searchnode_tries"
    retry_counter_attr: str = ""
    # Example: max_retries = 1
    max_retries: int = 1
    # Example: timeout_seconds = 600
    timeout_seconds: int = 600 # Default timeout

    @abc.abstractmethod
    async def _execute(self, ctx: GraphRunContext[State]) -> BaseNode | End:
        """
        The core logic specific to the node.
        Subclasses MUST implement this method.
        It should return the next node instance, an End state,
        a node Type (to instantiate), or None if handled internally.
        """
        pass

    async def run(self, ctx: GraphRunContext[State]) -> BaseNode | End:
        """
        Runs the node's core logic (_execute) with timeout, retry,
        and error handling.
        """
        if not self.retry_counter_attr:
            raise NotImplementedError(
                f"Node {self.__class__.__name__} must define 'retry_counter_attr'"
            )

        node_name = self.__class__.__name__
        # No need to load state here usually, ctx should be up-to-date

        try:
            logger.info(f"Running {node_name}...")
            # Wrap the specific logic execution with a timeout
            result = await asyncio.wait_for(
                self._execute(ctx), # Call the subclass's specific logic
                timeout=self.timeout_seconds
            )
            # Reset retry counter on success if desired (optional)
            # setattr(ctx.state, self.retry_counter_attr, 0)
            # save_state(ctx.state) # Save state after successful run? Optional.
            logger.info(f"{node_name} completed successfully.")
            return result # Return the next node or End

        except asyncio.TimeoutError:
            error_message = f"{node_name} timed out after {self.timeout_seconds} seconds"
            logger.error(error_message)
            # Fall through to the general exception handling for retry logic

        except Exception as e:
            error_message = f"Error in {node_name}: {str(e)}"
            logger.exception(f"Caught exception in {node_name}") # Logs traceback
            # Fall through to the general exception handling

        # --- Common Error/Retry Handling ---
        current_retries = getattr(ctx.state, self.retry_counter_attr, 0)
        ctx.state.add_error(node_name, error_message) # Log the error to state

        if current_retries < self.max_retries:
            # Increment retry counter
            setattr(ctx.state, self.retry_counter_attr, current_retries + 1)
            save_state(ctx.state) # Save state after incrementing counter and adding error
            logger.warning(f"Retrying {node_name} (Attempt {current_retries + 1}/{self.max_retries})...")
            # Reload state before retry might be safer if _execute could corrupt it
            # ctx.state = load_state() # Optional: reload state
            return self() # Return instance of the current node to retry
        else:
            final_error_msg = f"ERROR: {node_name} failed after {self.max_retries + 1} attempts. Last error: {error_message}"
            logger.error(final_error_msg)
            # Ensure state is saved with the final error logged
            save_state(ctx.state)
            return End(final_error_msg)



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
    current_date: date = current_date
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
# search_model = OpenAIModel('gpt-4o', api_key=os.getenv('OPENAI_API_KEY'))
search_model = OpenAIModel('gpt-4o', provider = OpenAIProvider(api_key=os.getenv('OPENAI_API_KEY')))

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

research_agent = Agent[None, ResearchPlan](
    model=search_model,
    result_type=ResearchPlan,
)

@dataclass
class SearchNode(ResilientNode):
    # --- Configure ResilientNode ---
    retry_counter_attr: str = "searchnode_tries"
    max_retries: int = 1 # Or configure as needed
    timeout_seconds: int = 600 # Specific timeout for this node

    async def _execute(self, ctx: GraphRunContext[State]) -> ScrapingNode | LlmKnowledgeNode | End:
        """
        Generates the research plan and queries based on the article topic.
        """
        # Core logic previously in _run_internal, without try/except/retry/timeout
        logger.info("Executing SearchNode logic...") # Use logger

        # No need to load_state here, ctx is passed by the runner

        prompt = research_agent_prompt.format(
            current_date=current_date, # Assuming current_date is accessible
            article_topic=ctx.state.configuration.article_topic,
            number_of_queries=ctx.state.configuration.number_of_queries
        )
        result = await research_agent.run(user_prompt=prompt) # research_agent needs to be accessible

        # Update state
        ctx.state.research_plan = result.data
        ctx.state.research_plan.queries.append(ctx.state.configuration.article_topic)

        # Save state *only if crucial* before moving to the next node.
        # The base class saves on error/retry. Saving here ensures the research_plan
        # is persisted even if the *next* node fails immediately. Good practice.
        save_state(ctx.state)

        logger.info(f'Search queries generated: {ctx.state.research_plan.queries}')

        # Return the TYPE of the next node
        if ctx.state.configuration.provide_llm_facts == "yes":
            return LlmKnowledgeNode() 
        else:
            return ScrapingNode() 

###############################################################################
################################ LlmKnowledge Node ################################
# llmknowledge_model = OpenAIModel('gpt-4o', api_key=os.getenv('OPENAI_API_KEY'))
llmknowledge_model = OpenAIModel('gpt-4o', provider = OpenAIProvider(api_key=os.getenv('OPENAI_API_KEY')))

llmknowledge_agent_prompt = """
You are a meticulous research assistant providing verified and sourced facts to support an article.

### Article Information:
- General Topic: {article_topic}

- Research Queries: {search_queries}

### Guidelines:
- Provide ONLY verified facts.
- Ensure all information is CURRENT (consider today's date: {current_date}).
- NEVER guess or create facts if uncertain. If solid information is unavailable, explicitly state "No verified information found."
- Provide a credible and direct source for every fact you provide (domain or citation).


Your accuracy and clarity are essential. Prioritize factual correctness over quantity, but give everything that is relevant and can be used to write the article.
"""
llmknowledge_agent = Agent(
    model=llmknowledge_model,
    result_type=List[FactFromLlm]
)

@dataclass
class LlmKnowledgeNode(ResilientNode):
    # --- Configure ResilientNode ---
    retry_counter_attr: str = "llmknowledgenode_tries"
    max_retries: int = 1
    timeout_seconds: int = 600

    # --- Corrected signature ---
    async def _execute(self, ctx: GraphRunContext[State]) -> ScrapingNode | End:
        """
        Retrieves and stores facts directly from the LLM based on the research plan.
        """
        logger.info("Executing LlmKnowledgeNode logic...")

        # Don't usually need load_state() here, ctx is current.
        # ctx.state = load_state() # Remove unless specifically needed before execution

        prompt = llmknowledge_agent_prompt.format(
            article_topic=ctx.state.configuration.article_topic,
            initial_plan=ctx.state.research_plan.plan, # Assuming plan is populated
            search_queries=ctx.state.research_plan.queries,
            current_date=current_date # Assuming current_date is accessible
        )
        logger.debug(f'LlmKnowledgeNode prompt: {prompt}') # Use debug/info as appropriate

        # Ensure llmknowledge_agent is accessible
        result = await llmknowledge_agent.run(user_prompt=prompt)
        logger.debug(f'LlmKnowledgeNode result.data: {result.data}')

        # Update state
        ctx.state.researched_info.facts_from_llm = result.data
        logger.info(f'LLM facts retrieved: {len(ctx.state.researched_info.facts_from_llm)} items.')

        # Save state on success before moving on
        save_state(ctx.state)

        # Return INSTANCE of the next node
        return ScrapingNode()
            
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
        # Convert set to list for scraping function
        urls_to_scrape = list(unique_urls)

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
# parsing_model = OpenAIModel('o3-mini', api_key=os.getenv('OPENAI_API_KEY'))
parsing_model = OpenAIModel('o3-mini', provider = OpenAIProvider(api_key=os.getenv('OPENAI_API_KEY')))

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
- **Publication date** (if present).  
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

parsing_agent = Agent(
    model=parsing_model,
    result_type=ParsedArticle,
    retries=2
)

@dataclass
class ParsingNode(ResilientNode):
    # --- Configure ResilientNode ---
    retry_counter_attr: str = "parsingnode_tries"
    max_retries: int = 1
    # Parsing can be CPU/LLM intensive, adjust timeout if needed
    timeout_seconds: int = 720 # Example: 12 minutes

    # --- Corrected signature ---
    async def _execute(self, ctx: GraphRunContext[State]) -> DataExtractionNode | End:
        """
        Parses the raw HTML of scraped pages to extract article text,
        handling token limits and individual page errors.
        """
        logger.info("Executing ParsingNode logic...")
        # ctx.state = load_state() # Generally not needed here

        enc = tiktoken.get_encoding("cl100k_base")
        MAX_TOKENS = 100_000 # Consider making this configurable

        # Work on a copy or be careful if modifying ctx.state.scraped_pages directly
        # Let's update pages in place, assuming process_page modifies the dict
        pages_to_process = ctx.state.scraped_pages
        if not pages_to_process:
            logger.warning("No scraped pages found to parse. Proceeding.")
            # save_state(ctx.state) # Optional save if state could have changed
            return DataExtractionNode()

        tasks = []
        processed_pages = [] # Collect successfully processed pages if needed separately
                             # Or just rely on modifications within the original list items

        async def process_page(page: dict):
            """Inner function to process a single page."""
            page_url = page.get('url', 'unknown URL')
            try:
                article_body = page.get("article_body", "")
                if not article_body:
                    logger.warning(f"No article_body found for {page_url}. Skipping parsing.")
                    page['webpage_type'] = 'other' # Mark as other if no body
                    page['parsed_article'] = None
                    return # Don't proceed further for this page

                tokens = enc.encode(article_body)
                token_count = len(tokens)

                if token_count > MAX_TOKENS:
                    logger.warning(
                        f"Article from {page_url} has {token_count} tokens, exceeding {MAX_TOKENS}. Truncating."
                    )
                    tokens = tokens[:MAX_TOKENS]
                    article_body = enc.decode(tokens)
                    page["article_body_truncated"] = True # Mark if truncated

                prompt = parsing_agent_prompt.format(html=article_body)
                # Ensure parsing_agent is accessible
                result = await parsing_agent.run(user_prompt=prompt)

                # Update the page dictionary directly
                page['webpage_type'] = result.data.webpage_type
                page['parsed_article'] = result.data.parsed_article
                logger.debug(f"Successfully parsed {page_url} as {result.data.webpage_type}")

            except Exception as error:
                # Log error specific to this page, but don't fail the whole node
                logger.error(f"Error processing page {page_url}: {error}", exc_info=True)
                # Mark page as failed or set default values
                page['webpage_type'] = 'other' # Or a specific error type?
                page['parsed_article'] = None
                page['parsing_error'] = str(error)
                # We are modifying the page dict in place, so no need to remove from list

        # Create tasks for processing pages
        for page in pages_to_process:
            tasks.append(process_page(page)) # Pass the dictionary

        # Run all parsing tasks concurrently
        await asyncio.gather(*tasks)

        logger.info(f"Parsing finished for {len(pages_to_process)} pages.")

        # State is modified in-place within the page dictionaries inside ctx.state.scraped_pages
        # Save the updated state
        save_state(ctx.state)

        # Proceed to the next node
        return DataExtractionNode()


###############################################################################
############################# DataExtraction Node #############################
# data_extraction_model = OpenAIModel('o3-mini', api_key=os.getenv('OPENAI_API_KEY'))
data_extraction_model = OpenAIModel('o3-mini', provider = OpenAIProvider(api_key=os.getenv('OPENAI_API_KEY')))

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
    publication_date: date
    facts: Optional[List[str]]
    quotes: Optional[List[Quote]]
    keywords: Optional[List[str]]

@dataclass # Keep if you have specific fields later, otherwise optional
class DataExtractionNode(ResilientNode):
    # --- Configure ResilientNode ---
    retry_counter_attr: str = "dataextractionnode_tries"
    max_retries: int = 1
    # Data extraction might involve many LLM calls, adjust timeout
    timeout_seconds: int = 900 # Example: 15 minutes

    # --- Corrected signature ---
    async def _execute(self, ctx: GraphRunContext[State]) -> InstructionsNode | End:
        """
        Extracts structured information (facts, quotes, keywords) from parsed articles,
        filters relevant and recent articles, and aggregates the data. Logs filtering decisions.
        """
        logger.info("Executing DataExtractionNode logic...")

        # Initialize the agent within the execution if not already done globally/passed
        # This ensures it uses the latest model/config if state changes matter
        data_extraction_agent = Agent(
            model=data_extraction_model, # Ensure data_extraction_model is accessible
            result_type=ResearchedArticle,
            retries=2 # Agent-level retries
        )

        # Filter pages that have actual parsed content to process
        pages_to_process = [
            page for page in ctx.state.scraped_pages
            if page and page.get('parsed_article') # Ensure page exists and has content
        ]

        if not pages_to_process:
            logger.warning("No pages with parsed content found to extract data from. Proceeding.")
            return InstructionsNode()

        tasks = []

        async def process_page(page: dict):
            """Inner function to extract data from a single parsed page."""
            page_url = page.get('url', 'unknown URL')
            try:
                parsed_article = page.get("parsed_article", "") # Already checked if exists

                # Improved title extraction (handles multiline titles better)
                title_match = re.search(r"<h1.*?>(.*?)</h1>", parsed_article, re.IGNORECASE | re.DOTALL)
                title = title_match.group(1).strip() if title_match else page.get('title', "Title not found")

                # Clean article text (remove H1 tag and its content)
                article_text_no_h1 = re.sub(r"<h1.*?>.*?</h1>", "", parsed_article, flags=re.IGNORECASE | re.DOTALL).strip()

                # Prepare formatted snippets for potential use/debugging
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

                # Create prompt for data extraction agent
                prompt = data_extraction_agent_prompt.format(
                    text=page['formated_article'], # Provide full context
                    topic=ctx.state.configuration.article_topic
                )
                logger.debug(f"Data extraction prompt for {page_url}: {prompt[:300]}...") # Log snippet

                # Run the agent
                researched_article_result = await data_extraction_agent.run(user_prompt=prompt)
                logger.debug(f"Data extraction result for {page_url}: {researched_article_result.data}")

                # Update the page dictionary in-place with extracted data
                if researched_article_result and researched_article_result.data:
                    data = researched_article_result.data
                    page['webpage_type'] = data.webpage_type
                    page['relevant'] = data.relevant
                    page['facts'] = data.facts
                    # Ensure quotes are stored as dicts if the agent returns Pydantic models
                    page['quotes'] = [q.model_dump() for q in data.quotes] if data.quotes else []
                    page['keywords'] = data.keywords
                    page['publication_date'] = data.publication_date
                else:
                     raise ValueError("Data extraction agent returned empty result.")


            except Exception as error:
                logger.error(f"Error extracting data from page {page_url}: {error}", exc_info=True)
                # Mark page with error, ensure default fields exist for filtering
                page['extraction_error'] = str(error)
                page.setdefault('webpage_type', 'other')
                page.setdefault('relevant', 'no')
                page.setdefault('publication_date', None)
                page.setdefault('facts', [])
                page.setdefault('quotes', [])
                page.setdefault('keywords', [])


        # Create and run tasks for all pages needing processing
        for page in pages_to_process:
            tasks.append(process_page(page))
        await asyncio.gather(*tasks)
        logger.info(f"Data extraction finished processing {len(pages_to_process)} pages.")


        # --- Filtering and Aggregation Logic ---
        logger.info("Filtering and aggregating extracted data...")
        x_days = ctx.state.configuration.search_days
        cutoff_date = datetime.now().date() - timedelta(days=x_days)
        logger.info(f'Filtering articles published on or after: {cutoff_date} (or manually specified URLs)')

        def parse_pub_date(pub_date):
            """Safely parse publication date from string or date object."""
            if isinstance(pub_date, date):
                return pub_date
            if isinstance(pub_date, str):
                for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d"): # Add more formats if needed
                    try:
                        return datetime.strptime(pub_date, fmt).date()
                    except ValueError:
                        pass # Try next format
            logger.debug(f"Could not parse date: {pub_date}")
            return None # Return None if not date, string, or unparseable string

        # Filtering loop with detailed logging
        articles = []
        logger.info(f"Starting filter process on {len(ctx.state.scraped_pages)} total pages.")
        manual_urls = set(ctx.state.configuration.urls or []) # Ensure it's a set

        for page in ctx.state.scraped_pages:
            page_url = page.get('url', 'unknown URL')
            log_prefix = f"Filtering '{page_url}':"
            filter_reason = "Included" # Default assumption

            if page is None:
                logger.debug(f"{log_prefix} Skipping None page object.")
                continue # Should ideally not happen if input is clean

            if err_msg := page.get('extraction_error'):
                logger.info(f"{log_prefix} Excluded - Extraction error: {err_msg}")
                filter_reason = f"Extraction error: {err_msg}"
                page['filter_reason'] = filter_reason # Store reason
                continue

            page_type = page.get('webpage_type')
            if page_type != "article":
                logger.info(f"{log_prefix} Excluded - Not classified as 'article' (Type: {page_type}).")
                filter_reason = f"Not classified as 'article' (Type: {page_type})"
                page['filter_reason'] = filter_reason # Store reason
                continue

            relevance = page.get('relevant')
            if relevance != "yes":
                logger.info(f"{log_prefix} Excluded - Not marked as 'relevant' (Relevance: {relevance}).")
                filter_reason = f"Not marked as 'relevant' (Relevance: {relevance})"
                page['filter_reason'] = filter_reason # Store reason
                continue

            # Date Check Logic
            is_manual_url = page_url in manual_urls
            publication_date_obj = parse_pub_date(page.get('publication_date'))
            pub_date_str = page.get('publication_date', 'N/A')

            if not is_manual_url:
                if publication_date_obj is None:
                    logger.info(f"{log_prefix} Excluded - Could not parse publication date ('{pub_date_str}') and not a manual URL.")
                    filter_reason = f"Could not parse publication date ('{pub_date_str}')"
                    page['filter_reason'] = filter_reason # Store reason
                    continue
                if publication_date_obj < cutoff_date:
                    logger.info(f"{log_prefix} Excluded - Publication date {publication_date_obj} is older than cutoff {cutoff_date} and not a manual URL.")
                    filter_reason = f"Publication date {publication_date_obj} older than cutoff {cutoff_date}"
                    page['filter_reason'] = filter_reason # Store reason
                    continue

            # If all checks passed
            logger.debug(f"{log_prefix} Included.")
            page['filter_reason'] = filter_reason # Explicitly mark as included
            articles.append(page) # Add to the list of articles to aggregate from


        logger.info(f"Found {len(articles)} relevant articles after filtering.")

        # Handle case where no articles meet criteria
        if not articles:
            logger.warning("No relevant articles found after filtering. Proceeding to InstructionsNode with only LLM facts (if any).")
            # Keep LLM facts, clear others. Keep original manual URLs in sources.
            llm_facts_preserved = ctx.state.researched_info.facts_from_llm or []
            llm_fact_strings = [f.fact_llm for f in llm_facts_preserved if f.fact_llm]
            ctx.state.researched_info = ResearchedInfo(
                 facts=llm_fact_strings, # Combined facts = only LLM facts
                 facts_from_articles=[],
                 facts_from_llm=llm_facts_preserved, # Preserve original LLM fact objects
                 quotes=[],
                 keywords=[],
                 article_texts=""
            )
            # Preserve only the original manual URLs in the sources list
            ctx.state.sources = list(manual_urls)
            save_state(ctx.state)
            return InstructionsNode()


        # --- Aggregate Data from Filtered Articles ---
        existing_facts_from_llm = ctx.state.researched_info.facts_from_llm or []
        llm_fact_strings = [fact.fact_llm for fact in existing_facts_from_llm if fact.fact_llm]

        facts_from_articles = []
        combined_quotes_data = [] # Store raw quote data first
        combined_keywords = set()
        article_sources = set(manual_urls) # Start with manual URLs
        article_texts_snippets = []

        for article in articles:
            # Extend lists, ensuring data exists and has the correct type
            if facts := article.get('facts'):
                 if isinstance(facts, list): facts_from_articles.extend(facts)
            if quotes_data := article.get('quotes'):
                 if isinstance(quotes_data, list): combined_quotes_data.extend(quotes_data)
            if keywords := article.get('keywords'):
                 if isinstance(keywords, list): combined_keywords.update(keywords)
            if url := article.get('url'): article_sources.add(url)
            if snippet := article.get('formated_article_short'): article_texts_snippets.append(snippet)

        # Convert quote data to Quote objects safely
        combined_quotes = []
        for q_data in combined_quotes_data:
             if isinstance(q_data, dict):
                 try:
                     combined_quotes.append(Quote(**q_data))
                 except Exception as e:
                     logger.warning(f"Could not create Quote object from data: {q_data}. Error: {e}")
             elif isinstance(q_data, Quote): # If already Quote objects
                 combined_quotes.append(q_data)


        combined_facts = llm_fact_strings + facts_from_articles
        if not combined_facts:
            logger.warning("No facts found (LLM or Article) after filtering. Proceeding, but article quality may suffer.")
            # Even if no facts, proceed. Writer node might handle this.

        # Update state with combined info
        ctx.state.researched_info.quotes = combined_quotes if combined_quotes else None
        ctx.state.researched_info.facts = combined_facts # Combined list
        ctx.state.researched_info.facts_from_articles = facts_from_articles # Explicitly track article facts
        # ctx.state.researched_info.facts_from_llm remains unchanged from start of node
        ctx.state.researched_info.keywords = list(combined_keywords)
        ctx.state.researched_info.article_texts = "\n\n==============================\n\n".join(article_texts_snippets) # Add separator
        ctx.state.sources = list(article_sources) # Final list of sources

        logger.info(f"Aggregated data: {len(combined_facts)} facts, {len(combined_quotes)} quotes, {len(ctx.state.sources)} sources.")

        # Save the final aggregated state
        save_state(ctx.state)

        # Proceed to the next node
        return InstructionsNode()


###############################################################################
############################## Instructions Node ##############################
# instructions_model = OpenAIModel('o3-mini', api_key=os.getenv('OPENAI_API_KEY'))
instructions_model = OpenAIModel('o3-mini', provider = OpenAIProvider(api_key=os.getenv('OPENAI_API_KEY')))

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

### Reference Articles:
Analyze these existing articles carefully. The new article should be **similar in tone, structure, and format**:
{article_texts}

### Article Topic:
The article will be about:
{topic}

### Initial Plan:
The following plan was proposed for the article:
{plan}
- You **do not need to strictly follow the plan**, but use it as guidance.

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
    timeout_seconds: int = 600 # Adjust if needed

    # --- Corrected signature ---
    async def _execute(self, ctx: GraphRunContext[State]) -> WritingNode | End:
        """
        Generates detailed writing instructions for the journalist agent
        based on the research plan, topic, and reference article snippets.
        """
        logger.info("Executing InstructionsNode logic...")
        # ctx.state = load_state() # Generally not needed

        # Prepare the prompt, handle potentially empty fields gracefully
        article_texts = ctx.state.researched_info.article_texts or "No reference articles available."
        research_plan = ctx.state.research_plan.plan or "No initial plan provided."
        topic = ctx.state.configuration.article_topic

        # Check if essential info is missing (optional, could rely on prompt/LLM)
        if not topic:
            logger.error("Article topic is missing in configuration. Cannot generate instructions.")
            # Option 1: End the graph
            return End("ERROR: Article topic is required for InstructionsNode.")
            # Option 2: Try to proceed (LLM might handle it, but quality loss likely)
            # logger.warning("Article topic missing, instructions quality might be low.")

        user_prompt = instructions_agent_prompt.format(
            article_texts=article_texts,
            plan=research_plan,
            topic=topic
        )
        logger.debug(f"InstructionsNode prompt: {user_prompt[:300]}...")

        # Ensure instructions_agent is initialized/accessible
        # If agent needs specific config, initialize here
        instructions_agent = Agent(
            model=instructions_model, # Ensure instructions_model is accessible
            result_type=str,
            retries=2 # Agent-level retries
        )

        # Run the agent
        result = await instructions_agent.run(user_prompt=user_prompt)

        if not result or not result.data:
             # Handle case where agent returns no instructions
             logger.error("Instructions agent returned no data.")
             return End("ERROR: Failed to generate writing instructions.")

        # Update state
        ctx.state.instructions = result.data
        logger.info("Successfully generated writing instructions.")

        # Save state on success
        save_state(ctx.state)

        # Proceed to the next node
        return WritingNode()


###############################################################################
################################ Writing Node #################################
# writing_model = OpenAIModel(
#     model_name='deepseek/deepseek-r1',
#     base_url='https://openrouter.ai/api/v1',
#     api_key=os.getenv('OPENROUTER_API_KEY'),
# )
provider = OpenAIProvider(
    base_url='https://openrouter.ai/api/v1',
    api_key=os.getenv('OPENROUTER_API_KEY'),)

writing_model = OpenAIModel('deepseek/deepseek-r1', provider = provider)

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
- Use **simple HTML tags** for formatting:
  - `<h1>` for the main title
  - `<h2>` for subheadings
  - `<strong>` for emphasis
  - `<blockquote>` for quotes
- You always need `<h1>`, article lead, at least 2 `<h2>`
- Keep **paragraphs between 3-5 sentences** for readability.
- Keep in mind current date: {current_date}
- Return **only the article**—**no additional comments** or explanations are necessary.
"""

@dataclass
class WritingNode(ResilientNode):
    # --- Configure ResilientNode ---
    retry_counter_attr: str = "writingnode_tries"
    max_retries: int = 1 # Retries for a single *invocation* of writing
    # Writing can take time, especially with large models/complex instructions
    timeout_seconds: int = 900 # Example: 15 minutes

    # --- Corrected signature (matches original logic) ---
    async def _execute(self, ctx: GraphRunContext[State]) -> ReflectionNode | FollowUpNode | End:
        """
        Writes or revises the article based on instructions or reflection feedback.
        Manages the reflection loop state.
        """
        logger.info(f"Executing WritingNode logic (Round: {ctx.state.reflection_round})...")
        # ctx.state = load_state() # Generally not needed

        # Ensure writing_agent is initialized/accessible
        # Use the specific writing model configuration
        writing_agent = Agent[None, str](
            model=writing_model, # Ensure writing_model is accessible
            result_type=str,
            retries=2 # Agent-level retries
        )

        # Determine the correct prompt based on the reflection round
        if ctx.state.reflection_round == 0:
            # Initial writing round
            # Prepare prompt, handling potentially missing data
            facts_str = "\n - ".join(ctx.state.researched_info.facts or ["No facts available."])
            keywords_str = ", ".join(ctx.state.researched_info.keywords or ["N/A"])
            quotes_list = ctx.state.researched_info.quotes or []
            quotes_str = "\n".join([f'"{q.text}" - {q.speaker} (Source: {q.source or "N/A"})' for q in quotes_list]) \
                         if quotes_list else "No quotes available."

            if not ctx.state.instructions:
                logger.error("Writing instructions are missing. Cannot proceed with writing.")
                return End("ERROR: Writing instructions are required for WritingNode.")

            user_prompt = writing_agent_prompt.format(
                topic=ctx.state.configuration.article_topic,
                facts=facts_str,
                keywords=keywords_str,
                quotes=quotes_str,
                instructions=ctx.state.instructions,
                current_date=ctx.state.current_date # Ensure current_date accessible
            )
            logger.info("Using initial writing prompt.")
        else:
            # Reflection round
            if not ctx.state.reflection_prompt:
                 logger.error(f"Reflection prompt is missing for round {ctx.state.reflection_round}. Cannot revise.")
                 return End(f"ERROR: Reflection prompt missing for round {ctx.state.reflection_round}.")

            user_prompt = ctx.state.reflection_prompt
            logger.info(f"Using reflection prompt for round {ctx.state.reflection_round}.")

        logger.debug(f"Writer prompt (Round {ctx.state.reflection_round}): {user_prompt[:300]}...")

        # Run the agent, passing the current message history
        try:
            result = await writing_agent.run(
                user_prompt=user_prompt,
                message_history=ctx.state.messages # Pass existing history
            )
        except Exception as agent_error:
            # If the agent call *itself* fails critically after its internal retries
            logger.exception(f"Writing agent failed during round {ctx.state.reflection_round}.")
            # Allow ResilientNode's retry logic to handle this attempt
            raise agent_error # Re-raise the exception for ResilientNode to catch

        if not result or not result.data:
            logger.error(f"Writing agent returned no data in round {ctx.state.reflection_round}.")
            # Allow ResilientNode's retry logic to handle this attempt
            # We might want to raise an error here to trigger the retry,
            # otherwise the graph might proceed incorrectly.
            raise ValueError(f"Writing agent returned empty result in round {ctx.state.reflection_round}.")


        # Update message history ALWAYS after a successful agent call
        ctx.state.messages = result.all_messages()

        # Determine next step based on reflection round
        if ctx.state.reflection_round > 0:
            # This was the revision round based on reflection
            ctx.state.finished_article = result.data
            logger.info(f"Article revision complete (Round {ctx.state.reflection_round}). Proceeding to FollowUpNode.")
            # Save state including the finished article and final message history
            save_state(ctx.state)
            return FollowUpNode()
        else:
            # This was the first writing round
            # Article is in result.data, but not yet final. Stored in messages.
            logger.info("Initial article draft complete. Proceeding to ReflectionNode.")
            # Save state including the updated message history (contains the draft)
            save_state(ctx.state)
            return ReflectionNode()


###############################################################################
############################### Reflection Node ###############################
# reflection_model = OpenAIModel('o3-mini', api_key=os.getenv('OPENAI_API_KEY'))
reflection_model = OpenAIModel('o3-mini', provider = OpenAIProvider(api_key=os.getenv('OPENAI_API_KEY')))

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

### High-quality Benchmark Articles:
{benchmark_articles}
"""

@dataclass
class ReflectionNode(ResilientNode):
    # --- Configure ResilientNode ---
    retry_counter_attr: str = "reflectionnode_tries"
    max_retries: int = 1
    timeout_seconds: int = 600 # Adjust if needed

    # --- Corrected signature ---
    async def _execute(self, ctx: GraphRunContext[State]) -> WritingNode | End:
        """
        Analyzes the draft article (from message history) against instructions
        and benchmarks, generating feedback (reflection prompt) for the next writing round.
        """
        logger.info("Executing ReflectionNode logic...")
        # ctx.state = load_state() # Generally not needed

        # Ensure reflection_agent is initialized/accessible
        reflection_agent = Agent(
            model=reflection_model, # Ensure reflection_model is accessible
            result_type=str,
            # Add retries if the agent supports it and it's desired
            # retries=1
        )

        # Prepare the prompt using benchmark articles
        benchmark_articles = ctx.state.researched_info.article_texts or "No benchmark articles available."
        user_prompt = reflection_agent_prompt.format(
            benchmark_articles=benchmark_articles
        )
        logger.debug(f"ReflectionNode prompt: {user_prompt[:300]}...")

        # Crucially, run the agent with the message history which contains the draft
        if not ctx.state.messages:
             logger.error("Message history is empty. Cannot perform reflection.")
             # This indicates a likely logic error earlier in the graph.
             return End("ERROR: Cannot run ReflectionNode with empty message history.")

        try:
            result = await reflection_agent.run(
                user_prompt=user_prompt,
                message_history=ctx.state.messages # Pass history including the draft
            )
        except Exception as agent_error:
            logger.exception("Reflection agent failed.")
            # Allow ResilientNode's retry logic to handle this attempt
            raise agent_error # Re-raise

        if not result or not result.data:
            logger.error("Reflection agent returned no data.")
            # Trigger retry by raising an error
            raise ValueError("Reflection agent returned empty result.")

        # Construct the feedback prompt for the next WritingNode execution
        feedback = result.data
        # Add benchmark articles to the feedback prompt for the writer's reference
        full_reflection_prompt = (
            f'Follow these instructions to improve your article:\n{feedback}\n\n'
            f'--- Benchmark Articles for Reference ---\n'
            f'{benchmark_articles}'
        )

        # Update state
        ctx.state.reflection_prompt = full_reflection_prompt
        ctx.state.reflection_round += 1 # Increment the round counter
        # Note: We don't update ctx.state.messages here, as reflection doesn't add to the core conversation history.
        # If you *wanted* the reflection feedback included in history, you'd append ModelMessages here.

        logger.info(f"Reflection complete. Generated feedback prompt for round {ctx.state.reflection_round}.")

        # Save state with the new reflection_prompt and incremented round
        save_state(ctx.state)

        # Proceed back to WritingNode for revision
        return WritingNode()

###############################################################################
############################## Follow up Node ##############################
# followup_model = OpenAIModel('o3-mini', api_key=os.getenv('OPENAI_API_KEY'))
followup_model = OpenAIModel('o3-mini', provider = OpenAIProvider(api_key=os.getenv('OPENAI_API_KEY')))

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
    timeout_seconds: int = 600 # Adjust if needed

    # --- Corrected signature ---
    async def _execute(self, ctx: GraphRunContext[State]) -> End:
        """
        Generates alternative titles and follow-up article ideas based on the
        finished article. Formats the final output including metadata and errors.
        """
        logger.info("Executing FollowUpNode logic...")
        # ctx.state = load_state() # Generally not needed

        if not ctx.state.finished_article:
            logger.error("Finished article is missing in state. Cannot generate follow-up content.")
            # Add error to state before ending
            ctx.state.add_error("FollowUpNode", "Finished article missing in state.")
            save_state(ctx.state)
            # Return End with an error message including collected errors
            error_report = self._generate_error_report(ctx.state.errors)
            return End(f"ERROR: Finished article missing.\n{error_report}")

        # Ensure followup_agent is initialized/accessible
        followup_agent = Agent(
            model=followup_model, # Ensure followup_model is accessible
            result_type=FollowUp, # Ensure FollowUp model is defined
            # Add retries if needed
        )

        user_prompt = followup_agent_prompt.format(
            finished_article=ctx.state.finished_article
        )
        logger.debug(f"FollowUpNode prompt: {user_prompt[:300]}...")

        try:
            result = await followup_agent.run(user_prompt=user_prompt)
            follow_up_data = result.data if result else None
        except Exception as agent_error:
            logger.exception("Follow-up agent failed.")
            # Allow ResilientNode's retry logic to handle this attempt
            raise agent_error # Re-raise

        if not follow_up_data:
            logger.warning("Follow-up agent returned no data. Proceeding without suggestions.")
            # Initialize with empty lists if agent failed or returned nothing
            follow_up_data = FollowUp(alternative_titles=[], followup_articles=[])
            # Optionally add this as a non-fatal error to the report
            ctx.state.add_error("FollowUpNode", "Follow-up agent returned no suggestions.")


        # --- Construct the final HTML Output ---
        logger.info("Constructing final HTML output...")

        article_html = f"<article>\n{ctx.state.finished_article}\n</article>"
        titles_html = self._generate_list_html("Alternatywne tytuły", follow_up_data.alternative_titles)
        topics_html = self._generate_list_html("Tematy do rozważenia", follow_up_data.followup_articles)
        # --- NEW sources HTML call ---
        sources_html = self._generate_detailed_sources_html(
            "Źródła i Status Przetwarzania",
            ctx.state.scraped_pages # Pass all scraped pages
        )
        quotes_html = self._generate_quotes_html(ctx.state.researched_info.quotes)
        article_facts_html = self._generate_list_html("Fakty z artykułów źródłowych", ctx.state.researched_info.facts_from_articles)
        llm_facts_html = self._generate_llm_facts_html(ctx.state.researched_info.facts_from_llm)
        error_report_html = self._generate_error_report_html(ctx.state.errors)

        full_result = f"""<!DOCTYPE html>
<html>
<head>
<title>Article Result</title>
<meta charset="UTF-8">
<style>
  /* ... (styles remain the same) ... */
  .source-item {{ margin-bottom: 8px; }}
  .source-url {{ font-weight: bold; }}
  .source-status {{ font-style: italic; margin-left: 10px; }}
  .status-included {{ color: green; }}
  .status-excluded {{ color: orange; }}
  .status-error {{ color: red; }} /* For extraction errors */
</style>
</head>
<body>
{article_html}
{error_report_html}
{titles_html}
{topics_html}
{sources_html} /* <-- Updated sources section */
{quotes_html}
{article_facts_html}
{llm_facts_html}
</body>
</html>
"""
        save_state(ctx.state)
        logger.info("FollowUpNode complete. Returning final output.")
        return End(full_result)

    # --- Helper methods for HTML generation ---

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
        if not errors:
            return "" # Return empty string if no errors

        title = "Execution Errors Report"
        list_items = "".join(
            f"<li><strong>{escape(err.get('node', 'Unknown Node'))}:</strong> {escape(err.get('error', 'Unknown Error'))}</li>"
            for err in errors
        )
        content = f"<ul>{list_items}</ul>"
        # Add specific class for styling
        return f"<section class='error-report'><h2>{escape(title)}</h2>{content}</section>"

    def _generate_error_report(self, errors: List[Dict[str, str]]) -> str:
        """Generates a plain text error report."""
        if not errors:
            return "No errors reported."
        report = "--- Execution Errors ---\n"
        for err in errors:
             report += f"- Node: {err.get('node', 'Unknown Node')}, Error: {err.get('error', 'Unknown Error')}\n"
        return report

    def _generate_detailed_sources_html(self, title: str, all_pages: List[Dict]) -> str:
        """Generates HTML for sources, showing status and filter reason."""
        if not all_pages:
            content = "<ul><li>No sources were processed.</li></ul>"
        else:
            list_items = ""
            for page in sorted(all_pages, key=lambda p: p.get('url', '')): # Sort by URL
                url = page.get('url', 'N/A')
                reason = page.get('filter_reason', 'Status unknown') # Get reason stored by DataExtractionNode
                status_class = "status-excluded" # Default style
                status_text = f"Excluded ({escape(reason)})"

                if reason == "Included":
                    status_class = "status-included"
                    status_text = "Included in final article"
                elif "error" in reason.lower():
                     status_class = "status-error"
                     # status_text remains "Excluded ({reason})" which contains error details

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
        number_of_queries: int = 3,
        scraping_model: str = "",
        max_search_results: int = 4,
        search_days: int = 500,
        provide_llm_facts: Literal["yes", "no"] = "yes",
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
        article_topic="Paula i Michał z 'Love Never Lies 3' wypowiadają się o kolegach z programu",
        domains=[],  # example domains
        urls=['https://party.pl/tv-show/paula-i-michal-z-love-never-lies-gorzko-o-uczestnikach-tak-nie-robia-prawdziwe-osoby-tylko-falszywe-po-emisji-w-niedziele/'],       # example URLs
        number_of_queries=1,
        scraping_model="",        # specify your scraping model if needed
        max_search_results=2,
        search_days=10,
        extraction_mode="markdown",
        provide_llm_facts="yes"
    )
    print(article)

