from __future__ import annotations
import asyncio
import os
import re
from typing import List, Literal, Optional, Dict
from pydantic import BaseModel, Field
from pydantic_ai.messages import ModelMessage
from pydantic_graph import BaseNode, End, Graph, GraphRunContext
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai import Agent
from dataclasses import dataclass
import tiktoken
import logging
from typing import List, Literal, Optional
from searchandscrape import SearchAndScrape
from rich import print
from dotenv import load_dotenv
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)
load_dotenv()
current_date = current_date_today = date.today()

###############################################################################
# State definition
###############################################################################
class Configuration(BaseModel):
    article_topic: str = ""
    domains: list[str] = Field(default_factory=list)
    number_of_queries: int = 2
    scraping_model: str = ""
    max_search_results: int = 3
    search_days: int = 30
    extraction_mode: Literal["markdown", "html", "llm"] = "markdown"


class ResearchPlan(BaseModel):
    queries: list[str] = Field(default_factory=list)
    plan: str = ""
    keywords: list[str] = Field(default_factory=list)
    possible_titles: list[str] = Field(default_factory=list)


class Quote(BaseModel):
    text: str | None
    speaker: str | None
    source: str | None


class ResearchedInfo(BaseModel):
    quotes: list[Quote] | None
    facts: list[str] | None
    keywords: list[str] | None
    article_texts: str | None


class State(BaseModel):
    current_date: date = current_date
    configuration: Configuration
    reflection_round: int = 0
    instructions: str = ""
    reflection_prompt: str = ""
    research_plan: ResearchPlan = None
    scraped_pages: list[Dict] = Field(default_factory=list)
    researched_info: ResearchedInfo | None = None
    finished_article: str = ""
    messages: list[ModelMessage] = Field(default_factory=list)


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
search_model = OpenAIModel('gpt-4o', api_key=os.getenv('OPENAI_API_KEY'))

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
class SearchNode(BaseNode):
    async def run(self, ctx: GraphRunContext[State]) -> ScrapingNode | End:
        # We wrap the original logic in a separate method and apply an 8-minute (600s) timeout.
        try:
            return await asyncio.wait_for(self._run_internal(ctx), 600)
        except asyncio.TimeoutError:
            return End("ERROR: SearchNode timed out")

    async def _run_internal(self, ctx: GraphRunContext[State]) -> ScrapingNode | End:
        if not hasattr(ctx.state, "_searchnode_tries"):
            ctx.state._searchnode_tries = 0
        try:
            prompt = research_agent_prompt.format(
                current_date=current_date,
                article_topic=ctx.state.configuration.article_topic,
                number_of_queries=ctx.state.configuration.number_of_queries
            )
            result = await research_agent.run(user_prompt=prompt)
            ctx.state.research_plan = result.data
            ctx.state.research_plan.queries.append(ctx.state.configuration.article_topic)
            save_state(ctx.state)
            print(f'Search queries: {ctx.state.research_plan.queries}')
            return ScrapingNode()
        except Exception as e:
            if ctx.state._searchnode_tries < 1:
                ctx.state._searchnode_tries += 1
                print("Retrying SearchNode after error...")
                ctx.state = load_state()
                return SearchNode()
            else:
                return End(f"ERROR: Error in SearchNode after retry: {str(e)}")


###############################################################################
################################ Scraping Node ################################
@dataclass
class ScrapingNode(BaseNode):
    async def run(self, ctx: GraphRunContext[State]) -> ParsingNode | End:
        # We wrap the original logic in a separate method and apply an 8-minute (600s) timeout.
        try:
            return await asyncio.wait_for(self._run_internal(ctx), 600)
        except asyncio.TimeoutError:
            return End("ERROR: ScrapingNode timed out")

    async def _run_internal(self, ctx: GraphRunContext[State]) -> ParsingNode | End:
        if not hasattr(ctx.state, "_scrapingnode_tries"):
            ctx.state._scrapingnode_tries = 0
        try:
            ctx.state = load_state()

            scraper = SearchAndScrape(
                search_domains=ctx.state.configuration.domains,
                max_results=ctx.state.configuration.max_search_results,
                days=ctx.state.configuration.search_days,
                model=ctx.state.configuration.scraping_model,
                extraction_mode="markdown"
            )

            search_tasks = [
                asyncio.create_task(asyncio.to_thread(scraper.search_urls, query))
                for query in ctx.state.research_plan.queries
            ]
            search_results = await asyncio.gather(*search_tasks)

            unique_urls = set()
            combined_descriptions = {}
            for urls, desc_map in search_results:
                unique_urls.update(urls)
                combined_descriptions.update(desc_map)
            unique_urls = list(unique_urls)

            scrape_result = await scraper.scrape_urls(unique_urls, description_mapping=combined_descriptions)
            ctx.state.scraped_pages = scrape_result["aggregated_results"]
            save_state(ctx.state)
            return ParsingNode()
        except Exception as e:
            if ctx.state._scrapingnode_tries < 1:
                ctx.state._scrapingnode_tries += 1
                print("Retrying ScrapingNode after error...")
                ctx.state = load_state()
                return ScrapingNode()
            else:
                return End(f"ERROR: Error in ScrapingNode after retry: {str(e)}")


