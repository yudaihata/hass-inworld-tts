"""The Inworld AI text-to-speech integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from aiohttp import ClientResponseError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import CONF_MODEL, DEFAULT_MODEL, MODEL_TTS_2, MODEL_TTS_2_FLASH, MODELS
from .voices import async_list_voices

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.TTS, Platform.STT]


@dataclass(kw_only=True, slots=True)
class InworldTTSData:
    """Inworld AI TTS runtime data."""

    api_key: str
    voices: list[dict]


type InworldTTSConfigEntry = ConfigEntry[InworldTTSData]


async def async_setup_entry(hass: HomeAssistant, entry: InworldTTSConfigEntry) -> bool:
    """Set up Inworld AI TTS from a config entry."""
    entry.async_on_unload(entry.add_update_listener(update_listener))

    api_key = entry.data[CONF_API_KEY]

    # Read and cache the full catalog once for both authentication and voice selection.
    try:
        voices = await async_list_voices(hass, api_key)
    except ClientResponseError as err:
        if err.status in (401, 403):
            raise ConfigEntryAuthFailed("Inworld AI authentication failed") from err
        raise ConfigEntryNotReady(f"Inworld voice API returned HTTP {err.status}") from err
    except Exception as err:
        raise ConfigEntryNotReady(f"Failed to connect to Inworld AI: {err}") from err

    entry.runtime_data = InworldTTSData(api_key=api_key, voices=voices)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: InworldTTSConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, config_entry: InworldTTSConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: InworldTTSConfigEntry) -> bool:
    """Replace retired TTS 1.5 selections without changing entry/entity identifiers."""
    if entry.version > 2:
        return False
    if entry.version == 1:
        options = dict(entry.options)
        old_model = options.get(CONF_MODEL, DEFAULT_MODEL)
        replacements = {
            "inworld-tts-1.5-max": MODEL_TTS_2,
            "inworld-tts-1.5-mini": MODEL_TTS_2_FLASH,
        }
        model = replacements.get(old_model, old_model)
        options[CONF_MODEL] = model if model in MODELS else DEFAULT_MODEL
        hass.config_entries.async_update_entry(entry, options=options, version=2)
    return True
