# server.py
import httpx

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Literal

# Import the ArticleWriter from your pipeline file
from article_writer import ArticleWriter

import queue
import threading
import time

# Create the FastAPI application
app = FastAPI()

# Define a Pydantic model for the request body
class ArticleRequest(BaseModel):
    id: str
    topic: str
    domains: str
    number_of_queries: int = 2
    scraping_model: str = ""
    max_search_results: int = 3
    search_days: int = 30
    extraction_mode: Literal["markdown", "html", "llm"] = "markdown"

def send_response(id, article_text):
    try:
        webhook_url = "https://hook.eu1.make.com/gs74hirsewkmxbvpp15tpgb78ohl4g28"
        data = {
            "ID": id,
            "article_text": article_text
        }
        print(f"send response {data}")
        with httpx.Client() as client:
            response = client.post(webhook_url, json=data)
        print(f"")    
    except httpx.RequestError as e:
        print(f"An error occurred while making the request: {e}")
        return "Error occurred during the request."

    # Print the status code
    print(f"Response status code: {response.status_code}")

    # Try to parse JSON if the response contains JSON content
    try:
        if response.headers.get("Content-Type", "").startswith("application/json"):
            print("Response JSON content:", response.json())  # JSON response content
        else:
            print("Response text content:", response.text)  # Fallback to printing raw text
    except httpx.JSONDecodeError:
        print("Response is not JSON format. Raw content:")
        print(response.text)



def worker(q):
    while True:
        job = q.get()  # Get a job from the queue
        if job is None:
            break  # Exit if no more jobs
        print(f"Processing job: {job}")
        time.sleep(2)  # Simulate a long-running task
        
        domains = job.domains.split(",")

        final_text = ArticleWriter.write_article(
            article_topic=job.topic,
            domains=domains,
            number_of_queries=job.number_of_queries,
            scraping_model=job.scraping_model,
            max_search_results=job.max_search_results,
            search_days=job.search_days,
            extraction_mode=job.extraction_mode
        )
        print(f"final_text {final_text}")

        print(f"Finished job: {job}")

        send_response(job.id, final_text)
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
        print(f"adding new job")
        job_queue.put(it)
        print(f"queue: {job_queue.qsize()}")

    # final_text = ArticleWriter.write_article(
    #     article_topic=request_data.topic,
    #     domains=request_data.domains,
    #     number_of_queries=request_data.number_of_queries,
    #     scraping_model=request_data.scraping_model,
    #     max_search_results=request_data.max_search_results,
    #     search_days=request_data.search_days,
    #     extraction_mode=request_data.extraction_mode
    # )
    # print(f"final_text {final_text}")
    # return {"article": final_text}
    return {"status": "OK"}

# Optional: to run directly from this file
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