###############################################################################
################################ Parsing Node #################################
parsing_model = OpenAIModel('o3-mini', api_key=os.getenv('OPENAI_API_KEY'))

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
class ParsingNode(BaseNode):
    async def run(self, ctx: GraphRunContext[State]) -> DataExtractionNode | End:
        # We wrap the original logic in a separate method and apply an 8-minute (600s) timeout.
        try:
            return await asyncio.wait_for(self._run_internal(ctx), 600)
        except asyncio.TimeoutError:
            return End("ERROR: ParsingNode timed out")

    async def _run_internal(self, ctx: GraphRunContext[State]) -> DataExtractionNode | End:
        if not hasattr(ctx.state, "_parsingnode_tries"):
            ctx.state._parsingnode_tries = 0
        try:
            ctx.state = load_state()
            enc = tiktoken.get_encoding("cl100k_base")
            MAX_TOKENS = 100_000

            original_pages = list(ctx.state.scraped_pages)
            tasks = []

            async def process_page(page: dict) -> Optional[str]:
                try:
                    article_body = page.get("article_body", "")
                    tokens = enc.encode(article_body)
                    token_count = len(tokens)
                    if token_count > MAX_TOKENS:
                        logger.warning(
                            f"Article from {page.get('url')} has {token_count} tokens, exceeding {MAX_TOKENS}. Truncating."
                        )
                        tokens = tokens[:MAX_TOKENS]
                        article_body = enc.decode(tokens)

                    prompt = parsing_agent_prompt.format(html=article_body)
                    result = await parsing_agent.run(user_prompt=prompt)
                    page['webpage_type'] = result.data.webpage_type
                    page['parsed_article'] = result.data.parsed_article
                    return result.data.parsed_article
                except Exception as error:
                    print(f"Error processing page {page.get('url', 'unknown')}: {error}")
                    if page in ctx.state.scraped_pages:
                        ctx.state.scraped_pages.remove(page)
                    return None

            for page in original_pages:
                tasks.append(process_page(page))

            await asyncio.gather(*tasks)
            save_state(ctx.state)
            return DataExtractionNode()
        except Exception as e:
            if ctx.state._parsingnode_tries < 1:
                ctx.state._parsingnode_tries += 1
                print("Retrying ParsingNode after error...")
                ctx.state = load_state()
                return ParsingNode()
            else:
                return End(f"ERROR: Error in ParsingNode after retry: {str(e)}")


###############################################################################
############################# DataExtraction Node #############################
data_extraction_model = OpenAIModel('o3-mini', api_key=os.getenv('OPENAI_API_KEY'))

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

