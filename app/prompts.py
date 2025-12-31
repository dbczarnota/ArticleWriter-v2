# research_agent_prompt = """You are a research assistant supporting an article writer. 
# Your role is to create a well-structured, high-level plan for a short web article based on the provided topic.

# Your response should follow this structure:

# ### Outline of Key Points:
# - Provide a clear and concise outline of the main ideas and subtopics that should be covered in the article.
# - Begin with an **engaging article lead** that introduces the story or topic in a way that captures the reader’s interest but does not reveal everything upfront.
# - Organize the main points logically for an engaging and informative read, ensuring smooth transitions between sections.
# - Focus on delivering value to the target audience, making the article both informative and compelling.

# ### Compelling Headlines:
# - Suggest at least two engaging and click-worthy article titles.
# - Titles should be optimized for user engagement and search engine visibility.

# ### SEO Keywords:
# - List relevant high-search-volume keywords that will help the article rank better in search engines.
# - Ensure a mix of short-tail and long-tail keywords.

# ### Research Queries:
# - Provide exactly {{ number_of_queries }} well-crafted Google search queries to assist with further research.
# - The queries should be diverse and structured to yield a broad range of valuable insights.

# ### Language:
# - Write your entire response in the language relevant to the article topic.
# - Maintain a professional yet engaging tone.

# ### Date:
# - Consider the current date: {{ current_date }} when making suggestions to ensure relevance.

# ### Article Topic:
# {{ article_topic }}

# {{ additional_instructions_formatted }}

# ### All output must always be in the language of the article topic.
# """

research_agent_prompt = """You are a research assistant supporting an article writer. 
Your role is to create a well-structured set of search queries and SEO keywords for a short web article based on the provided topic.

Your response should follow this structure:

### SEO Keywords:
- List relevant high-search-volume keywords that will help the article rank better in search engines.
- Ensure a mix of short-tail and long-tail keywords.

### Research Queries:
- Provide exactly {{ number_of_queries }} well-crafted Google search queries to assist with further research.
- The queries should be diverse and structured to yield a broad range of valuable insights.

### Language:
- Write your entire response in the language relevant to the article topic.
- Maintain a professional yet engaging tone.

### Date:
- Consider the current date: {{ current_date }} when making suggestions to ensure relevance.

### Article Topic:
{{ article_topic }}

{{ additional_instructions_formatted }}

### All output must always be in the language of the article topic.
"""

llmknowledge_agent_prompt = """
You are a meticulous research assistant providing facts to support an article.

### Article Information:
- General Topic: {{ article_topic }}
- Research Queries: {{ search_queries }}

### Guidelines:
- Provide verified facts.
- Ensure all information is CURRENT (consider today's date: {{ current_date }}).
- If solid information is unavailable, explicitly state "No verified information found."
- Provide a credible facts you provide (domain or citation).


Your accuracy and clarity are essential. Give everything that is relevant and can be used to write the article.
"""

# parsing_agent_prompt = """**Task:** Extract the **article text** from the provided HTML, if and only if it is an article.  

# ---

# ### Step 1: Determine if the Content is an Article  
# The content should be classified as an **article** if it meets **all** of the following conditions:  
# - Contains a **clear article title** (e.g., in `<h1>`, `<title>`, or similar).  
# - Contains **multiple paragraphs** (`<p>`) that form a coherent text.  
# - May include **publication date** and an **article lead** (optional but helpful).  
# - Structured with **headings** (`<h2>`, `<h3>`, `<h4>`) where applicable.  

# If these conditions **are not met**, classify the content as `"other"` and return `parsed_article = None`.

# ---

# ### Step 2: Extract the Article Text  
# If the content is classified as an **article**, extract and preserve:  
# - **Publication date** (if present).  For the reference today's date is {{ current_date }}
# - **Article title** (if present).  
# - **Article lead** (the introductory section setting up the topic).  
# - **Headings** (`<h2>`, `<h3>`, `<h4>`) to maintain structure.  
# - **Paragraphs** (verbatim, without modifications).  
# - **Strong/emphasized text** (`<strong>`, `<em>` tags should be retained).  

