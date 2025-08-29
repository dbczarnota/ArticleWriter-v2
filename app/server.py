# server.py
import httpx

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Literal, Optional

# Import the ArticleWriter from your pipeline file
from article_writer import ArticleWriter

import queue
import threading
import time

# Create the FastAPI application
app = FastAPI()

import logging
from rich.logging import RichHandler

logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(message)s",
        handlers=[RichHandler(rich_tracebacks=True, markup=True)],
    )


logger = logging.getLogger(__name__)

# Define a Pydantic model for the request body
class ArticleRequest(BaseModel):
    id: str
    topic: str
    urls: Optional[str]
    domains: Optional[str]
    number_of_queries: int = 2
    scraping_model: str = ""
    max_search_results: int = 3
    search_days: int = 30
    extraction_mode: Literal["markdown", "html", "llm"] = "markdown"
    provide_llm_facts: Literal["yes", "no"] = "no"  # <-- new parameter added
    additional_instructions: Optional[str] = None


def send_response(id, article_text, topic):
    try:
        webhook_url = "https://hook.eu1.make.com/gs74hirsewkmxbvpp15tpgb78ohl4g28"
        data = {"ID": id, "article_text": article_text, "topic": topic}
        logger.info(f"send response {data}")
        with httpx.Client() as client:
            response = client.post(webhook_url, json=data)
        logger.info(f"")
    except httpx.RequestError as e:
        logger.info(f"An error occurred while making the request: {e}")
        return "Error occurred during the request."

    # logger.info the status code
    logger.info(f"Response status code: {response.status_code}")

    # Try to parse JSON if the response contains JSON content
    try:
        if response.headers.get("Content-Type", "").startswith("application/json"):
            logger.info(
                "Response JSON content:", response.json()
            )  # JSON response content
        else:
            logger.info(
                "Response text content:", response.text
            )  # Fallback to logger.infoing raw text
    except httpx.JSONDecodeError:
        logger.info("Response is not JSON format. Raw content:")
        logger.info(response.text)


def worker(q):
    while True:
        try:
            job = q.get()  # Get a job from the queue
            if job is None:
                break  # Exit if no more jobs
            logger.info(f"Processing job: {job}")

            if job.domains != None:
                domains = job.domains.split("|")
            else:
                domains = []

            if job.urls != None:
                urls = job.urls.split("|")
            else:
                urls = []

            try:
                final_text = ArticleWriter.write_article(
                    article_topic=job.topic,
                    domains=domains,
                    urls=urls,
                    number_of_queries=job.number_of_queries,
                    scraping_model=job.scraping_model,
                    max_search_results=job.max_search_results,
                    search_days=job.search_days,
                    extraction_mode=job.extraction_mode,
                    provide_llm_facts=job.provide_llm_facts,  # <-- pass the parameter
                    additional_instructions=job.additional_instructions,
                )
            except Exception as e:
                logger.error(f"Exception in  ArticleWriter.write_article {e}")

            logger.info(f"final_text {final_text}")

            logger.info(f"Finished job: {job}")

            send_response(job.id, final_text, job.topic)
        finally:
            logger.info(f"Mark task as completed {job}")
            q.task_done()  # Mark the job as done


job_queue = queue.Queue()

num_workers = 1
threads = []
for _ in range(num_workers):
    t = threading.Thread(target=worker, args=(job_queue,))
    t.start()
    threads.append(t)

job_queue.join()


@app.post("/write_article")
def create_article(request_data: List[ArticleRequest]):
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
    for it in request_data:
        logger.info(f"adding new job")
        job_queue.put(it)
        logger.info(f"queue: {job_queue.qsize()}")

    # final_text = ArticleWriter.write_article(
    #     article_topic=request_data.topic,
    #     domains=request_data.domains,
    #     number_of_queries=request_data.number_of_queries,
    #     scraping_model=request_data.scraping_model,
    #     max_search_results=request_data.max_search_results,
    #     search_days=request_data.search_days,
    #     extraction_mode=request_data.extraction_mode
    # )
    # logger.info(f"final_text {final_text}")
    # return {"article": final_text}
    return {"status": "OK"}


# Optional: to run directly from this file
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
