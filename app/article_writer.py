from __future__ import annotations
import asyncio
import os
import re
import abc
from html import escape
from dataclasses import dataclass
import logging
from typing import List, Literal, Optional
from datetime import datetime, timedelta, date as date_type # alias date to avoid conflict

from pydantic import BaseModel, Field, field_validator
from pydantic_graph import BaseNode, End, Graph, GraphRunContext
from pydantic_ai.messages import ModelMessage

# Local imports
from resilient_agent import run_with_retry, AllModelsFailedError
from searchandscrape import SearchAndScrape
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
    followup_agent_prompt,
    usage_tracking_agent_prompt,
)
from tavily import TavilyClient
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import CrawlerRunConfig, CacheMode
import tiktoken

logger = logging.getLogger(__name__)
current_date = date_type.today()

###############################################################################
# New Simplified Base Node with Centralized Error Handling
###############################################################################
class ArticleWriterBaseNode(BaseNode, abc.ABC):
    """
    A simplified base node for the article writer graph.
    It provides a central run method to catch final errors from the resilient_agent
    and other unexpected exceptions, log them, and end the graph gracefully.
    """
    @abc.abstractmethod
    async def _execute(self, ctx: GraphRunContext[State]) -> BaseNode | End:
        """The core logic specific to the node. Subclasses MUST implement this."""
        pass

    async def run(self, ctx: GraphRunContext[State]) -> BaseNode | End:
        """
        Runs the node's logic with centralized error handling.
        """
        node_name = self.__class__.__name__
        try:
            logger.info(f"Running {node_name}...")
            result = await self._execute(ctx)
            logger.info(f"{node_name} completed successfully.")
            return result
        except AllModelsFailedError as e:
            error_message = f"{node_name} failed permanently after all model retries."
            logger.error(f"{error_message} Details: {e}", exc_info=False)
            ctx.state.add_error(node_name, str(e))
            error_report = self._generate_error_report(ctx.state.errors)
            return End(f"ERROR: A critical step failed at {node_name}.\n\nError Log:\n{error_report}")
        except Exception as e:
            error_message = f"An unexpected error occurred in {node_name}: {type(e).__name__}"
            logger.error(f"{error_message}: {str(e)}", exc_info=True)
            ctx.state.add_error(node_name, f"{error_message}: {str(e)}")
            error_report = self._generate_error_report(ctx.state.errors)
            return End(f"ERROR: An unexpected critical error occurred in {node_name}.\n\nError Log:\n{error_report}")

    def _generate_error_report(self, errors: list[dict[str, str]]) -> str:
        """Generates a plain text error report from the state."""
        if not errors:
            return "No errors reported during execution."
        report = ""
        for err in errors:
            report += f"- Node: {escape(err.get('node', 'Unknown Node'))}, Error: {escape(err.get('error', 'Unknown Error'))}\n"
        return report

# ###############################################################################
# # Centralized Model Configuration
# ###############################################################################
NODE_MODEL_CONFIG = {
    "SearchNode": ["gemini-2.0-flash", "gpt-5-mini"],
    "LlmKnowledgeNode": ["gemini-2.0-flash", "gpt-5-mini"],
    "ParsingNode": ["gemini-2.0-flash", "gpt-5-mini"],
    "DataExtractionNode": ["gemini-2.0-flash", "gpt-5-mini"],
    "InstructionsNode": ["gemini-2.5-pro", "gpt-5", "gemini-2.0-flash"],
    "WritingNode": ["gemini-2.5-pro", "gemini-2.5-pro", "gpt-5", "gemini-2.0-flash"],
    "ReflectionNode": ["gemini-2.5-pro", "gpt-5", "gemini-2.0-flash"],
    "FollowUpNode": ["gemini-2.5-pro", "gemini-2.0-flash", "gpt-5", "gemini-2.0-flash"],
    "UsageTracking": ["gemini-2.0-flash", "gpt-5-mini", "gemini-2.0-flash"],
}

###############################################################################
# State definition
###############################################################################
class Configuration(BaseModel):
    article_topic: str = ""
    domains: list[str] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)
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
    facts_from_articles: list[dict] = Field(default_factory=list)

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
    errors: list[dict[str, str]] = Field(default_factory=list, description="List of errors encountered during the graph run.")

    def add_error(self, node_name: str, error_message: str):
        self.errors.append({"node": node_name, "error": error_message})