@dataclass
class DataExtractionNode(BaseNode):
    async def run(self, ctx: GraphRunContext[State]) -> InstructionsNode | End:
        # We wrap the original logic in a separate method and apply an 8-minute (600s) timeout.
        try:
            return await asyncio.wait_for(self._run_internal(ctx), 600)
        except asyncio.TimeoutError:
            return End("ERROR: DataExtractionNode timed out")

    async def _run_internal(self, ctx: GraphRunContext[State]) -> InstructionsNode | End:
        if not hasattr(ctx.state, "_dataextractionnode_tries"):
            ctx.state._dataextractionnode_tries = 0
        try:
            ctx.state = load_state()

            data_extraction_agent = Agent(
                model=data_extraction_model,
                result_type=ResearchedArticle,
                retries=2
            )

            async def process_page(page: dict) -> Optional[ResearchedArticle]:
                try:
                    url = page["url"]
                    description = page.get("description", "No description available")
                    parsed_article = page.get("parsed_article", "")
                    title_match = re.search(r"<h1.*?>(.*?)</h1>", parsed_article, re.IGNORECASE)
                    title = title_match.group(1).strip() if title_match else "Title not found"
                    article_text = re.sub(r"<h1.*?>.*?</h1>", "", parsed_article, flags=re.IGNORECASE).strip()

                    formated_article = article_snippet.format(
                        url=url, title=title, description=description, article_text=article_text
                    )
                    page['formated_article'] = formated_article

                    formated_article_short = article_snippet_short.format(
                        title=title, article_text=article_text
                    )
                    page['formated_article_short'] = formated_article_short

                    prompt = data_extraction_agent_prompt.format(
                        text=formated_article,
                        topic=ctx.state.configuration.article_topic
                    )
                    print(f'formatted_article: {formated_article}')
                    researched_article = await data_extraction_agent.run(user_prompt=prompt)
                    print(f'researched_article: {researched_article.data}')

                    page['webpage_type'] = researched_article.data.webpage_type
                    page['relevant'] = researched_article.data.relevant
                    page['facts'] = researched_article.data.facts
                    page['quotes'] = researched_article.data.quotes
                    page['keywords'] = researched_article.data.keywords
                    page['publication_date'] = researched_article.data.publication_date

                    return researched_article.data
                except Exception as error:
                    print(f"Error processing page {page.get('url', 'unknown')}: {error}")
                    if page in ctx.state.scraped_pages:
                        ctx.state.scraped_pages.remove(page)
                    return None

            tasks = [process_page(page) for page in ctx.state.scraped_pages]
            await asyncio.gather(*tasks)

            x_days = ctx.state.configuration.search_days
            cutoff_date = datetime.now().date() - timedelta(days=x_days)
            print(f'cutoff_date: {cutoff_date}')

            def parse_pub_date(pub_date):
                if isinstance(pub_date, str):
                    return datetime.strptime(pub_date, "%d.%m.%Y").date()
                elif isinstance(pub_date, date):
                    return pub_date
                else:
                    return None

            articles = [
                res for res in ctx.state.scraped_pages
                if res is not None
                and res.get('webpage_type') == "article"
                and res.get('relevant') == "yes"
                and ((pub_date := parse_pub_date(res.get('publication_date'))) is not None and pub_date >= cutoff_date)
            ]

            if not articles:
                return End("All articles filtered out or none match criteria.")

            combined_facts = []
            combined_quotes = []
            combined_keywords = []

            for article in articles:
                if article.get('facts'):
                    combined_facts.extend(article['facts'])
                if article.get('quotes'):
                    combined_quotes.extend(article['quotes'])
                if article.get('keywords'):
                    combined_keywords.extend(article['keywords'])

            if not combined_facts:
                return End("No facts found in filtered articles. Cannot proceed.")

            combined_info = ResearchedInfo(
                quotes=combined_quotes if combined_quotes else None,
                facts=combined_facts,
                keywords=combined_keywords,
                article_texts="\n".join(article['formated_article_short'] for article in articles)
            )
            ctx.state.researched_info = combined_info

            save_state(ctx.state)
            return InstructionsNode()
        except Exception as e:
            if ctx.state._dataextractionnode_tries < 1:
                ctx.state._dataextractionnode_tries += 1
                print("Retrying DataExtractionNode after error...")
                ctx.state = load_state()
                return DataExtractionNode()
            else:
                return End(f"ERROR: Error in DataExtractionNode after retry: {str(e)}")


###############################################################################
############################## Instructions Node ##############################
instructions_model = OpenAIModel('o3-mini', api_key=os.getenv('OPENAI_API_KEY'))

