from pydantic import BaseModel, Field


class ImageMeta(BaseModel):
    """Optional WordPress-style metadata for a generated image.

    Empty/missing fields are treated as not-set and are NOT persisted
    or forwarded to the webhook. All fields are user-facing free text.
    """

    filename: str = ""
    caption: str = ""
    description: str = ""
    alt: str = ""


class CreateJobRequest(BaseModel):
    html: str
    article_id: str | None = None
    template_name: str = ""
    meta: ImageMeta = Field(default_factory=ImageMeta)


class CreateJobResponse(BaseModel):
    job_id: str


class WebhookPayload(BaseModel):
    job_id: str
    status: str  # "done" | "failed"
    url: str | None = None
    error: str | None = None


class EnableResponse(BaseModel):
    enabled: bool