###############################################################################
# Nodes
###############################################################################
@dataclass
class SearchNode(ArticleWriterBaseNode):
    async def _execute(self, ctx: GraphRunContext[State]) -> ScrapingNode | LlmKnowledgeNode | End:
        additional_instructions = ctx.state.configuration.additional_instructions
        additional_instructions_formatted = ""
        if additional_instructions and additional_instructions.lower() not in ["none", ""]:
            additional_instructions_formatted = f"### Additional Instructions and Context:\n{additional_instructions}\nThey are very important and must be included."

        prompt = research_agent_prompt.format(
            current_date=ctx.state.current_date,
            article_topic=ctx.state.configuration.article_topic,
            number_of_queries=ctx.state.configuration.number_of_queries,
            additional_instructions_formatted=additional_instructions_formatted,
        )

        result = await run_with_retry(
            model_list=NODE_MODEL_CONFIG[self.__class__.__name__],
            output_type=ResearchPlan,
            user_prompt=prompt
        )

        if not result or not result.output:
            raise ValueError("SearchNode agent run returned invalid data.")

        ctx.state.research_plan = result.output
        ctx.state.research_plan.queries.append(ctx.state.configuration.article_topic)
        logger.info(f'Search queries generated: {ctx.state.research_plan.queries}')

        if ctx.state.configuration.provide_llm_facts == "yes":
            logger.info("Transitioning to LlmKnowledgeNode")
            return LlmKnowledgeNode()
        else:
            logger.info("Transitioning to ScrapingNode")
            return ScrapingNode()

@dataclass
class LlmKnowledgeNode(ArticleWriterBaseNode):
    async def _execute(self, ctx: GraphRunContext[State]) -> ScrapingNode | End:
        if not ctx.state.research_plan:
            raise ValueError("Cannot execute LlmKnowledgeNode: research_plan is missing.")

        prompt = llmknowledge_agent_prompt.format(
            article_topic=ctx.state.configuration.article_topic,
            initial_plan=getattr(ctx.state.research_plan, 'plan', "No plan available"),
            search_queries=getattr(ctx.state.research_plan, 'queries', []),
            current_date=ctx.state.current_date
        )

        result = await run_with_retry(
            model_list=NODE_MODEL_CONFIG[self.__class__.__name__],
            output_type=List[FactFromLlm],
            user_prompt=prompt
        )

        if result is None or result.output is None:
            raise ValueError("LlmKnowledgeNode agent run did not return valid data.")

        ctx.state.researched_info.facts_from_llm = result.output
        logger.info(f'LLM facts retrieved: {len(ctx.state.researched_info.facts_from_llm)} items.')

        logger.info("Transitioning to ScrapingNode")
        return ScrapingNode()

@dataclass
class ScrapingNode(ArticleWriterBaseNode):
    async def _execute(self, ctx: GraphRunContext[State]) -> ParsingNode | End:
        # This node does not use LLMs, so its logic remains largely the same.
        # It has been slightly simplified to remove unused error handling that is now centralized.
        logger.info("Executing ScrapingNode logic...")
        tavily_client = TavilyClient(api_key=os.getenv('TAVILY_API_KEY'))

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

        if manual_urls := ctx.state.configuration.urls:
            unique_urls.update(manual_urls)
            for url in manual_urls:
                url_to_description.setdefault(url, "Manually provided URL.")

        EXCLUDED_DOMAINS = ['youtube.com', 'facebook.com', 'twitter.com', 'x.com', 'instagram.com', 'linkedin.com', 'tiktok.com']
        filtered_urls = {url for url in unique_urls if not any(domain in url for domain in EXCLUDED_DOMAINS)}
        urls_to_scrape = list(filtered_urls)

        if not urls_to_scrape:
            logger.warning("No URLs to scrape after searching and filtering.")
            return ParsingNode()

        logger.info(f"Identified {len(urls_to_scrape)} unique URLs to scrape.")
        
        run_config = CrawlerRunConfig(
            extraction_strategy=None,
            excluded_tags=['nav', 'header', 'footer', 'aside', 'form', 'script', 'style'],
            remove_overlay_elements=True,
            process_iframes=False,
            cache_mode=CacheMode.BYPASS,
            word_count_threshold=10
        )
        
        scraped_pages_data = []
        async with AsyncWebCrawler() as crawler:
            results = await crawler.arun_many(urls=urls_to_scrape, config=run_config)
            for result in results:
                if result.success:
                    scraped_pages_data.append({
                        "url": result.url,
                        "title": result.metadata.get('title', 'Title not found'),
                        "article_body": result.markdown,
                        "description": url_to_description.get(result.url, "")
                    })
                else:
                    logger.error(f"Failed to scrape {result.url}: {result.error_message}")

        ctx.state.scraped_pages = scraped_pages_data
        logger.info(f"Scraping complete. Processed {len(scraped_pages_data)} pages.")
        return ParsingNode()