instructions_agent_prompt = """
You are an **Editor-in-Chief**. Your task is to provide detailed, structured instructions for a journalist to write a **high-quality web article**.

### Key Requirements:
- Be **very specific** about:
  - **H1 Title**: The main title should be **highly clickbaity** to drive engagement but **must not be misleading**. The titles from the reference articles are a good benchmark.
  - **Structure**: Outline headings (H1, H2), article lead and how to break the content into sections.
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
class InstructionsNode(BaseNode):
    async def run(self, ctx: GraphRunContext[State]) -> WritingNode | End:
        # We wrap the original logic in a separate method and apply an 8-minute (600s) timeout.
        try:
            return await asyncio.wait_for(self._run_internal(ctx), 600)
        except asyncio.TimeoutError:
            return End("ERROR: InstructionsNode timed out")

    async def _run_internal(self, ctx: GraphRunContext[State]) -> WritingNode | End:
        if not hasattr(ctx.state, "_instructionsnode_tries"):
            ctx.state._instructionsnode_tries = 0
        try:
            ctx.state = load_state()

            user_prompt = instructions_agent_prompt.format(
                article_texts=ctx.state.researched_info.article_texts,
                plan=ctx.state.research_plan.plan,
                topic=ctx.state.configuration.article_topic
            )
            instructions_agent = Agent(
                model=instructions_model,
                result_type=str,
                retries=2
            )
            result = await instructions_agent.run(user_prompt=user_prompt)
            ctx.state.instructions = result.data
            save_state(ctx.state)
            return WritingNode()
        except Exception as e:
            if ctx.state._instructionsnode_tries < 1:
                ctx.state._instructionsnode_tries += 1
                print("Retrying InstructionsNode after error...")
                ctx.state = load_state()
                return InstructionsNode()
            else:
                return End(f"ERROR: Error in InstructionsNode after retry: {str(e)}")


###############################################################################
################################ Writing Node #################################
writing_model = OpenAIModel(
    model_name='deepseek/deepseek-r1',
    base_url='https://openrouter.ai/api/v1',
    api_key=os.getenv('OPENROUTER_API_KEY'),
)

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
class WritingNode(BaseNode):
    async def run(self, ctx: GraphRunContext[State]) -> End | ReflectionNode | FollowUpNode:
        # We wrap the original logic in a separate method and apply an 8-minute (600s) timeout.
        try:
            return await asyncio.wait_for(self._run_internal(ctx), 600)
        except asyncio.TimeoutError:
            return End("ERROR: WritingNode timed out")

    async def _run_internal(self, ctx: GraphRunContext[State]) -> End | ReflectionNode | FollowUpNode:
        if not hasattr(ctx.state, "_writingnode_tries"):
            ctx.state._writingnode_tries = 0
        try:
            ctx.state = load_state()
            writing_agent = Agent[None, str](
                model=writing_model,
                result_type=str,
                retries=2
            )
            if ctx.state.reflection_round == 0:
                user_prompt = writing_agent_prompt.format(
                    topic=ctx.state.configuration.article_topic,
                    facts=ctx.state.researched_info.facts,
                    keywords=ctx.state.researched_info.keywords,
                    quotes=ctx.state.researched_info.quotes,
                    instructions=ctx.state.instructions,
                    current_date=ctx.state.current_date
                )
            else:
                user_prompt = ctx.state.reflection_prompt

            print(f'WRITER PROMPT (Round: {ctx.state.reflection_round}): {user_prompt}')
            result = await writing_agent.run(user_prompt=user_prompt, message_history=ctx.state.messages)
            ctx.state.messages = result.all_messages()

            if ctx.state.reflection_round > 0:
                ctx.state.finished_article = result.data
                save_state(ctx.state)
                print(f"return End {result.data}")
                return FollowUpNode()
                # return End(result.data)
            else:
                save_state(ctx.state)
                print("go to ReflectionNode")
                return ReflectionNode()
        except Exception as e:
            if ctx.state._writingnode_tries < 1:
                ctx.state._writingnode_tries += 1
                print("Retrying WritingNode after error...")
                ctx.state = load_state()
                return WritingNode()
            else:
                return End(f"ERROR: Error in WritingNode after retry: {str(e)}")


###############################################################################
############################### Reflection Node ###############################
reflection_model = OpenAIModel('o3-mini', api_key=os.getenv('OPENAI_API_KEY'))

reflection_agent_prompt = """You are an **Editor-in-Chief**. Your task is to **review the article** written by the editor agent and provide **detailed, relevant, and actionable feedback**. Your output must consist solely of a structured AI prompt for a writing agent—do not include any additional commentary or explanations. The entire feedback must be written in the same language as the revised article.

Your review must:
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

