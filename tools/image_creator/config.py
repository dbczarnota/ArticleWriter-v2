import os

HTML2MEDIA_BASE_URL: str = os.environ.get(
    "HTML2MEDIA_BASE_URL", "https://headlinesforge.com/html2media"
)
HTML2MEDIA_ADMIN_SECRET: str = os.environ.get("HTML2MEDIA_ADMIN_SECRET", "")
HTML2MEDIA_WEBHOOK_SECRET: str = os.environ.get("HTML2MEDIA_WEBHOOK_SECRET", "")
PUBLIC_BASE_URL: str = os.environ.get("PUBLIC_BASE_URL", "https://headlinesforge.com")
WEBHOOK_PATH: str = "/v2/tools/image-creator/webhook"