class ParsedArticle(BaseModel):
    webpage_type: Literal['article', 'other']
    parsed_article: str

@dataclass
class ParsingNode(ArticleWriterBaseNode):
    async def _execute(self, ctx: GraphRunContext[State]) -> DataExtractionNode | End:
        pages_to_process = ctx.state.scraped_pages
        if not pages_to_process:
            logger.warning("No scraped pages to parse.")
            return DataExtractionNode()

        enc = tiktoken.get_encoding("cl100k_base")
        MAX_TOKENS = 150_000

        async def process_page(page: dict):
            page_url = page.get('url', 'unknown URL')
            article_body = page.get("article_body", "")
            if not article_body:
                logger.warning(f"Page {page_url}: No article_body found. Skipping.")
                page.update({'webpage_type': 'other', 'parsed_article': None, 'parsing_error': 'Empty body'})
                return

            tokens = enc.encode(article_body)
            if len(tokens) > MAX_TOKENS:
                logger.warning(f"Page {page_url}: Article has {len(tokens)} tokens, truncating.")
                article_body = enc.decode(tokens[:MAX_TOKENS])
                page["article_body_truncated"] = True

            prompt = parsing_agent_prompt.format(html=article_body, current_date=ctx.state.current_date)
            
            try:
                result = await run_with_retry(
                    model_list=NODE_MODEL_CONFIG["ParsingNode"],
                    output_type=ParsedArticle,
                    user_prompt=prompt,
                )
                if result and result.output:
                    page.update({
                        'webpage_type': result.output.webpage_type,
                        'parsed_article': result.output.parsed_article
                    })
                    logger.debug(f"Page {page_url}: Successfully parsed.")
                else:
                    raise ValueError("Parsing agent returned empty data.")
            except Exception as e:
                logger.error(f"Page {page_url}: Failed to parse after all retries: {e}")
                page.update({'webpage_type': 'other', 'parsed_article': None, 'parsing_error': str(e)})

        await asyncio.gather(*(process_page(page) for page in pages_to_process))
        logger.info("Finished parsing all pages.")
        return DataExtractionNode()

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
            raise ValueError("Publication date cannot be None")
        if isinstance(value, date_type):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace('Z', '+00:00')).date()
            except ValueError:
                for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d"):
                    try:
                        return datetime.strptime(value, fmt).date()
                    except ValueError:
                        continue
                raise ValueError(f"Invalid date format: {value}")
        raise TypeError(f"Invalid type for date: {type(value)}")

