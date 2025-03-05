import asyncio  # For asynchronous programming.
import os       # For interacting with environment variables.
import json     # For JSON parsing and generation.
import logging  # For logging messages.
from dotenv import load_dotenv  # To load environment variables from a .env file.
from rich import print as rich_print  # Enhanced printing with colors (aliased).
from rich.logging import RichHandler  # Provides colorful logging output.
from pydantic import BaseModel  # For creating data models with validation.
from tavily import TavilyClient  # Client for performing web searches via the Tavily API.

# Import modules from Crawl4AI for asynchronous web crawling.
from crawl4ai import AsyncWebCrawler, CrawlerMonitor
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from crawl4ai.async_dispatcher import MemoryAdaptiveDispatcher

# ------------------------------------------------------------------------------
# Configure Logging
# ------------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,  # Log INFO level and above.
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler()]  # Use RichHandler for colorful output.
)
logger = logging.getLogger("SearchAndScrape")

# ------------------------------------------------------------------------------
# Load Environment Variables
# ------------------------------------------------------------------------------
load_dotenv()  # Load sensitive data (like API keys) from a .env file.

# ------------------------------------------------------------------------------
# Define Data Models
# ------------------------------------------------------------------------------
class Article(BaseModel):
    """
    Pydantic model representing the structure of an article.
    """
    title: str         # The article's title.
    article_body: str  # The main text content of the article.

