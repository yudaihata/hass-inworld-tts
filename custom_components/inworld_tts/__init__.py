"""The Inworld AI text-to-speech integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import INWORLD_VOICES_API_URL

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.TTS]


@dataclass(kw_only=True, slots=True)
class InworldTTSData:
    """Inworld AI TTS runtime data."""

    api_key: str


type InworldTTSConfigEntry = ConfigEntry[InworldTTSData]


async def async_setup_entry(hass: HomeAssistant, entry: InworldTTSConfigEntry) -> bool:
    """Set up Inworld AI TTS from a config entry."""
    entry.async_on_unload(entry.add_update_listener(update_listener))

    api_key = entry.data[CONF_API_KEY]

    # Validate the API key by listing voices (no API credits used)
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            INWORLD_VOICES_API_URL,
            headers={"Authorization": f"Basic {api_key}"},
        ) as resp:
            if resp.status in (401, 403):
                raise ConfigEntryAuthFailed("Inworld AI authentication failed")
            if resp.status not in (200, 201):
                raise ConfigEntryNotReady(f"Inworld AI API returned HTTP {resp.status}")
    except ConfigEntryAuthFailed:
        raise
    except ConfigEntryNotReady:
        raise
    except Exception as err:
        raise ConfigEntryNotReady(f"Failed to connect to Inworld AI: {err}") from err

    entry.runtime_data = InworldTTSData(api_key=api_key)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: InworldTTSConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, config_entry: InworldTTSConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