@dataclass
class DataExtractionNode(ArticleWriterBaseNode):
    async def _execute(self, ctx: GraphRunContext[State]) -> InstructionsNode | End:
        pages_to_process = [
            p for p in ctx.state.scraped_pages if p and p.get('article_body') and not p.get('parsing_error')
        ]
        if not pages_to_process:
            logger.warning("No successfully parsed pages to extract data from.")
            if not ctx.state.researched_info.facts_from_llm:
                 raise ValueError("No parsed pages AND no LLM facts found. Cannot proceed.")
        
        async def process_page(page: dict):
            page_url = page.get('url', 'unknown URL')
            parsed_article_body = page.get("article_body", "")
            title = page.get('title', "Title not found")
            
            article_text_for_prompt = article_snippet.format(
                url=page_url, title=title, description=page.get("description", ""), article_text=parsed_article_body
            )
            page['formated_article'] = article_text_for_prompt
            page['formated_article_short'] = article_snippet_short.format(title=title, article_text=parsed_article_body)
            
            prompt = data_extraction_agent_prompt.format(text=article_text_for_prompt, topic=ctx.state.configuration.article_topic)

            try:
                result = await run_with_retry(
                    model_list=NODE_MODEL_CONFIG[self.__class__.__name__],
                    output_type=ResearchedArticle,
                    user_prompt=prompt,
                )
                if result and result.output:
                    data = result.output
                    page.update({
                        'webpage_type': data.webpage_type, 'relevant': data.relevant,
                        'facts': data.facts, 'publication_date': data.publication_date,
                        'keywords': data.keywords,
                        'quotes': [q.model_dump() for q in data.quotes if q] if data.quotes else []
                    })
                    for quote_dict in page.get('quotes', []):
                        quote_dict['page_url'] = page_url
                else:
                    raise ValueError("Data extraction agent returned empty data.")
            except Exception as e:
                logger.error(f"Page {page_url}: Failed data extraction after all retries: {e}")
                page.update({'extraction_error': str(e), 'webpage_type': 'other', 'relevant': 'no'})

        await asyncio.gather(*(process_page(page) for page in pages_to_process))

        # Filtering and Aggregation Logic (simplified)
        cutoff_date = (datetime.now().date() - timedelta(days=ctx.state.configuration.search_days))
        manual_urls = set(ctx.state.configuration.urls or [])
        articles = []

        for page in ctx.state.scraped_pages:
            page_url = page.get('url', 'N/A')
            is_manual = page_url in manual_urls
            if page.get('extraction_error') or page.get('parsing_error'):
                page['filter_reason'] = f"Processing error: {page.get('extraction_error') or page.get('parsing_error')}"
                continue
            if not is_manual:
                if page.get('webpage_type') != 'article':
                    page['filter_reason'] = "Not an article"
                    continue
                if page.get('relevant') != 'yes':
                    page['filter_reason'] = "Not relevant"
                    continue
                pub_date = page.get('publication_date')
                if not pub_date or (isinstance(pub_date, date_type) and pub_date < cutoff_date):
                    page['filter_reason'] = f"Too old: {pub_date}"
                    continue
            
            page['filter_reason'] = "Included"
            articles.append(page)

        if not articles and not ctx.state.researched_info.facts_from_llm:
            raise ValueError("No relevant articles found and no LLM facts available.")

        # Aggregate Data
        facts_from_articles = []
        for article in articles:
            if facts := article.get('facts'):
                source_url = article.get('url', '#') # Default to '#' if no URL
                for fact_text in facts:
                    facts_from_articles.append({'text': fact_text, 'source_url': source_url})
        llm_fact_strings = [fact.fact_llm for fact in ctx.state.researched_info.facts_from_llm if fact.fact_llm]
        
        ctx.state.researched_info.facts = llm_fact_strings + [f.get('text', '') for f in facts_from_articles]
        ctx.state.researched_info.facts_from_articles = facts_from_articles
        ctx.state.researched_info.quotes = [q for article in articles for q in article.get('quotes', [])]
        ctx.state.researched_info.keywords = list(set(k for article in articles for k in article.get('keywords', [])))
        ctx.state.researched_info.article_texts = "\n\n==============================\n\n".join(
            [a.get('formated_article_short', '') for a in articles]
        )
        ctx.state.sources = sorted(list(set(a['url'] for a in articles)))
        logger.info(f"Aggregated data: {len(ctx.state.researched_info.facts)} total facts ({len(llm_fact_strings)} from LLM, {len(facts_from_articles)} from articles).")
        logger.info(f"Aggregated data: {len(ctx.state.researched_info.quotes)} quotes from {len(ctx.state.sources)} sources.")
        return InstructionsNode()

@dataclass
class InstructionsNode(ArticleWriterBaseNode):
    async def _execute(self, ctx: GraphRunContext[State]) -> WritingNode | End:
        additional_instructions = ctx.state.configuration.additional_instructions
        additional_instructions_formatted = ""
        if additional_instructions and additional_instructions.lower() not in ["none", ""]:
            additional_instructions_formatted = f"### Additional Instructions and Context:\n{additional_instructions}"

        user_prompt = instructions_agent_prompt.format(
            article_texts=ctx.state.researched_info.article_texts or "No reference articles.",
            plan=ctx.state.research_plan.plan if ctx.state.research_plan else "No plan.",
            topic=ctx.state.configuration.article_topic,
            example_articles=example_articles,
            additional_instructions_formatted=additional_instructions_formatted,
        )

        result = await run_with_retry(
            model_list=NODE_MODEL_CONFIG[self.__class__.__name__],
            output_type=str,
            user_prompt=user_prompt
        )

        if not result or not result.output:
            raise ValueError("InstructionsNode agent returned empty data.")
        
        ctx.state.instructions = result.output
        return WritingNode()

