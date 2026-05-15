import os

HTML2MEDIA_BASE_URL: str = os.environ.get(
    "HTML2MEDIA_BASE_URL", "https://headlinesforge.com/html2media"
)
HTML2MEDIA_API_KEY: str = os.environ.get("HTML2MEDIA_API_KEY", "")
PUBLIC_BASE_URL: str = os.environ.get("PUBLIC_BASE_URL", "https://headlinesforge.com")
WEBHOOK_PATH: str = "/api/v2/tools/image-creator/webhook"