### High-quality Benchmark Articles:
{benchmark_articles}
"""

@dataclass
class ReflectionNode(BaseNode):
    async def run(self, ctx: GraphRunContext[State]) -> WritingNode | End:
        # We wrap the original logic in a separate method and apply an 8-minute (600s) timeout.
        try:
            return await asyncio.wait_for(self._run_internal(ctx), 600)
        except asyncio.TimeoutError:
            return End("ReflectionNode timed out")

    async def _run_internal(self, ctx: GraphRunContext[State]) -> WritingNode | End:
        if not hasattr(ctx.state, "_reflectionnode_tries"):
            ctx.state._reflectionnode_tries = 0
        try:
            ctx.state = load_state()
            reflection_agent = Agent(
                model=reflection_model,
                result_type=str,
            )
            user_prompt = reflection_agent_prompt.format(
                benchmark_articles=ctx.state.researched_info.article_texts
            )
            result = await reflection_agent.run(user_prompt=user_prompt, message_history=ctx.state.messages)
            ctx.state.reflection_prompt = (
                f'Follow these instructions to improve your article:\n {result.data}'
                f'\n Use these arricles below as a benchmark and additional inspiration:\n {ctx.state.researched_info.article_texts}'
            )
            ctx.state.reflection_round += 1
            save_state(ctx.state)
            return WritingNode()
        except Exception as e:
            if ctx.state._reflectionnode_tries < 1:
                ctx.state._reflectionnode_tries += 1
                print("Retrying ReflectionNode after error...")
                ctx.state = load_state()
                return ReflectionNode()
            else:
                return End(f"ERROR: Error in ReflectionNode after retry: {str(e)}")

###############################################################################
############################## Follow up Node ##############################
followup_model = OpenAIModel('o3-mini', api_key=os.getenv('OPENAI_API_KEY'))

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
class FollowUpNode(BaseNode):
    async def run(self, ctx: GraphRunContext[State]) -> End:
        # We wrap the original logic in a separate method and apply an 8-minute (600s) timeout.
        try:
            return await asyncio.wait_for(self._run_internal(ctx), 600)
        except asyncio.TimeoutError:
            return End("ReflectionNode timed out")

    async def _run_internal(self, ctx: GraphRunContext[State]) -> WritingNode | End:
        if not hasattr(ctx.state, "_followupnode_tries"):
            ctx.state._followupnode_tries = 0
        try:
            ctx.state = load_state()
            followup_agent = Agent(
                model=followup_model,
                result_type=FollowUp,
            )
            user_prompt = followup_agent_prompt.format(
                finished_article=ctx.state.finished_article
            )
            result = await followup_agent.run(user_prompt=user_prompt)
            
            full_result = (
                f"{ctx.state.finished_article}\n"
                f"Atrernatywne tytuły\n"
                f"{'\n'.join(result.data.alternative_titles)}\n"
                f"Tematy do rozważenia\n"
                f"{'\n'.join(result.data.followup_articles)}"
            )          
            save_state(ctx.state)
            return End(full_result)
        except Exception as e:
            if ctx.state._followupnode_tries < 1:
                ctx.state._followupnode_tries += 1
                print("Retrying FollowUpNode after error...")
                ctx.state = load_state()
                return ReflectionNode()
            else:
                return End(f"ERROR: Error in FollowUpNode after retry: {str(e)}")


###############################################################################
# Class wrapper so you can use it in other parts of your code
###############################################################################
class ArticleWriter:
    @staticmethod
    def write_article(
        article_topic: str,
        domains: List[str],
        number_of_queries: int = 3,
        scraping_model: str = "",
        max_search_results: int = 4,
        search_days: int = 500,
        extraction_mode: Literal["markdown", "html", "llm"] = "markdown",
    ) -> str:
        """
        Runs the entire article-writing process asynchronously.
        Returns the final article text as a string.
        """
        async def _run_graph():
            state = State(
                configuration=Configuration(
                    article_topic=article_topic,
                    domains=domains,
                    number_of_queries=number_of_queries,
                    scraping_model=scraping_model,
                    max_search_results=max_search_results,
                    search_days=search_days,
                    extraction_mode=extraction_mode,
                )
            )
            graph = Graph(nodes=(
                SearchNode, ScrapingNode, ParsingNode,
                DataExtractionNode, InstructionsNode,
                WritingNode, ReflectionNode, FollowUpNode
            ))
            response = await graph.run(SearchNode(), state=state)
            print(f"_run_graph {response}")
            return response.output

        final_article = asyncio.run(_run_graph())
        return final_article


###############################################################################
# Main
###############################################################################
async def main():
    graph = Graph(nodes=(
        SearchNode, ScrapingNode, ParsingNode,
        DataExtractionNode, InstructionsNode,
        WritingNode, ReflectionNode, FollowUpNode,
    ))
    state = State(
        configuration=Configuration(
            article_topic='​Podróże literackie – śladami słynnych pisarzy i poetów',
            # domains=['podroze.onet.pl','turystyka.wp.pl','top.pl','podroze.se.pl','turysci.pl'],
            domains=[],
            search_days=1500,
            number_of_queries=3,
            max_search_results=4,
        )
    )
    response = await graph.run(SearchNode(), state=state)
    # print(f'FINAL RESPONSE: {response.output}')

if __name__ == "__main__":
    asyncio.run(main())
