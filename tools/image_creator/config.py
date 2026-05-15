import os

HTML2MEDIA_BASE_URL: str = os.environ.get(
    "HTML2MEDIA_BASE_URL", "https://headlinesforge.com/html2media"
)
HTML2MEDIA_ADMIN_SECRET: str = os.environ.get("HTML2MEDIA_ADMIN_SECRET", "")
PUBLIC_BASE_URL: str = os.environ.get("PUBLIC_BASE_URL", "https://headlinesforge.com")
# In-cluster URL the htmltomedia worker should POST the webhook to. Using the
# public hostname is blocked by Cloudflare (bot-fight-mode returns 403/1010
# on non-browser User-Agents). Set this to a k8s service DNS like
# http://backend.headlinesforge.svc.cluster.local so the callback short-
# circuits the public ingress + WAF.
INTERNAL_CALLBACK_BASE_URL: str = os.environ.get(
    "INTERNAL_CALLBACK_BASE_URL", PUBLIC_BASE_URL
)
WEBHOOK_PATH: str = "/v2/tools/image-creator/webhook"
