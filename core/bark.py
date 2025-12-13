import httpx
import urllib.parse
from core.config import settings
from loguru import logger

class BarkClient:
    def __init__(self, url: str = None):
        self.url = url or settings.BARK_URL
        # Remove trailing slash if present for consistent path building
        if self.url and self.url.endswith("/"):
            self.url = self.url[:-1]

    async def send(self, body: str, title: str = None, group: str = None, level: str = None, url: str = None):
        """
        Send a notification via Bark.
        """
        if not self.url:
            logger.warning("Bark API URL is not set. Notification skipped.")
            return

        # Encode params to be safe for URL components
        safe_body = urllib.parse.quote(body)
        safe_title = urllib.parse.quote(title) if title else None

        endpoint = self.url
        if safe_title:
            endpoint += f"/{safe_title}/{safe_body}"
        else:
            endpoint += f"/{safe_body}"

        params = {}
        if group:
            params["group"] = group
        if level:
            params["level"] = level
        if url:
            params["url"] = url

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(endpoint, params=params)
                resp.raise_for_status()
                logger.info(f"Bark notification sent: {title}")
            except Exception as e:
                logger.error(f"Failed to send Bark notification: {e}")

bark = BarkClient()