@dataclass
class WritingNode(ArticleWriterBaseNode):
    async def _execute(self, ctx: GraphRunContext[State]) -> ReflectionNode | FollowUpNode | End:
        if ctx.state.reflection_round == 0:
            fact_items = ctx.state.researched_info.facts or []
            # Handle mixed list of strings and dicts
            facts_str_list = [f if isinstance(f, str) else f.get('text', '') for f in fact_items]
            facts_str = "\n - ".join(facts_str_list) if facts_str_list else "No facts available."
            keywords_str = ", ".join(ctx.state.researched_info.keywords or ["N/A"])
            quotes_str = "\n".join([f'"{escape(q.get("text",""))}" - {escape(q.get("speaker","?"))}' for q in ctx.state.researched_info.quotes or []]) or "No quotes."
            
            user_prompt = writing_agent_prompt.format(
                topic=ctx.state.configuration.article_topic, facts=facts_str, keywords=keywords_str,
                quotes=quotes_str, instructions=ctx.state.instructions, current_date=ctx.state.current_date,
                example_articles=example_articles
            )
        else:
            if not ctx.state.reflection_prompt:
                raise ValueError(f"Reflection prompt missing for round {ctx.state.reflection_round}.")
            user_prompt = ctx.state.reflection_prompt

        result = await run_with_retry(
            model_list=NODE_MODEL_CONFIG[self.__class__.__name__],
            output_type=str,
            user_prompt=user_prompt,
            message_history=ctx.state.messages
        )

        if not result or not result.output:
            raise ValueError("WritingNode agent returned empty data.")

        ctx.state.messages = result.all_messages()

        if ctx.state.reflection_round > 0:
            ctx.state.finished_article = result.output
            return FollowUpNode()
        else:
            return ReflectionNode()

@dataclass
class ReflectionNode(ArticleWriterBaseNode):
    async def _execute(self, ctx: GraphRunContext[State]) -> WritingNode | End:
        if not ctx.state.messages:
            raise ValueError("Message history is empty. Cannot perform reflection.")

        user_prompt = reflection_agent_prompt.format(
            benchmark_articles=ctx.state.researched_info.article_texts or "No benchmark articles.",
            example_articles=example_articles
        )

        result = await run_with_retry(
            model_list=NODE_MODEL_CONFIG[self.__class__.__name__],
            output_type=str,
            user_prompt=user_prompt,
            message_history=ctx.state.messages
        )

        if not result or not result.output:
            raise ValueError("ReflectionNode agent returned empty feedback.")

        ctx.state.reflection_prompt = (
            f'Follow these instructions to improve your article:\n{result.output}\n\n'
            f'--- Benchmark Articles for Reference ---\n'
            f'{ctx.state.researched_info.article_texts or "N/A"}'
        )
        ctx.state.reflection_round += 1
        return WritingNode()

class FollowUp(BaseModel):
    alternative_titles: list[str] = Field(default_factory=list)
    followup_articles: list[str] = Field(default_factory=list)

class UsedItems(BaseModel):
    used_facts: list[str] = Field(default_factory=list, description="A list of the exact facts that were used in the article.")
    used_quotes: list[str] = Field(default_factory=list, description="A list of the exact quotes that were used in the article.")

