from pydantic import BaseModel


class CreateJobRequest(BaseModel):
    html: str
    article_id: str | None = None
    template_name: str = ""


class CreateJobResponse(BaseModel):
    job_id: str


class WebhookPayload(BaseModel):
    job_id: str
    status: str  # "done" | "failed"
    url: str | None = None
    error: str | None = None


class EnableResponse(BaseModel):
    enabled: bool
