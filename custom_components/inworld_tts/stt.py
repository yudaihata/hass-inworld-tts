"""Inworld speech recognition for Home Assistant Assist."""

from __future__ import annotations

import asyncio
import base64
import logging
from collections.abc import AsyncIterable

from aiohttp import ClientTimeout
from homeassistant.components import stt
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import InworldTTSConfigEntry
from .const import DOMAIN, INWORLD_STT_API_URL, STT_MODEL

_LOGGER = logging.getLogger(__name__)

# https://docs.inworld.ai/stt/languages
SUPPORTED_LANGUAGES = [
    "ar", "yue", "zh", "cs", "da", "nl", "en", "fil", "fi", "fr",
    "de", "el", "hi", "hu", "id", "it", "ja", "ko", "mk", "ms",
    "fa", "pl", "pt", "ro", "ru", "es", "sv", "th", "tr", "vi",
]
# Bound memory and stay below the 16 MiB JSON request limit after Base64 encoding.
MAX_AUDIO_BYTES = 10 * 1024 * 1024


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: InworldTTSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a separate STT entity using the same credentials as TTS."""
    async_add_entities([
        InworldSTTEntity(config_entry.runtime_data.api_key, config_entry.entry_id)
    ])


class InworldSTTEntity(stt.SpeechToTextEntity):
    """Transcribe an Assist utterance after Home Assistant finishes capturing it."""

    _attr_name = "Inworld AI"

    def __init__(self, api_key: str, entry_id: str) -> None:
        """Initialize the speech recognition service."""
        self._api_key = api_key
        self._attr_unique_id = f"{entry_id}-stt"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Inworld AI",
            name="Inworld AI",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def supported_languages(self) -> list[str]:
        """Return Inworld STT's documented languages."""
        return SUPPORTED_LANGUAGES

    @property
    def supported_formats(self) -> list[stt.AudioFormats]:
        """Accept the Assist PCM stream."""
        return [stt.AudioFormats.WAV]

    @property
    def supported_codecs(self) -> list[stt.AudioCodecs]:
        """Accept signed little-endian PCM."""
        return [stt.AudioCodecs.PCM]

    @property
    def supported_bit_rates(self) -> list[stt.AudioBitRates]:
        """Accept 16-bit samples."""
        return [stt.AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[stt.AudioSampleRates]:
        """Use Inworld's recommended rate and Assist's native input rate."""
        return [stt.AudioSampleRates.SAMPLERATE_16000]

    @property
    def supported_channels(self) -> list[stt.AudioChannels]:
        """Accept mono speech."""
        return [stt.AudioChannels.CHANNEL_MONO]

    async def async_process_audio_stream(
        self, metadata: stt.SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> stt.SpeechResult:
        """Buffer a bounded utterance and send it to the synchronous STT API."""
        if not self.check_metadata(metadata):
            return stt.SpeechResult(None, stt.SpeechResultState.ERROR)
        try:
            audio = bytearray()
            async with asyncio.timeout(120):
                async for chunk in stream:
                    if len(audio) + len(chunk) > MAX_AUDIO_BYTES:
                        _LOGGER.error("Inworld STT audio exceeds the upload limit")
                        return stt.SpeechResult(None, stt.SpeechResultState.ERROR)
                    audio.extend(chunk)
            if not audio:
                return stt.SpeechResult(None, stt.SpeechResultState.ERROR)
            session = async_get_clientsession(self.hass)
            async with session.post(
                INWORLD_STT_API_URL,
                headers={
                    "Authorization": f"Basic {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "transcribeConfig": {
                        "modelId": STT_MODEL,
                        "audioEncoding": "LINEAR16",
                        "language": metadata.language,
                        "sampleRateHertz": int(metadata.sample_rate),
                        "numberOfChannels": int(metadata.channel),
                    },
                    "audioData": {"content": base64.b64encode(audio).decode("ascii")},
                },
                timeout=ClientTimeout(total=60),
            ) as response:
                if response.status in (401, 403):
                    _LOGGER.error("Inworld STT authentication failed")
                    return stt.SpeechResult(None, stt.SpeechResultState.ERROR)
                response.raise_for_status()
                result = await response.json()
            text = result.get("transcription", {}).get("transcript")
            if not isinstance(text, str):
                raise TypeError("Missing transcription in Inworld STT response")
        except Exception:
            _LOGGER.exception("Inworld STT request failed")
            return stt.SpeechResult(None, stt.SpeechResultState.ERROR)
        return stt.SpeechResult(text, stt.SpeechResultState.SUCCESS)
