# server.py

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Literal

# Import the ArticleWriter from your pipeline file
from article_writer import ArticleWriter

# Create the FastAPI application
app = FastAPI()

# Define a Pydantic model for the request body
class ArticleRequest(BaseModel):
    article_topic: str
    domains: List[str]
    number_of_queries: int = 2
    scraping_model: str = ""
    max_search_results: int = 3
    search_days: int = 30
    extraction_mode: Literal["markdown", "html", "llm"] = "markdown"

@app.post("/write_article")
def create_article(request_data: ArticleRequest):
    """
    POST to this endpoint with a JSON body describing the article parameters.
    
    Example request body:
    {
      "article_topic": "Sample Topic",
      "domains": ["example.com", "anotherdomain.com"],
      "number_of_queries": 2,
      "scraping_model": "",
      "max_search_results": 3,
      "search_days": 30,
      "extraction_mode": "markdown"
    }
    """
    final_text = ArticleWriter.write_article(
        article_topic=request_data.article_topic,
        domains=request_data.domains,
        number_of_queries=request_data.number_of_queries,
        scraping_model=request_data.scraping_model,
        max_search_results=request_data.max_search_results,
        search_days=request_data.search_days,
        extraction_mode=request_data.extraction_mode
    )
    return {"article": final_text}

# Optional: to run directly from this file
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