# ------------------------------------------------------------------------------
# Define the Main Class: SearchAndScrape
# ------------------------------------------------------------------------------
class SearchAndScrape:
    def __init__(
        self,
        search_domains: list[str] = ['styl.fm', 'party.pl', 'plejada.pl', 'pudelek.pl'],
        max_results: int = 3,
        days: int = 30,
        model: str = "openai/gpt-4o-mini",
        instruction: str = None,  # Custom instruction for LLM extraction.
        extraction_mode: str = "llm"  # "llm", "markdown", or "html"
    ):
        self.search_domains = search_domains
        self.max_results = max_results
        self.days = days
        self.model = model
        self.extraction_mode = extraction_mode.lower()

        if self.extraction_mode not in ["llm", "markdown", "html"]:
            raise ValueError("extraction_mode must be one of 'llm', 'markdown', or 'html'.")

        if instruction is None:
            instruction = (
                "Extract the article title and article body from the content. "
                "Article body is the main text of the article including article title, article lead, headings (h2, h3, h4) and paragraphs. "
                "The article body is not a summary; it must be an exact quotation of the content. "
                "Use html tags to mark headings, strongs, etc. "
                "Don't include links, images, author, publication date or ads in article body, just the text."
            )
        self.instruction = instruction

        # Initialize Tavily Client
        self.tavily_client = TavilyClient(api_key=os.getenv('TAVILY_API_KEY'))

        # Choose Extraction Strategy Based on extraction_mode
        if self.extraction_mode == "llm":
            self.llm_strategy = LLMExtractionStrategy(
                provider=self.model,
                api_token=os.getenv('OPENAI_API_KEY'),
                schema=Article.model_json_schema(),
                extraction_type="schema",
                instruction=self.instruction,
                apply_chunking=False,
                input_format="markdown",
                extra_args={"temperature": 0.0}
            )
            extraction_strategy = self.llm_strategy
        else:
            extraction_strategy = None  # Let Crawl4AI produce markdown or HTML.

        # Configure Browser Settings for the Crawler
        self.browser_config = BrowserConfig(
            # verbose=True,
            # user_agent_mode="random",
            # text_mode=True,
            # light_mode=True,
            headless=True,
            verbose=False,
            extra_args=["--disable-gpu", "--disable-dev-shm-usage", "--no-sandbox"],
        )

        # Configure Crawler Run Settings
        self.run_config = CrawlerRunConfig(
            extraction_strategy=extraction_strategy,
            word_count_threshold=10,
            excluded_tags=['form', 'header'],
            exclude_external_links=True,
            process_iframes=True,
            remove_overlay_elements=True,
            cache_mode=CacheMode.BYPASS,
            stream=True
        )

    def search_urls(self, phrase: str) -> tuple[list[str], dict]:
        response = self.tavily_client.search(
            query=phrase,
            max_results=self.max_results,
            days=self.days,
            include_domains=self.search_domains
        )
        urls = []
        url_to_description = {}
        if isinstance(response, dict):
            results = response.get("results", [])
            if isinstance(results, list):
                for res in results:
                    url = res.get("url")
                    if url:
                        urls.append(url)
                        url_to_description[url] = res.get("content", "")
        return urls, url_to_description

    async def _process_result(self, result, description_mapping: dict) -> dict | None:
        try:
            desc = description_mapping.get(result.url, "")
            if not result.success:
                logger.error(f"Crawl failed for {result.url}: {result.error_message}")
                return None

            if self.extraction_mode == "llm":
                try:
                    data = json.loads(result.extracted_content)
                except Exception as e:
                    logger.error(f"JSON decode error for {result.url}: {e}")
                    return None

                if isinstance(data, list):
                    if data and isinstance(data[0], dict):
                        data = data[0]
                    else:
                        logger.error(f"Unexpected data format (list) for {result.url}")
                        return None

                if not isinstance(data, dict):
                    logger.error(f"Unexpected data format for {result.url}: {data}")
                    return None

                title = data.get("title")
                article_body = data.get("article_body")
                if not title or not article_body:
                    logger.error(f"Missing title or article_body for {result.url}")
                    return None

                return {
                    "url": result.url,
                    "title": title,
                    "article_body": article_body,
                    "description": desc
                }

            elif self.extraction_mode == "markdown":
                return {
                    "url": result.url,
                    "title": "",
                    "article_body": str(result.markdown),
                    "description": desc
                }

            elif self.extraction_mode == "html":
                return {
                    "url": result.url,
                    "title": "",
                    "article_body": result.html,
                    "description": desc
                }

        except Exception as e:
            logger.error(f"Error processing result for {result.url}: {e}")
            return None

    async def _scrape(self, urls: list[str], description_mapping: dict) -> dict:
        aggregated_results = []

        dispatcher = MemoryAdaptiveDispatcher(
            memory_threshold_percent=90.0,
            check_interval=0.5,
            max_session_permit=50,
            # monitor=CrawlerMonitor(display_mode="DETAILED")
        )

        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            async for result in await crawler.arun_many(
                urls=urls,
                config=self.run_config,
                dispatcher=dispatcher
            ):
                processed = await self._process_result(result, description_mapping)
                if processed is not None:
                    aggregated_results.append(processed)

        if self.extraction_mode == "llm":
            self.llm_strategy.show_usage()

        formatted_str = SearchAndScrape.format_results(aggregated_results)
        return {"formatted_str": formatted_str, "aggregated_results": aggregated_results}

    async def search_and_scrape(self, phrase: str) -> dict:
        urls, description_mapping = self.search_urls(phrase)
        if not urls:
            logger.error(f"No URLs found for phrase: {phrase}")
            return {"formatted_str": "", "aggregated_results": []}
        return await self._scrape(urls, description_mapping)

    async def scrape_urls(self, urls: list[str], description_mapping: dict = None) -> dict:
        """
        Scrape a provided list of URLs along with their descriptions.
        """
        if description_mapping is None:
            description_mapping = {}
        if not urls:
            logger.error("No URLs provided for scraping")
            return {"formatted_str": "", "aggregated_results": []}
        return await self._scrape(urls, description_mapping)

    @classmethod
    def format_results(cls, results: list[dict]) -> str:
        output_lines = []
        for idx, result in enumerate(results, start=1):
            output_lines.append("=" * 80)
            output_lines.append(f"Result #{idx}")
            output_lines.append("-" * 80)
            output_lines.append(f"URL: {result.get('url')}")
            output_lines.append(f"Title: {result.get('title')}")
            output_lines.append(f"Description: {result.get('description')}")
            output_lines.append("Article Body:")
            output_lines.append(result.get("article_body"))
            output_lines.append("=" * 80)
            output_lines.append("\n")
        return "\n".join(output_lines)


# ------------------------------------------------------------------------------
# Example Usage
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    search_phrase = "eurowizja 2025"

    custom_instruction = (
        "Please extract the article's title and full article body verbatim. "
        "Ensure that the article body includes all headings and paragraphs without any additional commentary or summaries."
    )

    # Choose one of: "llm", "markdown", or "html"
    scraper = SearchAndScrape(
        search_domains=["styl.fm", "party.pl", "plejada.pl", "pudelek.pl"],
        max_results=3,
        days=30,
        model="openai/gpt-4o-mini",
        instruction=custom_instruction,
        extraction_mode="llm"  # ← Change this to "llm", "markdown", or "html"
    )

    # Run the search and scrape process asynchronously.
    results_dict = asyncio.run(scraper.search_and_scrape(search_phrase))

    # If you're returning HTML, printing it with Rich might produce weird colored blocks.
    # To avoid that, either disable Rich markup or use a standard print.
    # Example: plain Python print for the final output:
    print(results_dict["formatted_str"])  # Plain print with HTML content
    # Also print the raw JSON result (formatted) for debugging.
    print(json.dumps(results_dict["aggregated_results"], indent=4, ensure_ascii=False))