@dataclass
class FollowUpNode(ArticleWriterBaseNode):
    async def _execute(self, ctx: GraphRunContext[State]) -> End:
        used_facts_set = set()
        used_quotes_set = set()

        if ctx.state.finished_article:
            # Step 1: Run usage tracking agent
            all_facts = ctx.state.researched_info.facts or []
            all_quotes_text = [q.get('text', '') for q in ctx.state.researched_info.quotes or [] if q.get('text')]
            
            if all_facts or all_quotes_text:
                try:
                    usage_prompt = usage_tracking_agent_prompt.format(
                        article_text=ctx.state.finished_article,
                        list_of_facts="\n- ".join(all_facts),
                        list_of_quotes="\n- ".join(all_quotes_text)
                    )
                    usage_result = await run_with_retry(
                        model_list=NODE_MODEL_CONFIG["UsageTracking"],
                        output_type=UsedItems,
                        user_prompt=usage_prompt
                    )
                    if usage_result and usage_result.output:
                        used_facts_set = set(usage_result.output.used_facts)
                        used_quotes_set = set(usage_result.output.used_quotes)
                        logger.info(f"Usage tracking complete. Found {len(used_facts_set)} used facts and {len(used_quotes_set)} used quotes.")
                except Exception as e:
                    logger.warning(f"Usage tracking agent failed: {e}. Proceeding without usage data.")
                    ctx.state.add_error(self.__class__.__name__, f"Usage tracking failed: {e}")

            # Step 2: Run follow-up suggestions agent
            try:
                result = await run_with_retry(
                    model_list=NODE_MODEL_CONFIG[self.__class__.__name__],
                    output_type=FollowUp,
                    user_prompt=followup_agent_prompt.format(finished_article=ctx.state.finished_article)
                )
                follow_up_data = result.output if result and result.output else FollowUp()
            except AllModelsFailedError as e:
                logger.warning(f"Follow-up generation failed: {e}. Proceeding without suggestions.")
                ctx.state.add_error(self.__class__.__name__, f"Follow-up generation failed: {e}")
                follow_up_data = FollowUp()
        else:
            logger.error("FollowUpNode: Finished article is missing.")
            ctx.state.add_error(self.__class__.__name__, "Finished article was not generated.")
            follow_up_data = FollowUp()

        # Step 3: Construct final HTML output
        article_html = f"<article>\n{ctx.state.finished_article}\n</article>" 
        titles_html = self._generate_list_html("Alternatywne tytuły", follow_up_data.alternative_titles)
        topics_html = self._generate_list_html("Tematy do rozważenia", follow_up_data.followup_articles)
        sources_html = self._generate_detailed_sources_html("Źródła i Status Przetwarzania", ctx.state.scraped_pages)
        quotes_html = self._generate_quotes_html(ctx.state.researched_info.quotes, used_quotes_set)
        article_facts_html = self._generate_article_facts_html("Fakty z artykułów źródłowych", ctx.state.researched_info.facts_from_articles, used_facts_set)
        llm_facts_html = self._generate_llm_facts_html(ctx.state.researched_info.facts_from_llm, used_facts_set)
        error_report_html = self._generate_error_report_html(ctx.state.errors)

        full_result = f"""<!DOCTYPE html>
<html><head><title>Article Result</title><meta charset="UTF-8"><style>
body{{font-family:sans-serif;margin:20px}}article{{border:1px solid #ccc;padding:15px;margin-bottom:20px;background-color:#f9f9f9}}section{{margin-bottom:20px;border:1px solid #eee;padding:0 15px 15px 15px}}h1,h2{{color:#333}}h1{{border-bottom:2px solid #ccc;padding-bottom:5px}}h2{{border-bottom:1px solid #eee;padding-bottom:3px}}ul{{list-style-type:disc;margin-left:20px}}li{{margin-bottom:5px}}blockquote{{border-left:3px solid #ccc;padding-left:10px;margin-left:0;font-style:italic;color:#555}}.source-item{{margin-bottom:8px}}.source-url{{font-weight:bold}}.source-status{{font-style:italic;margin-left:10px;padding:2px 5px;border-radius:3px}}.status-included{{color:#2a8a2a;background-color:#e9f5e9}}.status-excluded,.status-error{{color:#b95000;background-color:#fff8e1}}.error-report{{border-color:#d32f2f;background-color:#ffebee}}.error-report h2{{color:#c00}}.used-marker{{color:green;font-weight:bold;margin-left:10px;font-size:0.8em}}
</style></head><body>
{article_html}{error_report_html}{titles_html}{topics_html}{sources_html}{quotes_html}{article_facts_html}{llm_facts_html}
</body></html>"""
        return End(full_result)

    def _generate_list_html(self, title: str, items: Optional[List[str]]) -> str:
        content = f"<ul>{''.join(f'<li>{escape(item)}</li>' for item in items)}</ul>" if items else "<ul><li>Brak danych.</li></ul>"
        return f"<section><h2>{escape(title)}</h2>{content}</section>"
    
    def _generate_quotes_html(self, quotes: Optional[list[dict]], used_quotes: set) -> str:
        if not quotes: return self._generate_list_html("Cytaty", None)
        items = []
        for q in quotes:
            text = q.get('text', 'N/A')
            used_marker = '<span class="used-marker">USED</span>' if text in used_quotes else ''
            source_parts = [escape(s) for s in [q.get('source'), q.get('page_url')] if s]
            source_details = f" (Źródło: {' / '.join(source_parts)})" if source_parts else ""
            items.append(f"<li>{escape(text)} - {escape(q.get('speaker','Unknown'))}{source_details}{used_marker}</li>")
        return f"<section><h2>Cytaty</h2><ul>{''.join(items)}</ul></section>"

    def _generate_article_facts_html(self, title: str, facts: Optional[list[dict]], used_facts: set) -> str:
        if not facts: return self._generate_list_html(title, None)
        list_items = []
        for fact in facts:
            fact_text = escape(fact.get('text', 'N/A'))
            used_marker = '<span class="used-marker">USED</span>' if fact.get('text') in used_facts else ''
            source_url = escape(fact.get('source_url', '#'))
            item_html = f'<li>{fact_text} (<a href="{source_url}" target="_blank">źródło</a>){used_marker}</li>'
            list_items.append(item_html)
        content = f"<ul>{''.join(list_items)}</ul>"
        return f"<section><h2>{escape(title)}</h2>{content}</section>"

    def _generate_llm_facts_html(self, llm_facts: Optional[list[FactFromLlm]], used_facts: set) -> str:
        if not llm_facts: return self._generate_list_html("LLM Fakty i ich źródła", None)
        items = []
        for f in llm_facts:
            fact_text = f.fact_llm or 'N/A'
            used_marker = '<span class="used-marker">USED</span>' if fact_text in used_facts else ''
            items.append(f"<li>{escape(fact_text)} (Źródło: {escape(f.source or 'N/A')}){used_marker}</li>")
        return f"<section><h2>LLM Fakty i ich źródła</h2><ul>{''.join(items)}</ul></section>"

    def _generate_error_report_html(self, errors: list[dict[str, str]]) -> str:
        if not errors: return ""
        items = [f"<strong>{escape(e.get('node','?'))}:</strong> {escape(e.get('error','?'))}" for e in errors]
        content = f"<ul>{''.join(f'<li>{item}</li>' for item in items)}</ul>"
        return f"<section class='error-report'><h2>Execution Errors Report</h2>{content}</section>"

    def _generate_detailed_sources_html(self, title: str, all_pages: list[dict]) -> str:
        if not all_pages: return self._generate_list_html(title, ["No sources were processed."])
        items = []
        for page in sorted(all_pages, key=lambda p: p.get('url', '')):
            if not page: continue
            url = escape(page.get('url', 'N/A'))
            reason = escape(page.get('filter_reason', 'Status unknown'))
            status_class = "status-included" if "Included" in reason else "status-excluded"
            items.append(f"<li class='source-item'><span class='source-url'>{url}</span> - <span class='source-status {status_class}'>{reason}</span></li>")
        return f"<section><h2>{escape(title)}</h2><ul>{''.join(items)}</ul></section>"

###############################################################################
# Class wrapper
###############################################################################
class ArticleWriter:
    @staticmethod
    def write_article(
        article_topic: str,
        domains: list[str] = [],
        urls: list[str] = [],
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
                    article_topic=article_topic, domains=domains, urls=urls or [],
                    number_of_queries=number_of_queries, scraping_model=scraping_model,
                    max_search_results=max_search_results, search_days=search_days,
                    extraction_mode=extraction_mode, provide_llm_facts=provide_llm_facts,
                    additional_instructions=additional_instructions
                )
            )
            graph = Graph(nodes=list(ArticleWriterBaseNode.__subclasses__()))
            response = await graph.run(SearchNode(), state=state)
            return response.output

        return asyncio.run(_run_graph())

###############################################################################
# Main
###############################################################################
if __name__ == "__main__":
    article = ArticleWriter.write_article(
        article_topic="Miłość i wielkie pieniądze. Cristiano dał jej pierścionek, ale umowę podpisali już dawno. Ujawniamy kwoty.",
        domains=[],
        urls=[],
        number_of_queries=1,
        max_search_results=2,
        search_days=30,
        provide_llm_facts="no",
        additional_instructions=None
    )
    print(article)