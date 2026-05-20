import httpx
from typing import Optional


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HEADERS = {"User-Agent": "DirectProperty/1.0 (joshuaokoghie111@gmail.com)"}


async def geocode_address(
    address: str,
    city: str,
    state: str,
    lga: str,
) -> tuple[Optional[float], Optional[float]]:
    """Return (latitude, longitude) for a Nigerian property address via Nominatim.

    Returns (None, None) on any failure — never raises.
    """
    parts = [p for p in [address, lga, city, state, "Nigeria"] if p and p.strip()]
    query = ", ".join(parts)

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                NOMINATIM_URL,
                params={"q": query, "format": "json", "limit": "1"},
                headers=NOMINATIM_HEADERS,
            )
            resp.raise_for_status()
            results = resp.json()
            if results:
                return float(results[0]["lat"]), float(results[0]["lon"])
            # Retry with a broader query (state + lga only) if exact address returns nothing
            broad_query = f"{lga}, {state}, Nigeria"
            resp2 = await client.get(
                NOMINATIM_URL,
                params={"q": broad_query, "format": "json", "limit": "1"},
                headers=NOMINATIM_HEADERS,
            )
            resp2.raise_for_status()
            results2 = resp2.json()
            if results2:
                return float(results2[0]["lat"]), float(results2[0]["lon"])
    except Exception:
        pass

    return None, None
