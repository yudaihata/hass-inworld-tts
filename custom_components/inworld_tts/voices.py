"""Load the current Voice API catalog, including every page."""

from aiohttp import ClientTimeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import INWORLD_VOICES_API_URL


async def async_list_voices(hass: HomeAssistant, api_key: str) -> list[dict]:
    """Fetch visible system/custom voices; deduplicate by synthesis ID."""
    session = async_get_clientsession(hass)
    voices: dict[str, dict] = {}
    params = {"pageSize": 2000}
    seen_tokens: set[str] = set()
    while True:
        async with session.get(
            INWORLD_VOICES_API_URL,
            headers={"Authorization": f"Basic {api_key}"},
            params=params,
            timeout=ClientTimeout(total=30),
        ) as response:
            response.raise_for_status()
            data = await response.json()
        for voice in data.get("voices", []):
            if voice_id := voice.get("voiceId"):
                voices[voice_id] = voice
        if not (token := data.get("nextPageToken")):
            return list(voices.values())
        if token in seen_tokens:
            raise ValueError("Inworld voice API repeated a pagination token")
        seen_tokens.add(token)
        params = {**params, "pageToken": token}