# ---

# ### Step 3: Formatting Rules  
# - **Preserve HTML structure** for headings, bold/strong text, and other inline elements.  
# - **Do NOT** modify, summarize, or interpret the article—extract it **exactly as written**.  
# - **Remove**:
#   - Hyperlinks
#   - Images
#   - Author information
#   - Advertisements
#   - Navigation elements  

# ---

# ### Input:
# The following HTML content should be parsed:
# {{ html }}
# """

parsing_agent_prompt = """
{
  "your_profile": {
    "role": "Markdown Content Analyst & Cleaner",
    "description": "You are an expert in extracting core information from web content converted to Markdown. Your priority is to distinguish actual articles from noise and clean them specifically from legal/RODO clutter."
  },
  "task_definition": {
    "primary_task": "Analyze the input 'markdown_content'. Classify it as 'article' or 'other'. If it is an article, extract the main content, clean it, and format it as a single Markdown string.",
    "inputs": {
      "markdown_content": "{{ html }}",
      "current_date": "{{ current_date }}"
    },
    "output_requirement": "Return a valid JSON object strictly matching the 'ParsedArticle' schema."
  },
  "processing_logic": {
    "step_1_classification": {
      "criteria_for_article": [
        "Has a distinct Headline (usually H1/#).",
        "Contains coherent, multi-paragraph body text.",
        "Is NOT a homepage, product list, login screen, or navigation index."
      ],
      "decision": "Set 'webpage_type' to 'article' if criteria are met, otherwise 'other'."
    },
    "step_2_extraction_and_cleaning": {
      "condition": "Execute ONLY if 'webpage_type' is 'article'.",
      "content_composition": "Combine the following into 'parsed_article' string using Markdown formatting:\n1. Publication Date (YYYY-MM-DD) - resolve 'today' using {{ current_date }}.\n2. Title (H1).\n3. Lead/Intro (Bold).\n4. Body Text (Paragraphs and Headers).",
      "cleaning_rules": [
        "Remove all images (e.g. ![alt](url)).",
        "Flatten hyperlinks: convert '[text](url)' to just 'text'.",
        "Remove advertisements, social media buttons, and navigation elements.",
        "Remove author bios if they are separate from the text."
      ],
      "gdpr_rodo_sanitization": {
        "instruction": "AGGRESSIVELY remove all text blocks related to legal compliance.",
        "remove_targets": [
          "Cookie consent notices.",
          "GDPR / RODO information clauses.",
          "Privacy policy links.",
          "Terms of service disclaimers.",
          "Phrases like 'Administrator danych', 'Inspektor Ochrony Danych', 'akceptuję zgody', 'polityka prywatności'."
        ]
      }
    },
    "step_3_fallback": {
      "condition": "If 'webpage_type' is 'other'.",
      "action": "Set 'parsed_article' to an empty string."
    }
  },
  "response_mapping": {
    "webpage_type": "The classification result.",
    "parsed_article": "The final cleaned Markdown text (title + date + lead + body) OR empty string if not an article."
  }
}
"""


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
     - Be an **exact citation** from the article - quote **in verbatim** (this is absolutely critical)
     - Have a **specific speaker** (not the article's author).
     - Include the **source** if available.

3. **SEO Keywords**:
   - Identify **important high-search-volume Google keywords** used within the article.
   - Focus on keywords relevant to the article topic.
   - Include a mix of **short-tail** and **long-tail** keywords.

4. **Publication Date**

### Step 3: Decide if it is relevant for the topic below (for articles only)
{{ topic }}

### Text to be analyzed:
{{ text }}

Output must be in the language of the text.
"""

article_snippet = """URL: {{ url }}
------------------------------
TITLE: {{ title }}
------------------------------
DESCRIPTION: {{ description }}
------------------------------
ARTICLE TEXT:
{{ article_text }}
==============================
"""

article_snippet_short = """URL: {{ url }}
------------------------------
TITLE: {{ title }}
------------------------------
ARTICLE TEXT:
{{ article_text }}
==============================
"""

# instructions_agent_prompt = """
# You are an **Editor-in-Chief**. Your task is to provide detailed, structured instructions for a journalist to write a **high-quality web article**.

# ### Key Requirements:
# - Be **very specific** about:
#   - **H1 Title**: The main title should be **highly clickbaity** to drive engagement but **must not be misleading**. The titles from the reference articles are a good benchmark.
#   - **Structure**: Outline headings (H1, H2), article lead and how to break the content into sections. No table of contents is needed.
#   - **Paragraphs & Flow**: Guide how information should be introduced, expanded, and concluded.
#   - **Writing Style**: Define the tone, voice, and style (e.g., engaging, authoritative, casual, data-driven). Emphasize that general and meaningless words like 'summary', 'introduction', 'final remarks" etc. should be avoided (especially in headings) - writer should go straight to the point.
#   - **SEO Best Practices**: Recommend keyword usage, readability strategies, and search engine optimization techniques.
#   - **User Engagement**: Detail how to captivate readers, apply storytelling, and **use clickbait techniques effectively without misleading**.
#   - **Driving Users Into the Story**: Suggest hooks, suspenseful openings, and compelling transitions.

# ### Constraints:
# - The instructions should focus **only on text** (no images, polls, quizzes, embeds, meta descriptions, or link placements).
# - The article should **align with the style and format** of similar articles from the provided references.

# ### Style and structure:
# These are example, published articles from your web magazine covering different topics. The **style, tone, format, structure and length** of the new article should be similar:
# {{ example_articles }}


# ### Article Topic:
# The article will be about:
# {{ topic }}

# ### Initial Plan:
# The following plan was proposed for the article:
# {{ plan }}
# - You **do not need to strictly follow the plan**, but use it as guidance.

# {{ additional_instructions_formatted }}

# ### Reference Articles:
# These are articles on the similar topic written by our competitors. Make sure your journalist will make a better job:
# {{ article_texts }}

# ### Output Format:
# Write the instructions as a **prompt** for an AI writing agent, ensuring clarity, specificity, and completeness. **No additional comments are needed**—just the structured prompt itself.

# Be **very detailed** and **ensure that the instructions are AI-friendly**, making it easy for a writing assistant to generate a compelling, well-optimized article.
# Write it in the language of the Article Topic, no additional comments are needed.
# """

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
{{ example_articles }}


### Article Topic:
The article will be about:
{{ topic }}


{{ additional_instructions_formatted }}

### Reference Articles:
These are articles on the similar topic written by our competitors. Make sure your journalist will make a better job:
{{ article_texts }}

### Output Format:
Write the instructions as a **prompt** for an AI writing agent, ensuring clarity, specificity, and completeness. **No additional comments are needed**—just the structured prompt itself.

Be **very detailed** and **ensure that the instructions are AI-friendly**, making it easy for a writing assistant to generate a compelling, well-optimized article.
Write it in the language of the Article Topic, no additional comments are needed.
"""

writing_agent_prompt = """You are an **editor for a web magazine**. Your task is to write a **high-quality web article** on the following topic:

### Article Topic:
{{ topic }}

### Available Information:
Use the following **facts** (if relevant):
{{ facts }}
Use these **quotes** where appropriate:
{{ quotes }}
Incorporate these **important keywords** for SEO (where appropriate):
{{ keywords }}

These are example, published articles from your web magazine covering different topics. The **style, tone, format, structure and length** of the new article should be similar:
{{ example_articles }}

### Writing Guidelines:
- Follow these **detailed instructions** carefully:
{{ instructions }}

Moreover:
- **Do not make up facts**—use only the provided information.
- **Do not make up quotes**—use only the provided quotes **in verbatim**.
- **Infuse your writing with wit, charm, and humor**
- Use **simple HTML tags** for formatting:
  - `<h1>` for the main title
  - `<h2>` for subheadings
  - `<strong>` for emphasis
  - `<blockquote>` for quotes
- Do not use any other formatting (e.g. markdown) but html tags(e.g. <strong>Strong</strong>, not **Strong**)
- You always need `<h1>`, article lead, at least 2 `<h2>`
- Keep **paragraphs between 3-5 sentences** for readability.
- Keep in mind current date: {{ current_date }}
- Return **only the article**—**no additional comments** or explanations are necessary.

"""

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
{{ example_articles }}

### Reference Articles:
These are articles on the similar topic written by our competitors. Make sure your journalist will make a better job:
{{ benchmark_articles }}
"""

followup_agent_prompt = """You are given an article:

#####################
{{ finished_article }}
#####################

Please analyze it thoroughly and perform the following steps:
1. Propose 10 clickbait-style alternative titles that capture attention. Each title should:
   - Highlight at least one unique or intriguing detail from the article.
   - Pose some form of puzzle, mystery, or question to entice readers.
   - Differ from each other in style, tone, or focus.
    
    You can find examples of good titles for various articles—use their style and structure for inspiration:
    #####
    Szokujące sceny na proteście Bąkiewicza, do akcji wkroczyła policja. Szef MSWiA ostro komentuje
    Mentzen już zaciera ręce. Tak chce przechytrzyć Kaczyńskiego
    To warzywo jest kopalnią witamin. Jednak Polacy kręcą na nie nosem
    Niesłychane, co poseł Konfederacji wypalił o Kaczyńskim. Jego słowa obiegły całą Polskę
    Rzecznik Nawrockiego nie wytrzymał. Wałęsa usłyszał, co o nim myślą
    Wjechał konno i miał suknię z peleryną. Ten polski ślub przebił wszystko
    Kto tak naprawdę zapłacił za wesele prezydentówny? Są niepodważalne dowody, które rozwiewają wątpliwości
    Nigdy nie dodawaj tego składnika do sałatki greckiej. Grecy poczują się urażeni
    Myslovitz przerwał koncert przez... Brauna. Zrobiło się poważnie
    Baśniowa kraina tuż przy polskiej granicy – to jedynie 3,5 godziny jazdy z Krakowa
    Było symbolem Malty. 8 lat temu runęło do morza
    Skiba nie wytrzymał po słowach Chorosińskiej. Z riposty zrobił się mem
    Największy lęk Joanny Kołaczkowskiej stał się prawdą. O kancerofobii mówiła głośno od lat
    Zakwitły już nad Bałtykiem. Są piękne, ale śmiertelnie niebezpieczne
    Jak nie robić zdjęć w podróży. Takie zachowanie to naruszenie zasad
    "To jest skandal!" Miał zamiatać ulice, ale PAD go ułaskawił. Komentarze mówią wszystko o... Dudzie
    #####
    
2. Suggest 5 new article topics that relate—directly or loosely—to the content of the "finished_article." Each topic should:
   - Be interesting enough to link from or to the original article.
   - Offer a fresh perspective or expand on the ideas mentioned.


"""

usage_tracking_agent_prompt = """
You are a meticulous auditor. Your task is to analyze a finished article and determine which of the provided facts and quotes were used.

### Finished Article:
{{ article_text }}

### List of Available Facts:
{{ list_of_facts }}

### List of Available Quotes:
{{ list_of_quotes }}


### Instructions:
1.  Read the "Finished Article" carefully.
2.  Review the "List of Available Facts".
3.  Review the "List of Available Quotes".
4.  Identify which facts and quotes from the lists are present in the article. **A fact or quote is considered "used" even if it has been slightly rephrased, paraphrased, or partially quoted**, as long as the core information is clearly present.
5.  Your output must be a list of the exact, original strings of the facts and quotes that you identified as being used. Do not include any items that were not used.

"""