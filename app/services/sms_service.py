import httpx
import logging
from typing import Optional
from fastapi import HTTPException

logger = logging.getLogger(__name__)

_sms_client: Optional["BulkSMSNigeriaService"] = None


def get_sms_client() -> "BulkSMSNigeriaService":
    global _sms_client
    if _sms_client is None:
        from app.core.config import settings
        if not settings.BULKSMS_NIGERIA_API_TOKEN:
            raise ValueError("BULKSMS_NIGERIA_API_TOKEN is missing in .env")
        _sms_client = BulkSMSNigeriaService(
            api_token=settings.BULKSMS_NIGERIA_API_TOKEN,
            sender_id=settings.BULKSMS_NIGERIA_SENDER_ID,
        )
    return _sms_client


class BulkSMSNigeriaService:
    BASE_URL = "https://www.bulksmsnigeria.com/api/v2"
    TIMEOUT = 10

    def __init__(self, api_token: str, sender_id: str):
        self.api_token = api_token.strip()
        self.sender_id = sender_id.strip()[:11]
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def send_sms(self, to: str, message: str) -> dict:
        # Normalize phone: strip spaces/+, convert leading 0 to 234
        clean = to.replace(" ", "").strip().lstrip("+")
        if clean.startswith("0"):
            clean = "234" + clean[1:]
        elif not clean.startswith("234"):
            clean = "234" + clean

        payload = {
            "from": self.sender_id,
            "to": clean,
            "body": message,
            "gateway": "otp",
        }

        logger.info(f"Sending OTP SMS to {clean}")

        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                response = await client.post(
                    f"{self.BASE_URL}/sms", headers=self.headers, json=payload
                )
        except httpx.ConnectError as e:
            logger.error(f"SMS gateway unreachable (network/DNS error): {e}")
            return {}
        except httpx.TimeoutException as e:
            logger.error(f"SMS gateway timed out: {e}")
            return {}
        except httpx.HTTPError as e:
            logger.error(f"SMS HTTP error: {e}")
            return {}

        logger.debug(f"BulkSMS response {response.status_code}: {response.text[:300]}")

        if response.status_code != 200:
            logger.error(f"SMS gateway error {response.status_code}: {response.text[:200]}")
            return {}

        data = response.json()
        if data.get("status") == "error":
            error_msg = (
                data.get("error", {}).get("message")
                or data.get("message", "Unknown SMS error")
            )
            logger.error(f"SMS failed: {error_msg}")
            return {}

        logger.info(f"SMS sent – message_id: {data.get('data', {}).get('message_id')}")
        return data
